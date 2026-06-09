"""Installed TSA source manifest loading and writing helpers."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any

from tsa_throughput.exceptions import ManifestError
from tsa_throughput.models import SourceManifest, ThroughputReport

SOURCE_MANIFEST_SCHEMA_VERSION = 1
SOURCE_MANIFEST_ASSET = "source_manifest.json"
SOURCE_MANIFEST_SOURCE_NAME = "TSA FOIA Reading Room"
SOURCE_MANIFEST_LISTING_URL = (
    "https://www.tsa.gov/foia/readingroom?title=&field_foia_tax_category_target_id=1132&page=0"
)

_REPORT_FIELDS = {
    "canonical_id",
    "week_start",
    "week_end",
    "title",
    "source_url",
    "source_filename",
    "canonical_filename",
    "date_confidence",
    "listing_url",
    "alternate_urls",
}


def load_installed_source_manifest() -> SourceManifest:
    """Load the source manifest distributed with the installed package."""
    try:
        asset_text = (
            resources.files("tsa_throughput")
            .joinpath("assets", SOURCE_MANIFEST_ASSET)
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, OSError) as exc:
        raise ManifestError(
            f"could not read installed source manifest asset: {SOURCE_MANIFEST_ASSET}"
        ) from exc

    return _source_manifest_from_json_text(asset_text, "installed source manifest")


def load_source_manifest(path: Path) -> SourceManifest:
    """Load a source manifest from a filesystem path."""
    manifest_path = Path(path)
    try:
        return _source_manifest_from_json_text(
            manifest_path.read_text(encoding="utf-8"),
            f"source manifest: {manifest_path}",
        )
    except OSError as exc:
        raise ManifestError(f"could not read source manifest: {manifest_path}") from exc


def save_source_manifest(manifest: SourceManifest, path: Path) -> None:
    """Save a source manifest to stable, human-readable JSON."""
    manifest_path = Path(path)
    try:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(_source_manifest_to_json(manifest), indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise ManifestError(f"could not write source manifest: {manifest_path}") from exc


def create_source_manifest(
    reports: list[ThroughputReport],
    generated_at: str | None = None,
) -> SourceManifest:
    """Create a source manifest from normalized source report metadata."""
    return SourceManifest(
        schema_version=SOURCE_MANIFEST_SCHEMA_VERSION,
        generated_at=generated_at or _utc_now_iso(),
        source_name=SOURCE_MANIFEST_SOURCE_NAME,
        source_listing_url=SOURCE_MANIFEST_LISTING_URL,
        reports=_sort_reports(reports),
    )


def list_source_reports(
    manifest: SourceManifest | None = None,
) -> list[ThroughputReport]:
    """Return source reports from a provided or installed manifest."""
    source_manifest = manifest or load_installed_source_manifest()
    return list(source_manifest.reports)


def find_source_report(
    canonical_id: str,
    manifest: SourceManifest | None = None,
) -> ThroughputReport | None:
    """Return a source report by canonical ID, if present."""
    return next(
        (
            report
            for report in list_source_reports(manifest)
            if report.canonical_id == canonical_id
        ),
        None,
    )


def _source_manifest_from_json_text(text: str, context: str) -> SourceManifest:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"could not decode {context}") from exc

    return _source_manifest_from_json(data)


def _source_manifest_from_json(data: Any) -> SourceManifest:
    if not isinstance(data, dict):
        raise ManifestError("source manifest must be a JSON object")

    schema_version = data.get("schema_version")
    if schema_version != SOURCE_MANIFEST_SCHEMA_VERSION:
        raise ManifestError(
            f"unsupported source manifest schema_version: {schema_version!r}"
        )

    generated_at = data.get("generated_at")
    if not isinstance(generated_at, str):
        raise ManifestError("source manifest must include generated_at")

    source = data.get("source")
    if not isinstance(source, dict):
        raise ManifestError("source manifest must include source metadata")

    source_name = source.get("name")
    if not isinstance(source_name, str):
        raise ManifestError("source manifest source.name must be a string")

    source_listing_url = source.get("listing_url")
    if not isinstance(source_listing_url, str):
        raise ManifestError("source manifest source.listing_url must be a string")

    raw_reports = data.get("reports")
    if not isinstance(raw_reports, list):
        raise ManifestError("source manifest must include a reports list")

    return SourceManifest(
        schema_version=schema_version,
        generated_at=generated_at,
        source_name=source_name,
        source_listing_url=source_listing_url,
        reports=_sort_reports(
            [_throughput_report_from_json(item) for item in raw_reports]
        ),
    )


def _throughput_report_from_json(data: Any) -> ThroughputReport:
    if not isinstance(data, dict):
        raise ManifestError("source manifest report must be a JSON object")

    missing_fields = _REPORT_FIELDS - data.keys()
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise ManifestError(f"source manifest report missing required field(s): {missing}")

    try:
        return ThroughputReport(
            canonical_id=_required_string(data, "canonical_id"),
            week_start=_parse_iso_date(data["week_start"], "week_start"),
            week_end=_parse_iso_date(data["week_end"], "week_end"),
            title=_required_string(data, "title"),
            source_url=_required_string(data, "source_url"),
            source_filename=_required_string(data, "source_filename"),
            canonical_filename=_required_string(data, "canonical_filename"),
            date_confidence=_required_string(data, "date_confidence"),
            listing_url=_required_string(data, "listing_url"),
            alternate_urls=_alternate_urls(data["alternate_urls"]),
        )
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"invalid source manifest report: {data!r}") from exc


def _source_manifest_to_json(manifest: SourceManifest) -> dict[str, Any]:
    if manifest.schema_version != SOURCE_MANIFEST_SCHEMA_VERSION:
        raise ManifestError(
            f"unsupported source manifest schema_version: {manifest.schema_version!r}"
        )

    return {
        "schema_version": manifest.schema_version,
        "generated_at": manifest.generated_at,
        "source": {
            "name": manifest.source_name,
            "listing_url": manifest.source_listing_url,
        },
        "reports": [
            _throughput_report_to_json(report)
            for report in _sort_reports(manifest.reports)
        ],
    }


def _throughput_report_to_json(report: ThroughputReport) -> dict[str, Any]:
    return {
        "canonical_id": _report_required_string(report.canonical_id, "canonical_id"),
        "week_start": _format_iso_date(report.week_start),
        "week_end": _format_iso_date(report.week_end),
        "title": _report_required_string(report.title, "title"),
        "source_url": _report_required_string(report.source_url, "source_url"),
        "source_filename": _report_required_string(
            report.source_filename,
            "source_filename",
        ),
        "canonical_filename": _report_required_string(
            report.canonical_filename,
            "canonical_filename",
        ),
        "date_confidence": _report_required_string(
            report.date_confidence,
            "date_confidence",
        ),
        "listing_url": _report_required_string(report.listing_url, "listing_url"),
        "alternate_urls": list(report.alternate_urls),
    }


def _sort_reports(reports: list[ThroughputReport]) -> list[ThroughputReport]:
    return sorted(
        reports,
        key=lambda report: (
            report.week_end is None,
            -(report.week_end.toordinal()) if report.week_end is not None else 0,
            report.canonical_id or report.source_url,
        ),
    )


def _parse_iso_date(value: Any, field_name: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ManifestError(f"source manifest {field_name} must be a string or null")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ManifestError(f"invalid source manifest {field_name}: {value!r}") from exc


def _format_iso_date(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _required_string(data: dict[str, Any], field_name: str) -> str:
    value = data[field_name]
    if not isinstance(value, str):
        raise ManifestError(f"source manifest {field_name} must be a string")
    return value


def _report_required_string(value: str | None, field_name: str) -> str:
    if not isinstance(value, str):
        raise ManifestError(f"source manifest report {field_name} must be set")
    return value


def _alternate_urls(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ManifestError("source manifest alternate_urls must be a list of strings")
    return list(value)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
