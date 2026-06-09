"""Report download helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from tsa_throughput.exceptions import DownloadError, ManifestError, StorageError
from tsa_throughput.manifest import (
    find_manifest_entry,
    load_runtime_manifest,
    save_runtime_manifest,
    upsert_downloaded_report,
)
from tsa_throughput.models import DownloadResult, RuntimeManifestEntry, ThroughputReport
from tsa_throughput.storage import LocalStorage

PDF_HEADER = b"%PDF"


def download_report(
    report: ThroughputReport,
    storage: LocalStorage,
    manifest_path: Path | None = None,
    fetch_bytes: Callable[[str], bytes] | None = None,
    overwrite: bool = False,
) -> DownloadResult:
    """Download one normalized TSA throughput report into local storage."""
    source_url = _required_value(report.source_url, "source_url")
    storage_key = _required_value(report.canonical_filename, "canonical_filename")
    canonical_id = _required_value(report.canonical_id, "canonical_id")
    manifest_file = _manifest_path(storage, manifest_path)

    manifest = _load_manifest(manifest_file)
    existing_entry = find_manifest_entry(manifest, canonical_id)
    existing_path = _manifest_entry_path(storage, existing_entry, storage_key)

    _raise_for_conflicting_existing_file(report, manifest, overwrite)

    if existing_entry is not None and existing_path.is_file() and not overwrite:
        sha256, size_bytes = _file_metadata(existing_path)
        return DownloadResult(
            report=report,
            status="skipped_existing",
            path=existing_path,
            sha256=sha256,
            size_bytes=size_bytes,
        )

    storage_path = _storage_path(storage, storage_key)
    if storage_path.is_file() and existing_entry is None and not overwrite:
        pdf_bytes = _read_existing_pdf(storage, storage_key)
        sha256, size_bytes = _bytes_metadata(pdf_bytes)
        _save_entry(report, storage, manifest_file, manifest, storage_path, sha256, size_bytes)
        return DownloadResult(
            report=report,
            status="skipped_existing",
            path=storage_path,
            sha256=sha256,
            size_bytes=size_bytes,
            message="registered existing local file",
        )

    existed_before_write = existing_entry is not None or storage_path.is_file()
    content = _fetch_pdf(source_url, fetch_bytes)
    path = _write_pdf(storage, storage_key, content, overwrite=overwrite)
    sha256, size_bytes = _bytes_metadata(content)
    manifest = _load_manifest(manifest_file)
    _save_entry(report, storage, manifest_file, manifest, path, sha256, size_bytes)

    status = "overwritten" if overwrite and existed_before_write else "downloaded"
    return DownloadResult(
        report=report,
        status=status,
        path=path,
        sha256=sha256,
        size_bytes=size_bytes,
    )


def download_missing_reports(
    reports: list[ThroughputReport],
    storage: LocalStorage,
    manifest_path: Path | None = None,
    fetch_bytes: Callable[[str], bytes] | None = None,
    overwrite: bool = False,
) -> list[DownloadResult]:
    """Download reports in order, returning one result per successfully handled report."""
    return [
        download_report(
            report,
            storage,
            manifest_path=manifest_path,
            fetch_bytes=fetch_bytes,
            overwrite=overwrite,
        )
        for report in reports
    ]


def _manifest_path(storage: LocalStorage, manifest_path: Path | None) -> Path:
    if manifest_path is not None:
        return Path(manifest_path)
    return storage.root / "manifest.json"


def _load_manifest(manifest_path: Path):
    try:
        return load_runtime_manifest(manifest_path)
    except ManifestError as exc:
        raise DownloadError(f"could not load runtime manifest: {manifest_path}") from exc


def _save_entry(
    report: ThroughputReport,
    storage: LocalStorage,
    manifest_path: Path,
    manifest,
    path: Path,
    sha256: str,
    size_bytes: int,
) -> None:
    entry = _manifest_entry(report, storage, path, sha256, size_bytes)
    try:
        save_runtime_manifest(upsert_downloaded_report(manifest, entry), manifest_path)
    except ManifestError as exc:
        raise DownloadError(f"could not update runtime manifest: {manifest_path}") from exc


def _manifest_entry(
    report: ThroughputReport,
    storage: LocalStorage,
    path: Path,
    sha256: str,
    size_bytes: int,
) -> RuntimeManifestEntry:
    return RuntimeManifestEntry(
        canonical_id=_required_value(report.canonical_id, "canonical_id"),
        week_start=report.week_start,
        week_end=report.week_end,
        source_url=_required_value(report.source_url, "source_url"),
        source_filename=_source_filename(report),
        canonical_filename=_required_value(report.canonical_filename, "canonical_filename"),
        local_path=_relative_local_path(storage, path),
        sha256=sha256,
        bytes=size_bytes,
        downloaded_at=_utc_now_iso(),
        date_confidence=report.date_confidence,
    )


def _source_filename(report: ThroughputReport) -> str:
    return _required_value(report.source_filename or report.original_filename, "source_filename")


def _manifest_entry_path(
    storage: LocalStorage,
    entry: RuntimeManifestEntry | None,
    fallback_key: str,
) -> Path:
    if entry is None:
        return _storage_path(storage, fallback_key)
    return _storage_path(storage, entry.local_path)


def _storage_path(storage: LocalStorage, key: str) -> Path:
    try:
        return storage.path_for(key)
    except StorageError as exc:
        raise DownloadError(f"could not resolve storage path for {key!r}") from exc


def _read_existing_pdf(storage: LocalStorage, key: str) -> bytes:
    try:
        content = storage.read_bytes(key)
    except StorageError as exc:
        raise DownloadError(f"could not read existing local file: {key}") from exc

    _validate_pdf(content)
    return content


def _fetch_pdf(source_url: str, fetch_bytes: Callable[[str], bytes] | None) -> bytes:
    fetcher = fetch_bytes or _default_fetch_bytes
    try:
        content = fetcher(source_url)
    except DownloadError:
        raise
    except Exception as exc:
        raise DownloadError(f"could not fetch report: {source_url}") from exc

    _validate_pdf(content)
    return content


def _write_pdf(storage: LocalStorage, key: str, content: bytes, overwrite: bool) -> Path:
    try:
        return storage.write_bytes(key, content, overwrite=overwrite)
    except StorageError as exc:
        raise DownloadError(f"could not write report to local storage: {key}") from exc


def _default_fetch_bytes(source_url: str) -> bytes:
    import httpx

    try:
        response = httpx.get(source_url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise DownloadError(f"could not fetch report: {source_url}") from exc
    return response.content


def _validate_pdf(content: bytes) -> None:
    if not content:
        raise DownloadError("downloaded report is empty")
    if not content.startswith(PDF_HEADER):
        raise DownloadError("downloaded report does not appear to be a PDF")


def _file_metadata(path: Path) -> tuple[str, int]:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise DownloadError(f"could not read local report: {path}") from exc

    _validate_pdf(content)
    return _bytes_metadata(content)


def _bytes_metadata(content: bytes) -> tuple[str, int]:
    return hashlib.sha256(content).hexdigest(), len(content)


def _relative_local_path(storage: LocalStorage, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(storage.root).as_posix()
    except ValueError as exc:
        raise DownloadError(f"local report path is outside storage root: {path}") from exc


def _raise_for_conflicting_existing_file(
    report: ThroughputReport,
    manifest,
    overwrite: bool,
) -> None:
    if report.date_confidence != "title_url_conflict" or overwrite:
        return

    canonical_filename = _required_value(report.canonical_filename, "canonical_filename")
    source_url = _required_value(report.source_url, "source_url")
    for entry in manifest.reports:
        if entry.canonical_filename == canonical_filename and entry.source_url != source_url:
            raise DownloadError(
                "conflicting report metadata maps to an existing canonical filename"
            )


def _required_value(value: str | None, field_name: str) -> str:
    if value is None or not value.strip():
        raise DownloadError(f"report is missing {field_name}")
    return value.strip()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
