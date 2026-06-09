from __future__ import annotations

import hashlib
import socket
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from tsa_throughput.download import download_missing_reports, download_report
from tsa_throughput.exceptions import DownloadError
from tsa_throughput.manifest import load_runtime_manifest
from tsa_throughput.models import ThroughputReport
from tsa_throughput.storage import LocalStorage

PDF_BYTES = b"%PDF-1.7\nreport bytes\n%%EOF\n"
UPDATED_PDF_BYTES = b"%PDF-1.7\nupdated report bytes\n%%EOF\n"


def test_download_report_downloads_pdf_to_canonical_filename_and_updates_manifest(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "raw")
    report = _report()
    calls: list[str] = []

    result = download_report(report, storage, fetch_bytes=_fetcher(PDF_BYTES, calls))

    assert result.status == "downloaded"
    assert result.path == storage.root / report.canonical_filename
    assert result.path.read_bytes() == PDF_BYTES
    assert result.sha256 == _sha256(PDF_BYTES)
    assert result.size_bytes == len(PDF_BYTES)
    assert result.bytes == len(PDF_BYTES)
    assert calls == [report.source_url]

    manifest_path = storage.root / "manifest.json"
    assert manifest_path.is_file()
    manifest = load_runtime_manifest(manifest_path)
    assert len(manifest.reports) == 1
    entry = manifest.reports[0]
    assert entry.canonical_id == report.canonical_id
    assert entry.week_start == report.week_start
    assert entry.week_end == report.week_end
    assert entry.source_url == report.source_url
    assert entry.source_filename == report.source_filename
    assert entry.canonical_filename == report.canonical_filename
    assert entry.local_path == report.canonical_filename
    assert not Path(entry.local_path).is_absolute()
    assert entry.sha256 == _sha256(PDF_BYTES)
    assert entry.bytes == len(PDF_BYTES)
    assert entry.date_confidence == report.date_confidence


def test_download_report_skips_existing_manifest_entry_and_local_file(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "raw")
    report = _report()
    first = download_report(report, storage, fetch_bytes=_fetcher(PDF_BYTES))

    result = download_report(report, storage, fetch_bytes=_failing_fetcher)

    assert result.status == "skipped_existing"
    assert result.path == first.path
    assert result.sha256 == _sha256(PDF_BYTES)
    assert result.size_bytes == len(PDF_BYTES)
    assert result.path.read_bytes() == PDF_BYTES


def test_download_report_redownloads_when_overwrite_is_true(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "raw")
    report = _report()
    download_report(report, storage, fetch_bytes=_fetcher(PDF_BYTES))

    result = download_report(
        report,
        storage,
        fetch_bytes=_fetcher(UPDATED_PDF_BYTES),
        overwrite=True,
    )

    assert result.status == "overwritten"
    assert result.path == storage.root / report.canonical_filename
    assert result.path.read_bytes() == UPDATED_PDF_BYTES
    assert result.sha256 == _sha256(UPDATED_PDF_BYTES)

    manifest = load_runtime_manifest(storage.root / "manifest.json")
    assert manifest.reports[0].sha256 == _sha256(UPDATED_PDF_BYTES)
    assert manifest.reports[0].bytes == len(UPDATED_PDF_BYTES)


def test_download_report_registers_existing_local_pdf_without_refetching(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "raw")
    report = _report()
    storage.write_bytes(report.canonical_filename or "", PDF_BYTES)

    result = download_report(report, storage, fetch_bytes=_failing_fetcher)

    assert result.status == "skipped_existing"
    assert result.message == "registered existing local file"
    assert result.sha256 == _sha256(PDF_BYTES)

    manifest = load_runtime_manifest(storage.root / "manifest.json")
    assert len(manifest.reports) == 1
    assert manifest.reports[0].canonical_id == report.canonical_id
    assert manifest.reports[0].sha256 == _sha256(PDF_BYTES)
    assert manifest.reports[0].bytes == len(PDF_BYTES)


