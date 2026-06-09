"""Runtime download manifest loading and writing helpers."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from tsa_throughput.exceptions import ManifestError
from tsa_throughput.models import RuntimeManifest, RuntimeManifestEntry

RUNTIME_MANIFEST_SCHEMA_VERSION = 1

_REPORT_FIELDS = {
    "canonical_id",
    "week_start",
    "week_end",
    "source_url",
    "source_filename",
    "canonical_filename",
    "local_path",
    "sha256",
    "bytes",
    "downloaded_at",
    "date_confidence",
}


def load_runtime_manifest(path: Path) -> RuntimeManifest:
    """Load a local runtime download manifest."""
    manifest_path = Path(path)
    if not manifest_path.exists():
        return create_empty_runtime_manifest()

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestError(f"could not read runtime manifest: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"could not decode runtime manifest: {manifest_path}") from exc

    return _runtime_manifest_from_json(data)


def save_runtime_manifest(manifest: RuntimeManifest, path: Path) -> None:
    """Save a local runtime download manifest."""
    manifest_path = Path(path)
    try:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(_runtime_manifest_to_json(manifest), indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise ManifestError(f"could not write runtime manifest: {manifest_path}") from exc


def create_empty_runtime_manifest() -> RuntimeManifest:
    """Create an empty local runtime download manifest."""
    return RuntimeManifest(
        schema_version=RUNTIME_MANIFEST_SCHEMA_VERSION,
        updated_at=_utc_now_iso(),
        reports=[],
    )


def upsert_downloaded_report(
    manifest: RuntimeManifest,
    entry: RuntimeManifestEntry,
) -> RuntimeManifest:
    """Add or replace a downloaded report entry by canonical ID."""
    reports = [
        existing
        for existing in manifest.reports
        if existing.canonical_id != entry.canonical_id
    ]
    reports.append(entry)

    return RuntimeManifest(
        schema_version=manifest.schema_version,
        updated_at=_utc_now_iso(),
        reports=_sort_reports(reports),
    )


def find_manifest_entry(
    manifest: RuntimeManifest,
    canonical_id: str,
) -> RuntimeManifestEntry | None:
    """Return a manifest entry by canonical ID, if present."""
    return next(
        (
            entry
            for entry in manifest.reports
            if entry.canonical_id == canonical_id
        ),
        None,
    )


def _runtime_manifest_from_json(data: Any) -> RuntimeManifest:
    if not isinstance(data, dict):
        raise ManifestError("runtime manifest must be a JSON object")

    schema_version = data.get("schema_version")
    if schema_version != RUNTIME_MANIFEST_SCHEMA_VERSION:
        raise ManifestError(
            f"unsupported runtime manifest schema_version: {schema_version!r}"
        )

    updated_at = data.get("updated_at")
    if not isinstance(updated_at, str):
        raise ManifestError("runtime manifest must include updated_at")

    raw_reports = data.get("reports")
    if not isinstance(raw_reports, list):
        raise ManifestError("runtime manifest must include a reports list")

    return RuntimeManifest(
        schema_version=schema_version,
        updated_at=updated_at,
        reports=_sort_reports(
            [_runtime_manifest_entry_from_json(item) for item in raw_reports]
        ),
    )


def _runtime_manifest_entry_from_json(data: Any) -> RuntimeManifestEntry:
    if not isinstance(data, dict):
        raise ManifestError("runtime manifest report entry must be a JSON object")

    missing_fields = _REPORT_FIELDS - data.keys()
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise ManifestError(f"runtime manifest report missing required field(s): {missing}")

    try:
        return RuntimeManifestEntry(
            canonical_id=_required_string(data, "canonical_id"),
            week_start=_parse_iso_date(data["week_start"], "week_start"),
            week_end=_parse_iso_date(data["week_end"], "week_end"),
            source_url=_required_string(data, "source_url"),
            source_filename=_required_string(data, "source_filename"),
            canonical_filename=_required_string(data, "canonical_filename"),
            local_path=_required_string(data, "local_path"),
            sha256=_required_string(data, "sha256"),
            bytes=int(data["bytes"]),
            downloaded_at=_required_string(data, "downloaded_at"),
            date_confidence=_required_string(data, "date_confidence"),
        )
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"invalid runtime manifest report entry: {data!r}") from exc


def _runtime_manifest_to_json(manifest: RuntimeManifest) -> dict[str, Any]:
    if manifest.schema_version != RUNTIME_MANIFEST_SCHEMA_VERSION:
        raise ManifestError(
            f"unsupported runtime manifest schema_version: {manifest.schema_version!r}"
        )

    return {
        "schema_version": manifest.schema_version,
        "updated_at": manifest.updated_at,
        "reports": [
            _runtime_manifest_entry_to_json(entry)
            for entry in _sort_reports(manifest.reports)
        ],
    }


def _runtime_manifest_entry_to_json(entry: RuntimeManifestEntry) -> dict[str, Any]:
    return {
        "canonical_id": entry.canonical_id,
        "week_start": _format_iso_date(entry.week_start),
        "week_end": _format_iso_date(entry.week_end),
        "source_url": entry.source_url,
        "source_filename": entry.source_filename,
        "canonical_filename": entry.canonical_filename,
        "local_path": entry.local_path,
        "sha256": entry.sha256,
        "bytes": entry.bytes,
        "downloaded_at": entry.downloaded_at,
        "date_confidence": entry.date_confidence,
    }


def _sort_reports(reports: list[RuntimeManifestEntry]) -> list[RuntimeManifestEntry]:
    return sorted(
        reports,
        key=lambda entry: (
            entry.week_end is None,
            entry.week_end or date.max,
            entry.canonical_id,
        ),
    )


def _parse_iso_date(value: Any, field_name: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ManifestError(f"runtime manifest {field_name} must be a string or null")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ManifestError(f"invalid runtime manifest {field_name}: {value!r}") from exc


def _format_iso_date(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _required_string(data: dict[str, Any], field_name: str) -> str:
    value = data[field_name]
    if not isinstance(value, str):
        raise ManifestError(f"runtime manifest {field_name} must be a string")
    return value


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
