import csv
import json
import socket
from collections.abc import Callable
from datetime import date
from importlib import import_module
from pathlib import Path

import pytest

import tsa_throughput.cli
from tsa_throughput.cli import CANONICAL_COLUMNS, main
from tsa_throughput.discovery import TSA_READING_ROOM_URL, discover_report_links
from tsa_throughput.download import download_missing_reports
from tsa_throughput.models import SourceManifest, ThroughputReport
from tsa_throughput.parsing.plugins.historical_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    PARSER_NAME as HISTORICAL_PARSER_NAME,
)
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    PARSER_NAME,
)
from tsa_throughput.source_manifest import (
    SourceManifestRefreshResult,
    save_source_manifest,
)
from tsa_throughput.storage import LocalStorage

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf")
FIXTURES_DIR = Path("tests/fixtures")
PAGE_0_URL = TSA_READING_ROOM_URL
PAGE_1_URL = (
    "https://www.tsa.gov/foia/readingroom?title=&field_foia_tax_category_target_id=1132&page=1"
)
MODERN_CANONICAL_ID = "tsa-throughput-week-ending-2026-06-06"
NEWER_CANONICAL_ID = "tsa-throughput-week-ending-2026-06-13"
PDF_BYTES = b"%PDF-1.7\ncli report bytes\n%%EOF\n"
UPDATED_PDF_BYTES = b"%PDF-1.7\ncli updated report bytes\n%%EOF\n"
STRICT_HISTORICAL_PARSER_NAME = import_module(
    "tsa_throughput.parsing.plugins."
    "historical_total_pax_kcm_hourly_checkpoint_strict_pdfplumber"
).PARSER_NAME
PMIS_PARSER_NAME = import_module(
    "tsa_throughput.parsing.plugins."
    "historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber"
).PARSER_NAME
MARCH_2022_PARSER_NAME = import_module(
    "tsa_throughput.parsing.plugins."
    "historical_march_2022_total_pax_kcm_hourly_checkpoint_pdfplumber"
).PARSER_NAME


def test_discover_latest_command_exits_successfully_with_fixture_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_cli_fixture_discovery(monkeypatch)

    exit_code = main(["discover", "--latest"])

    assert exit_code == 0