@pytest.mark.parametrize("content", [b"", b"not a pdf"])
def test_download_report_rejects_invalid_downloads_without_updating_manifest(
    tmp_path: Path,
    content: bytes,
) -> None:
    storage = LocalStorage(tmp_path / "raw")

    with pytest.raises(DownloadError):
        download_report(_report(), storage, fetch_bytes=_fetcher(content))

    assert not (storage.root / "manifest.json").exists()
    assert not (storage.root / (_report().canonical_filename or "")).exists()


def test_download_report_rejects_missing_source_url(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "raw")
    report = _report(source_url="")

    with pytest.raises(DownloadError, match="source_url"):
        download_report(report, storage, fetch_bytes=_failing_fetcher)

    assert not (storage.root / "manifest.json").exists()


def test_download_report_wraps_failed_fetch_and_does_not_update_manifest(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "raw")

    with pytest.raises(DownloadError):
        download_report(_report(), storage, fetch_bytes=_failing_fetcher)

    assert not (storage.root / "manifest.json").exists()


def test_download_report_does_not_overwrite_conflicting_report_without_overwrite(
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "raw")
    original = _report(date_confidence="title_url_conflict")
    download_report(original, storage, fetch_bytes=_fetcher(PDF_BYTES))
    conflicting = _report(
        source_url="https://www.tsa.gov/sites/default/files/foia-readingroom/conflict.pdf",
        date_confidence="title_url_conflict",
    )

    with pytest.raises(DownloadError, match="conflicting"):
        download_report(conflicting, storage, fetch_bytes=_fetcher(UPDATED_PDF_BYTES))

    assert (storage.root / (original.canonical_filename or "")).read_bytes() == PDF_BYTES


def test_download_missing_reports_returns_one_result_per_input_report(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "raw")
    reports = [
        _report(),
        _report(
            week_start=date(2026, 6, 7),
            week_end=date(2026, 6, 13),
            canonical_id="tsa-throughput-week-ending-2026-06-13",
            source_filename="tsa-throughput-data-to-june-7-2026-to-june-13-2026.pdf",
            canonical_filename="tsa-throughput-week-ending-2026-06-13.pdf",
        ),
    ]
    calls: list[str] = []

    results = download_missing_reports(reports, storage, fetch_bytes=_fetcher(PDF_BYTES, calls))

    assert [result.status for result in results] == ["downloaded", "downloaded"]
    assert [result.report for result in results] == reports
    assert calls == [report.source_url for report in reports]


def test_download_report_uses_injected_fetcher_and_makes_no_live_network_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("Downloader should use injected fetch_bytes in tests")

    monkeypatch.setattr(socket, "socket", fail_socket)
    storage = LocalStorage(tmp_path / "raw")

    result = download_report(_report(), storage, fetch_bytes=_fetcher(PDF_BYTES))

    assert result.status == "downloaded"


def _report(**overrides: object) -> ThroughputReport:
    data = {
        "source_url": (
            "https://www.tsa.gov/sites/default/files/foia-readingroom/"
            "tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf"
        ),
        "week_start": date(2026, 5, 31),
        "week_end": date(2026, 6, 6),
        "canonical_id": "tsa-throughput-week-ending-2026-06-06",
        "title": "TSA Throughput Data to May 31, 2026 to June 6, 2026",
        "source_filename": "tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf",
        "canonical_filename": "tsa-throughput-week-ending-2026-06-06.pdf",
        "date_confidence": "title_url_match",
    }
    data.update(overrides)
    return ThroughputReport(**data)


def _fetcher(content: bytes, calls: list[str] | None = None) -> Callable[[str], bytes]:
    def fetch(source_url: str) -> bytes:
        if calls is not None:
            calls.append(source_url)
        return content

    return fetch


def _failing_fetcher(source_url: str) -> bytes:
    raise RuntimeError(f"unexpected fetch: {source_url}")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