def test_discover_latest_text_output_includes_known_canonical_id(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_cli_fixture_discovery(monkeypatch)

    exit_code = main(["discover", "--latest"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert MODERN_CANONICAL_ID in captured.out
    assert "2026-05-31" in captured.out
    assert "2026-06-06" in captured.out
    assert "tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf" in captured.out
    assert "title_url_match" in captured.out
    assert "https://www.tsa.gov/sites/default/files/foia-readingroom/" in captured.out


def test_discover_latest_json_output_is_valid_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_cli_fixture_discovery(monkeypatch)

    exit_code = main(["discover", "--latest", "--format", "json"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)


def test_discover_latest_json_output_includes_normalized_report_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_cli_fixture_discovery(monkeypatch)

    exit_code = main(["discover", "--latest", "--format", "json"])

    assert exit_code == 0
    reports = json.loads(capsys.readouterr().out)
    report = next(item for item in reports if item["canonical_id"] == MODERN_CANONICAL_ID)
    assert report["week_start"] == "2026-05-31"
    assert report["week_end"] == "2026-06-06"
    assert report["source_filename"] == "tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf"
    assert report["canonical_filename"] == "tsa-throughput-week-ending-2026-06-06.pdf"
    assert report["date_confidence"] == "title_url_match"
    assert report["source_url"].endswith("tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf")


def test_discover_max_pages_one_only_fetches_one_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    _patch_cli_fixture_discovery(monkeypatch, calls=calls)

    exit_code = main(["discover", "--max-pages", "1"])

    assert exit_code == 0
    assert calls == [PAGE_0_URL]


def test_discover_all_follows_pagination(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    _patch_cli_fixture_discovery(monkeypatch, calls=calls)

    exit_code = main(["discover", "--all"])

    assert exit_code == 0
    assert calls == [PAGE_0_URL, PAGE_1_URL]
    assert NEWER_CANONICAL_ID in capsys.readouterr().out


def test_invalid_discovery_arguments_exit_nonzero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["discover", "--latest", "--all"])

    assert exc_info.value.code != 0


def test_download_latest_downloads_fixture_pdf_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_cli_fixture_discovery(monkeypatch)
    calls = _patch_cli_downloader(monkeypatch, PDF_BYTES)
    output_dir = tmp_path / "raw"

    exit_code = main(["download", "--latest", "--output-dir", str(output_dir)])

    assert exit_code == 0
    assert calls
    assert (output_dir / "tsa-throughput-week-ending-2026-06-06.pdf").read_bytes() == PDF_BYTES


def test_download_from_installed_manifest_uses_manifest_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tsa_throughput.cli, "list_source_reports", lambda: [_report()])
    _patch_cli_downloader(monkeypatch, PDF_BYTES)
    output_dir = tmp_path / "raw"

    exit_code = main(
        ["download", "--from-installed-manifest", "--output-dir", str(output_dir)]
    )

    assert exit_code == 0
    assert (output_dir / (_report().canonical_filename or "")).read_bytes() == PDF_BYTES


def test_download_from_source_manifest_uses_manifest_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_manifest_path = tmp_path / "source_manifest.json"
    save_source_manifest(_source_manifest(), source_manifest_path)
    _patch_cli_downloader(monkeypatch, PDF_BYTES)
    output_dir = tmp_path / "raw"

    exit_code = main(
        [
            "download",
            "--from-source-manifest",
            str(source_manifest_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "tsa-throughput-week-ending-2026-06-13.pdf").read_bytes() == (
        PDF_BYTES
    )
    assert (output_dir / "tsa-throughput-week-ending-2026-06-06.pdf").read_bytes() == (
        PDF_BYTES
    )


def test_download_writes_pdf_files_under_output_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_cli_fixture_discovery(monkeypatch)
    _patch_cli_downloader(monkeypatch, PDF_BYTES)
    output_dir = tmp_path / "raw"

    exit_code = main(["download", "--latest", "--output-dir", str(output_dir)])

    assert exit_code == 0
    pdf_paths = list(output_dir.glob("*.pdf"))
    assert pdf_paths
    assert all(path.parent == output_dir for path in pdf_paths)


def test_download_creates_manifest_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_cli_fixture_discovery(monkeypatch)
    _patch_cli_downloader(monkeypatch, PDF_BYTES)
    output_dir = tmp_path / "raw"

    exit_code = main(["download", "--latest", "--output-dir", str(output_dir)])

    assert exit_code == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["reports"]


def test_download_output_includes_result_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_cli_fixture_discovery(monkeypatch)
    _patch_cli_downloader(monkeypatch, PDF_BYTES)
    output_dir = tmp_path / "raw"

    first_exit_code = main(["download", "--latest", "--output-dir", str(output_dir)])
    second_exit_code = main(["download", "--latest", "--output-dir", str(output_dir)])

    assert first_exit_code == 0
    assert second_exit_code == 0
    captured = capsys.readouterr()
    assert "downloaded" in captured.out
    assert "skipped_existing" in captured.out


def test_download_overwrite_redownloads_existing_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_cli_fixture_discovery(monkeypatch)
    output_dir = tmp_path / "raw"
    _patch_cli_downloader(monkeypatch, PDF_BYTES)

    first_exit_code = main(["download", "--latest", "--output-dir", str(output_dir)])
    _patch_cli_downloader(monkeypatch, UPDATED_PDF_BYTES)
    second_exit_code = main(
        ["download", "--latest", "--output-dir", str(output_dir), "--overwrite"]
    )

    assert first_exit_code == 0
    assert second_exit_code == 0
    assert (output_dir / "tsa-throughput-week-ending-2026-06-06.pdf").read_bytes() == (
        UPDATED_PDF_BYTES
    )


def test_download_missing_output_dir_exits_nonzero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["download", "--latest"])

    assert exc_info.value.code != 0


def test_manifest_refresh_command_exits_successfully_with_fixture_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_cli_manifest_refresh(monkeypatch)
    output_path = tmp_path / "source_manifest.json"

    exit_code = main(["manifest", "refresh", "--output", str(output_path)])

    assert exit_code == 0
    assert output_path.is_file()


def test_manifest_refresh_dry_run_does_not_write_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_cli_manifest_refresh(monkeypatch)
    output_path = tmp_path / "source_manifest.json"

    exit_code = main(
        ["manifest", "refresh", "--output", str(output_path), "--dry-run"]
    )

    assert exit_code == 0
    assert not output_path.exists()


def test_manifest_refresh_json_output_is_valid_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_cli_manifest_refresh(monkeypatch)
    output_path = tmp_path / "source_manifest.json"

    exit_code = main(
        [
            "manifest",
            "refresh",
            "--output",
            str(output_path),
            "--dry-run",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    manifest_json = json.loads(capsys.readouterr().out)
    assert manifest_json["reports"][0]["canonical_id"] == NEWER_CANONICAL_ID


def test_manifest_refresh_max_pages_is_passed_to_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    _patch_cli_manifest_refresh(monkeypatch, calls)
    output_path = tmp_path / "source_manifest.json"

    exit_code = main(
        ["manifest", "refresh", "--output", str(output_path), "--max-pages", "3"]
    )

    assert exit_code == 0
    assert calls[0]["max_pages"] == 3


def test_manifest_refresh_text_output_includes_concise_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_cli_manifest_refresh(monkeypatch)
    output_path = tmp_path / "source_manifest.json"

    exit_code = main(["manifest", "refresh", "--output", str(output_path)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "reports discovered: 2" in captured.out
    assert "reports normalized: 2" in captured.out
    assert "reports written: 2" in captured.out
    assert f"output path: {output_path}" in captured.out
    assert "non-clean date confidence: 1" in captured.out


def test_manifest_refresh_command_makes_no_live_network_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network calls are not allowed in CLI manifest tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket.socket, "connect", fail_network)
    _patch_cli_manifest_refresh(monkeypatch)

    exit_code = main(
        ["manifest", "refresh", "--output", str(tmp_path / "source_manifest.json")]
    )

    assert exit_code == 0


def test_discover_and_download_commands_make_no_live_network_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network calls are not allowed in CLI discovery/download tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket.socket, "connect", fail_network)
    _patch_cli_fixture_discovery(monkeypatch)
    _patch_cli_downloader(monkeypatch, PDF_BYTES)

    discover_exit_code = main(["discover", "--latest"])
    download_exit_code = main(
        ["download", "--latest", "--output-dir", str(tmp_path / "raw")]
    )

    assert discover_exit_code == 0
    assert download_exit_code == 0


def test_parse_command_writes_expected_csv(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "parsed.csv"

    exit_code = main(
        [
            "parse",
            str(FIXTURE_PDF),
            "--output",
            str(output_path),
            "--max-pages",
            "5",
        ]
    )

    assert exit_code == 0
    assert output_path.is_file()

    with output_path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert rows
    assert list(rows[0]) == CANONICAL_COLUMNS
    assert rows[0]["throughput_date"] == "2026-05-31"
    assert rows[0]["hour"] == "00:00"
    assert rows[0]["airport_code"] == "ANC"
    assert rows[0]["checkpoint_name"] == "South Checkpoint"
    assert rows[0]["throughput_count"] == "208"

    captured = capsys.readouterr()
    assert "Parsed " in captured.out
    assert str(output_path) in captured.out


def test_parse_command_accepts_parser_override(tmp_path: Path) -> None:
    output_path = tmp_path / "parsed.csv"

    exit_code = main(
        [
            "parse",
            str(FIXTURE_PDF),
            "--output",
            str(output_path),
            "--max-pages",
            "5",
            "--parser",
            PARSER_NAME,
        ]
    )

    assert exit_code == 0
    assert output_path.is_file()


def test_parse_command_unknown_parser_exits_nonzero(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "parsed.csv"

    exit_code = main(
        [
            "parse",
            str(FIXTURE_PDF),
            "--output",
            str(output_path),
            "--max-pages",
            "5",
            "--parser",
            "unknown_parser",
        ]
    )

    assert exit_code != 0
    assert not output_path.exists()
    captured = capsys.readouterr()
    assert "parser not found" in captured.err


def test_parse_command_missing_pdf_path_exits_nonzero(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "parsed.csv"

    exit_code = main(
        [
            "parse",
            str(tmp_path / "missing.pdf"),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code != 0
    assert not output_path.exists()
    captured = capsys.readouterr()
    assert "PDF path does not exist" in captured.err


def test_parse_command_creates_output_parent_directories(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "directory" / "parsed.csv"

    exit_code = main(
        [
            "parse",
            str(FIXTURE_PDF),
            "--output",
            str(output_path),
            "--max-pages",
            "5",
        ]
    )

    assert exit_code == 0
    assert output_path.is_file()


def test_parse_command_does_not_make_network_calls(tmp_path: Path, monkeypatch) -> None:
    output_path = tmp_path / "parsed.csv"

    def fail_network(*args, **kwargs):
        raise AssertionError("network calls are not allowed in CLI parse tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket.socket, "connect", fail_network)

    exit_code = main(
        [
            "parse",
            str(FIXTURE_PDF),
            "--output",
            str(output_path),
            "--max-pages",
            "5",
        ]
    )

    assert exit_code == 0
    assert output_path.is_file()


def test_parsers_list_command_exits_successfully(capsys) -> None:
    exit_code = main(["parsers", "list"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert PARSER_NAME in captured.out


def test_parsers_list_output_includes_modern_parser_metadata(capsys) -> None:
    exit_code = main(["parsers", "list"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert PARSER_NAME in captured.out
    assert HISTORICAL_PARSER_NAME in captured.out
    assert STRICT_HISTORICAL_PARSER_NAME in captured.out
    assert PMIS_PARSER_NAME in captured.out
    assert MARCH_2022_PARSER_NAME in captured.out
    assert "hourly_checkpoint_total_pax_kcm" in captured.out


def test_parsers_match_command_exits_successfully(capsys) -> None:
    exit_code = main(["parsers", "match", "--week-ending", "2026-06-06"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert PARSER_NAME in captured.out


def test_parsers_match_outside_coverage_exits_nonzero(capsys) -> None:
    exit_code = main(["parsers", "match", "--week-ending", "2022-02-26"])

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "no parser found" in captured.err


def test_parsers_match_selects_historical_parser(capsys) -> None:
    exit_code = main(["parsers", "match", "--week-ending", "2025-12-20"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert HISTORICAL_PARSER_NAME in captured.out


def test_parsers_match_selects_strict_historical_parser(capsys) -> None:
    exit_code = main(["parsers", "match", "--week-ending", "2022-12-31"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert STRICT_HISTORICAL_PARSER_NAME in captured.out


def test_parsers_match_selects_pmis_parser(capsys) -> None:
    exit_code = main(["parsers", "match", "--week-ending", "2022-04-02"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert PMIS_PARSER_NAME in captured.out


def test_parsers_match_selects_march_2022_parser(capsys) -> None:
    exit_code = main(["parsers", "match", "--week-ending", "2022-03-26"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert MARCH_2022_PARSER_NAME in captured.out


def test_parsers_match_with_pdf_path_exits_successfully(capsys) -> None:
    exit_code = main(
        [
            "parsers",
            "match",
            "--week-ending",
            "2026-06-06",
            "--pdf-path",
            str(FIXTURE_PDF),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert PARSER_NAME in captured.out


def test_parsers_match_missing_pdf_path_exits_nonzero(tmp_path: Path, capsys) -> None:
    exit_code = main(
        [
            "parsers",
            "match",
            "--week-ending",
            "2026-06-06",
            "--pdf-path",
            str(tmp_path / "missing.pdf"),
        ]
    )

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "PDF path does not exist" in captured.err


def test_debug_preserves_unexpected_traceback_behavior(monkeypatch) -> None:
    def fail_unexpected(args):
        raise RuntimeError("unexpected parser inspection failure")

    monkeypatch.setattr(tsa_throughput.cli, "_handle_parsers_list", fail_unexpected)

    with pytest.raises(RuntimeError, match="unexpected parser inspection failure"):
        main(["parsers", "list", "--debug"])


def test_parsers_commands_do_not_make_network_calls(monkeypatch, capsys) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network calls are not allowed in parser inspection tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket.socket, "connect", fail_network)

    list_exit_code = main(["parsers", "list"])
    match_exit_code = main(["parsers", "match", "--week-ending", "2026-06-06"])

    assert list_exit_code == 0
    assert match_exit_code == 0
    captured = capsys.readouterr()
    assert PARSER_NAME in captured.out


def _patch_cli_fixture_discovery(
    monkeypatch: pytest.MonkeyPatch,
    calls: list[str] | None = None,
) -> None:
    def fixture_discover_report_links(max_pages: int | None = None):
        return discover_report_links(
            fetch_html=_fixture_fetcher(calls=calls),
            max_pages=max_pages,
        )

    monkeypatch.setattr(
        tsa_throughput.cli,
        "discover_report_links",
        fixture_discover_report_links,
    )


def _patch_cli_downloader(
    monkeypatch: pytest.MonkeyPatch,
    content: bytes,
) -> list[str]:
    calls: list[str] = []

    def fixture_download_missing_reports(
        reports: list[ThroughputReport],
        storage: LocalStorage,
        manifest_path: Path | None = None,
        overwrite: bool = False,
    ):
        return download_missing_reports(
            reports,
            storage=storage,
            manifest_path=manifest_path,
            fetch_bytes=_fetcher(content, calls),
            overwrite=overwrite,
        )

    monkeypatch.setattr(
        tsa_throughput.cli,
        "download_missing_reports",
        fixture_download_missing_reports,
    )
    return calls


def _patch_cli_manifest_refresh(
    monkeypatch: pytest.MonkeyPatch,
    calls: list[dict[str, object]] | None = None,
) -> None:
    def fixture_refresh_source_manifest_with_result(
        output_path: Path | None = None,
        max_pages: int | None = None,
        fetch_html: Callable[[str], str] | None = None,
        dry_run: bool = False,
    ) -> SourceManifestRefreshResult:
        del fetch_html
        manifest = _source_manifest()
        manifest_path = Path(output_path) if output_path is not None else None
        if calls is not None:
            calls.append(
                {
                    "output_path": manifest_path,
                    "max_pages": max_pages,
                    "dry_run": dry_run,
                }
            )
        if manifest_path is not None and not dry_run:
            save_source_manifest(manifest, manifest_path)
        return SourceManifestRefreshResult(
            manifest=manifest,
            raw_report_count=2,
            normalized_report_count=len(manifest.reports),
            output_path=manifest_path,
            dry_run=dry_run,
        )

    monkeypatch.setattr(
        tsa_throughput.cli,
        "refresh_source_manifest_with_result",
        fixture_refresh_source_manifest_with_result,
    )


def _fixture_fetcher(calls: list[str] | None = None) -> Callable[[str], str]:
    pages = {
        PAGE_0_URL: (FIXTURES_DIR / "tsa_reading_room_page_0.html").read_text(encoding="utf-8"),
        PAGE_1_URL: (FIXTURES_DIR / "tsa_reading_room_page_1.html").read_text(encoding="utf-8"),
    }

    def fetch_html(url: str) -> str:
        if calls is not None:
            calls.append(url)
        return pages[url]

    return fetch_html


def _fetcher(content: bytes, calls: list[str] | None = None) -> Callable[[str], bytes]:
    def fetch(source_url: str) -> bytes:
        if calls is not None:
            calls.append(source_url)
        return content

    return fetch


def _source_manifest() -> SourceManifest:
    return SourceManifest(
        schema_version=1,
        generated_at="2026-06-08T00:00:00Z",
        source_name="TSA FOIA Reading Room",
        source_listing_url=PAGE_0_URL,
        reports=[
            _report(
                canonical_id=NEWER_CANONICAL_ID,
                week_start=date(2026, 6, 7),
                week_end=date(2026, 6, 13),
                canonical_filename="tsa-throughput-week-ending-2026-06-13.pdf",
                date_confidence="title_url_conflict",
            ),
            _report(),
        ],
    )


def _report(**overrides: object) -> ThroughputReport:
    data = {
        "canonical_id": MODERN_CANONICAL_ID,
        "week_start": date(2026, 5, 31),
        "week_end": date(2026, 6, 6),
        "title": "TSA Throughput Data to May 31, 2026 to June 6, 2026",
        "source_url": (
            "https://www.tsa.gov/sites/default/files/foia-readingroom/"
            "tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf"
        ),
        "source_filename": "tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf",
        "canonical_filename": "tsa-throughput-week-ending-2026-06-06.pdf",
        "date_confidence": "title_url_match",
        "listing_url": PAGE_0_URL,
        "alternate_urls": [],
    }
    data.update(overrides)
    return ThroughputReport(**data)
