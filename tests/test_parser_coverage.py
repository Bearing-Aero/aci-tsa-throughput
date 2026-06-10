import json
import shutil
import socket
from datetime import date
from importlib import import_module
from pathlib import Path

import pytest

import tsa_throughput.parsing.coverage
from tsa_throughput.cli import main
from tsa_throughput.exceptions import ParseError, ParserNotFoundError
from tsa_throughput.manifest import save_runtime_manifest
from tsa_throughput.models import (
    ParseResult,
    RuntimeManifest,
    RuntimeManifestEntry,
    ThroughputReport,
)
from tsa_throughput.parsing.coverage import (
    STATUS_METADATA_MISSING,
    STATUS_NO_MATCHING_PARSER,
    STATUS_PARSE_ERROR,
    STATUS_PARSED,
    scan_parser_coverage,
)
from tsa_throughput.parsing.plugins.historical_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    PARSER_NAME as HISTORICAL_PARSER_NAME,
)
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    PARSER_NAME as MODERN_PARSER_NAME,
)

STRICT_HISTORICAL_PARSER_NAME = import_module(
    "tsa_throughput.parsing.plugins."
    "historical_total_pax_kcm_hourly_checkpoint_strict_pdfplumber"
).PARSER_NAME
PMIS_PARSER_NAME = import_module(
    "tsa_throughput.parsing.plugins."
    "historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber"
).PARSER_NAME
LEGACY_PMIS_PARSER_NAME = import_module(
    "tsa_throughput.parsing.plugins.historical_legacy_pmis_split_year_dates_pdfplumber"
).PARSER_NAME
MARCH_2022_PARSER_NAME = import_module(
    "tsa_throughput.parsing.plugins."
    "historical_march_2022_total_pax_kcm_hourly_checkpoint_pdfplumber"
).PARSER_NAME

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf")
HISTORICAL_MODERN_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2025-12-27.pdf"
)
HISTORICAL_TOTAL_PAX_KCM_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2025-12-20.pdf"
)
HISTORICAL_TOTAL_PAX_KCM_BOUNDARY_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2023-01-07.pdf"
)
STRICT_HISTORICAL_TOTAL_PAX_KCM_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2022-12-31.pdf"
)
STRICT_HISTORICAL_TOTAL_PAX_KCM_BOUNDARY_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2022-04-09.pdf"
)
PMIS_FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2022-04-02.pdf")
PMIS_EARLY_BOUNDARY_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2022-02-26.pdf"
)
PMIS_START_BOUNDARY_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2022-01-08.pdf"
)
LEGACY_PMIS_FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2022-01-01.pdf")
LEGACY_PMIS_START_BOUNDARY_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2018-07-07.pdf"
)
MARCH_2022_FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2022-03-26.pdf")
MARCH_2022_BOUNDARY_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2022-03-05.pdf"
)


def test_coverage_scan_finds_pdf_files_under_input_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_coverage_parser(monkeypatch)
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-06-06.pdf")
    (input_dir / "notes.txt").write_text("ignore me", encoding="utf-8")

    result = scan_parser_coverage(input_dir)

    assert result.scanned_count == 1
    assert calls[0]["source_file"].name == "tsa-throughput-week-ending-2026-06-06.pdf"


def test_coverage_scan_honors_pattern(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_coverage_parser(monkeypatch)
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-06-06.pdf")
    _write_pdf(input_dir / "other-week-ending-2026-05-30.pdf")

    result = scan_parser_coverage(input_dir, pattern="tsa-throughput-*.pdf")

    assert result.scanned_count == 1
    assert result.results[0].week_end == date(2026, 6, 6)


def test_coverage_scan_sorts_files_reverse_chronologically_by_week_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_coverage_parser(monkeypatch)
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-05-23.pdf")
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-06-06.pdf")
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-05-30.pdf")

    result = scan_parser_coverage(input_dir)

    assert [item.week_end for item in result.results] == [
        date(2026, 6, 6),
        date(2026, 5, 30),
        date(2026, 5, 23),
    ]


def test_coverage_scan_uses_runtime_manifest_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_coverage_parser(monkeypatch)
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    pdf_name = "manifest-name.pdf"
    _write_pdf(input_dir / pdf_name)
    save_runtime_manifest(
        RuntimeManifest(
            schema_version=1,
            updated_at="2026-06-08T00:00:00Z",
            reports=[
                _manifest_entry(
                    canonical_id="manifest-canonical-id",
                    week_end=date(2026, 6, 6),
                    local_path=pdf_name,
                    canonical_filename="tsa-throughput-week-ending-2026-06-06.pdf",
                    source_url="https://example.test/manifest.pdf",
                )
            ],
        ),
        input_dir / "manifest.json",
    )

    result = scan_parser_coverage(input_dir)

    assert result.results[0].canonical_id == "manifest-canonical-id"
    assert result.results[0].week_end == date(2026, 6, 6)
    assert calls[0]["report"].source_url == "https://example.test/manifest.pdf"


def test_coverage_scan_inferrs_metadata_from_canonical_filename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_coverage_parser(monkeypatch)
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-05-30.pdf")

    result = scan_parser_coverage(input_dir)

    assert result.results[0].canonical_id == "tsa-throughput-week-ending-2026-05-30"
    assert result.results[0].week_end == date(2026, 5, 30)
    assert calls[0]["report"].date_confidence == "filename_only"


def test_coverage_scan_marks_missing_metadata_without_crashing(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    _write_pdf(input_dir / "unknown-layout.pdf")

    result = scan_parser_coverage(input_dir)

    assert result.scanned_count == 1
    assert result.skipped_count == 1
    assert result.results[0].status == STATUS_METADATA_MISSING


def test_coverage_scan_records_success_parser_name_and_record_count(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    shutil.copyfile(
        FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2026-06-06.pdf",
    )

    result = scan_parser_coverage(input_dir, max_pages=5)

    assert result.success_count == 1
    assert result.results[0].status == STATUS_PARSED
    assert result.results[0].parser_name == MODERN_PARSER_NAME
    assert result.results[0].record_count


def test_coverage_scan_extends_through_verified_2025_boundary(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    shutil.copyfile(
        FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2026-06-06.pdf",
    )
    shutil.copyfile(
        HISTORICAL_MODERN_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2025-12-27.pdf",
    )

    result = scan_parser_coverage(input_dir, max_pages=3, stop_on_first_error=True)

    assert result.success_count == 2
    assert result.failure_count == 0
    assert result.earliest_success_week_end == date(2025, 12, 27)
    assert [item.parser_name for item in result.results] == [
        MODERN_PARSER_NAME,
        MODERN_PARSER_NAME,
    ]


def test_coverage_scan_extends_through_historical_total_pax_kcm_boundary(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    shutil.copyfile(
        FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2026-06-06.pdf",
    )
    shutil.copyfile(
        HISTORICAL_MODERN_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2025-12-27.pdf",
    )
    shutil.copyfile(
        HISTORICAL_TOTAL_PAX_KCM_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2025-12-20.pdf",
    )
    shutil.copyfile(
        HISTORICAL_TOTAL_PAX_KCM_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2023-01-07.pdf",
    )

    result = scan_parser_coverage(input_dir, max_pages=3, stop_on_first_error=True)

    assert result.success_count == 4
    assert result.failure_count == 0
    assert result.earliest_success_week_end == date(2023, 1, 7)
    assert [item.parser_name for item in result.results] == [
        MODERN_PARSER_NAME,
        MODERN_PARSER_NAME,
        HISTORICAL_PARSER_NAME,
        HISTORICAL_PARSER_NAME,
    ]


def test_coverage_scan_extends_through_strict_historical_total_pax_kcm_boundary(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    shutil.copyfile(
        FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2026-06-06.pdf",
    )
    shutil.copyfile(
        HISTORICAL_MODERN_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2025-12-27.pdf",
    )
    shutil.copyfile(
        HISTORICAL_TOTAL_PAX_KCM_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2025-12-20.pdf",
    )
    shutil.copyfile(
        HISTORICAL_TOTAL_PAX_KCM_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2023-01-07.pdf",
    )
    shutil.copyfile(
        STRICT_HISTORICAL_TOTAL_PAX_KCM_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-12-31.pdf",
    )
    shutil.copyfile(
        STRICT_HISTORICAL_TOTAL_PAX_KCM_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-04-09.pdf",
    )

    result = scan_parser_coverage(input_dir, max_pages=3, stop_on_first_error=True)

    assert result.success_count == 6
    assert result.failure_count == 0
    assert result.earliest_success_week_end == date(2022, 4, 9)
    assert [item.parser_name for item in result.results] == [
        MODERN_PARSER_NAME,
        MODERN_PARSER_NAME,
        HISTORICAL_PARSER_NAME,
        HISTORICAL_PARSER_NAME,
        STRICT_HISTORICAL_PARSER_NAME,
        STRICT_HISTORICAL_PARSER_NAME,
    ]


def test_coverage_scan_extends_through_historical_pmis_boundary(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    shutil.copyfile(
        FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2026-06-06.pdf",
    )
    shutil.copyfile(
        HISTORICAL_MODERN_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2025-12-27.pdf",
    )
    shutil.copyfile(
        HISTORICAL_TOTAL_PAX_KCM_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2025-12-20.pdf",
    )
    shutil.copyfile(
        HISTORICAL_TOTAL_PAX_KCM_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2023-01-07.pdf",
    )
    shutil.copyfile(
        STRICT_HISTORICAL_TOTAL_PAX_KCM_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-12-31.pdf",
    )
    shutil.copyfile(
        STRICT_HISTORICAL_TOTAL_PAX_KCM_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-04-09.pdf",
    )
    shutil.copyfile(
        PMIS_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-04-02.pdf",
    )

    result = scan_parser_coverage(input_dir, max_pages=3, stop_on_first_error=True)

    assert result.success_count == 7
    assert result.failure_count == 0
    assert result.earliest_success_week_end == date(2022, 4, 2)
    assert [item.parser_name for item in result.results] == [
        MODERN_PARSER_NAME,
        MODERN_PARSER_NAME,
        HISTORICAL_PARSER_NAME,
        HISTORICAL_PARSER_NAME,
        STRICT_HISTORICAL_PARSER_NAME,
        STRICT_HISTORICAL_PARSER_NAME,
        PMIS_PARSER_NAME,
    ]


def test_coverage_scan_extends_through_march_2022_historical_boundary(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    shutil.copyfile(
        FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2026-06-06.pdf",
    )
    shutil.copyfile(
        HISTORICAL_MODERN_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2025-12-27.pdf",
    )
    shutil.copyfile(
        HISTORICAL_TOTAL_PAX_KCM_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2025-12-20.pdf",
    )
    shutil.copyfile(
        HISTORICAL_TOTAL_PAX_KCM_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2023-01-07.pdf",
    )
    shutil.copyfile(
        STRICT_HISTORICAL_TOTAL_PAX_KCM_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-12-31.pdf",
    )
    shutil.copyfile(
        STRICT_HISTORICAL_TOTAL_PAX_KCM_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-04-09.pdf",
    )
    shutil.copyfile(
        PMIS_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-04-02.pdf",
    )
    shutil.copyfile(
        MARCH_2022_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-03-26.pdf",
    )
    shutil.copyfile(
        MARCH_2022_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-03-05.pdf",
    )

    result = scan_parser_coverage(input_dir, max_pages=3, stop_on_first_error=True)

    assert result.success_count == 9
    assert result.failure_count == 0
    assert result.earliest_success_week_end == date(2022, 3, 5)
    assert [item.parser_name for item in result.results] == [
        MODERN_PARSER_NAME,
        MODERN_PARSER_NAME,
        HISTORICAL_PARSER_NAME,
        HISTORICAL_PARSER_NAME,
        STRICT_HISTORICAL_PARSER_NAME,
        STRICT_HISTORICAL_PARSER_NAME,
        PMIS_PARSER_NAME,
        MARCH_2022_PARSER_NAME,
        MARCH_2022_PARSER_NAME,
    ]


def test_coverage_scan_extends_through_early_historical_pmis_boundary(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    shutil.copyfile(
        FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2026-06-06.pdf",
    )
    shutil.copyfile(
        HISTORICAL_MODERN_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2025-12-27.pdf",
    )
    shutil.copyfile(
        HISTORICAL_TOTAL_PAX_KCM_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2025-12-20.pdf",
    )
    shutil.copyfile(
        HISTORICAL_TOTAL_PAX_KCM_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2023-01-07.pdf",
    )
    shutil.copyfile(
        STRICT_HISTORICAL_TOTAL_PAX_KCM_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-12-31.pdf",
    )
    shutil.copyfile(
        STRICT_HISTORICAL_TOTAL_PAX_KCM_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-04-09.pdf",
    )
    shutil.copyfile(
        PMIS_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-04-02.pdf",
    )
    shutil.copyfile(
        MARCH_2022_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-03-26.pdf",
    )
    shutil.copyfile(
        MARCH_2022_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-03-05.pdf",
    )
    shutil.copyfile(
        PMIS_EARLY_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-02-26.pdf",
    )
    shutil.copyfile(
        PMIS_START_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-01-08.pdf",
    )

    result = scan_parser_coverage(input_dir, max_pages=3, stop_on_first_error=True)

    assert result.success_count == 11
    assert result.failure_count == 0
    assert result.earliest_success_week_end == date(2022, 1, 8)
    assert [item.parser_name for item in result.results] == [
        MODERN_PARSER_NAME,
        MODERN_PARSER_NAME,
        HISTORICAL_PARSER_NAME,
        HISTORICAL_PARSER_NAME,
        STRICT_HISTORICAL_PARSER_NAME,
        STRICT_HISTORICAL_PARSER_NAME,
        PMIS_PARSER_NAME,
        MARCH_2022_PARSER_NAME,
        MARCH_2022_PARSER_NAME,
        PMIS_PARSER_NAME,
        PMIS_PARSER_NAME,
    ]


def test_coverage_scan_extends_through_legacy_pmis_boundary(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    shutil.copyfile(
        FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2026-06-06.pdf",
    )
    shutil.copyfile(
        HISTORICAL_MODERN_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2025-12-27.pdf",
    )
    shutil.copyfile(
        HISTORICAL_TOTAL_PAX_KCM_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2025-12-20.pdf",
    )
    shutil.copyfile(
        HISTORICAL_TOTAL_PAX_KCM_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2023-01-07.pdf",
    )
    shutil.copyfile(
        STRICT_HISTORICAL_TOTAL_PAX_KCM_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-12-31.pdf",
    )
    shutil.copyfile(
        STRICT_HISTORICAL_TOTAL_PAX_KCM_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-04-09.pdf",
    )
    shutil.copyfile(
        PMIS_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-04-02.pdf",
    )
    shutil.copyfile(
        MARCH_2022_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-03-26.pdf",
    )
    shutil.copyfile(
        MARCH_2022_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-03-05.pdf",
    )
    shutil.copyfile(
        PMIS_EARLY_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-02-26.pdf",
    )
    shutil.copyfile(
        PMIS_START_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-01-08.pdf",
    )
    shutil.copyfile(
        LEGACY_PMIS_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2022-01-01.pdf",
    )
    shutil.copyfile(
        LEGACY_PMIS_START_BOUNDARY_FIXTURE_PDF,
        input_dir / "tsa-throughput-week-ending-2018-07-07.pdf",
    )

    result = scan_parser_coverage(input_dir, max_pages=3, stop_on_first_error=True)

    assert result.success_count == 13
    assert result.failure_count == 0
    assert result.earliest_success_week_end == date(2018, 7, 7)
    assert [item.parser_name for item in result.results] == [
        MODERN_PARSER_NAME,
        MODERN_PARSER_NAME,
        HISTORICAL_PARSER_NAME,
        HISTORICAL_PARSER_NAME,
        STRICT_HISTORICAL_PARSER_NAME,
        STRICT_HISTORICAL_PARSER_NAME,
        PMIS_PARSER_NAME,
        MARCH_2022_PARSER_NAME,
        MARCH_2022_PARSER_NAME,
        PMIS_PARSER_NAME,
        PMIS_PARSER_NAME,
        LEGACY_PMIS_PARSER_NAME,
        LEGACY_PMIS_PARSER_NAME,
    ]


def test_coverage_scan_records_parser_registry_miss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_parser(report: ThroughputReport, pdf_path: Path):
        raise ParserNotFoundError("no parser found for report")

    monkeypatch.setattr(tsa_throughput.parsing.coverage, "get_parser", no_parser)
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    _write_pdf(input_dir / "tsa-throughput-week-ending-2025-12-27.pdf")

    result = scan_parser_coverage(input_dir)

    assert result.failure_count == 1
    assert result.results[0].status == STATUS_NO_MATCHING_PARSER
    assert result.results[0].error_type == "ParserNotFoundError"


def test_coverage_scan_records_parser_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_coverage_parser(monkeypatch, fail_week_ends={date(2026, 5, 16)})
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-05-16.pdf")

    result = scan_parser_coverage(input_dir)

    assert result.failure_count == 1
    assert result.results[0].status == STATUS_PARSE_ERROR
    assert result.results[0].parser_name == "fake_parser"


def test_coverage_scan_stop_on_first_error_stops_after_first_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_coverage_parser(monkeypatch, fail_week_ends={date(2026, 5, 30)})
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-06-06.pdf")
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-05-30.pdf")
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-05-23.pdf")

    result = scan_parser_coverage(input_dir, stop_on_first_error=True)

    assert [item.path.name for item in result.results] == [
        "tsa-throughput-week-ending-2026-06-06.pdf",
        "tsa-throughput-week-ending-2026-05-30.pdf",
    ]


def test_coverage_scan_continues_after_failures_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_coverage_parser(monkeypatch, fail_week_ends={date(2026, 5, 30)})
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-06-06.pdf")
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-05-30.pdf")
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-05-23.pdf")

    result = scan_parser_coverage(input_dir)

    assert result.scanned_count == 3
    assert [item.week_end for item in result.results] == [
        date(2026, 6, 6),
        date(2026, 5, 30),
        date(2026, 5, 23),
    ]


def test_coverage_summary_identifies_success_range_and_first_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_coverage_parser(monkeypatch, fail_week_ends={date(2026, 5, 16)})
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-06-06.pdf")
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-05-23.pdf")
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-05-16.pdf")

    result = scan_parser_coverage(input_dir)

    assert result.latest_success_week_end == date(2026, 6, 6)
    assert result.earliest_success_week_end == date(2026, 5, 23)
    assert result.first_failure_week_end == date(2026, 5, 16)
    assert result.first_failure_path
    assert result.first_failure_path.name == "tsa-throughput-week-ending-2026-05-16.pdf"


def test_coverage_cli_text_output_includes_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_coverage_parser(monkeypatch, fail_week_ends={date(2026, 5, 16)})
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-06-06.pdf")
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-05-23.pdf")
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-05-16.pdf")

    exit_code = main(["parsers", "coverage", "--input-dir", str(input_dir)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Parser coverage boundary:" in captured.out
    assert "earliest successful week ending: 2026-05-23" in captured.out
    assert "first failure week ending: 2026-05-16" in captured.out
    assert "failure reason: parse error" in captured.out


def test_coverage_cli_json_output_is_valid_json_with_per_file_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_coverage_parser(monkeypatch)
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-06-06.pdf")

    exit_code = main(
        [
            "parsers",
            "coverage",
            "--input-dir",
            str(input_dir),
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["success_count"] == 1
    assert payload["results"][0]["status"] == STATUS_PARSED


def test_coverage_cli_passes_max_pages_to_parser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_coverage_parser(monkeypatch)
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-06-06.pdf")

    exit_code = main(
        [
            "parsers",
            "coverage",
            "--input-dir",
            str(input_dir),
            "--max-pages",
            "3",
        ]
    )

    assert exit_code == 0
    assert calls[0]["max_pages"] == 3


def test_coverage_scan_makes_no_network_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network calls are not allowed in parser coverage tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket.socket, "connect", fail_network)
    _patch_coverage_parser(monkeypatch)
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    _write_pdf(input_dir / "tsa-throughput-week-ending-2026-06-06.pdf")

    result = scan_parser_coverage(input_dir)

    assert result.success_count == 1


def _write_pdf(path: Path) -> None:
    path.write_bytes(b"%PDF-1.7\nfixture\n%%EOF\n")


def _patch_coverage_parser(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail_week_ends: set[date] | None = None,
) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []
    fail_week_ends = fail_week_ends or set()

    def fake_get_parser(report: ThroughputReport, pdf_path: Path):
        return _FakeCoverageParser(calls, fail_week_ends)

    monkeypatch.setattr(tsa_throughput.parsing.coverage, "get_parser", fake_get_parser)
    return calls


class _FakeCoverageParser:
    parser_name = "fake_parser"
    parser_version = "test"

    def __init__(
        self,
        calls: list[dict[str, object]],
        fail_week_ends: set[date],
    ) -> None:
        self.calls = calls
        self.fail_week_ends = fail_week_ends

    def parse(
        self,
        source_file: Path,
        *,
        max_pages: int | None = None,
        report: ThroughputReport | None = None,
    ) -> ParseResult:
        source_file = Path(source_file)
        self.calls.append(
            {
                "source_file": source_file,
                "max_pages": max_pages,
                "report": report,
            }
        )
        if report is not None and report.week_end in self.fail_week_ends:
            raise ParseError("synthetic parser failure")

        return ParseResult(
            source_file=source_file,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            records=[],
            record_count=2,
            week_start=report.week_start if report else None,
            week_end=report.week_end if report else None,
        )


def _manifest_entry(**overrides: object) -> RuntimeManifestEntry:
    week_end = overrides.pop("week_end", date(2026, 6, 6))
    week_start = week_end - (date(2026, 6, 6) - date(2026, 5, 31))
    data = {
        "canonical_id": "tsa-throughput-week-ending-2026-06-06",
        "week_start": week_start,
        "week_end": week_end,
        "source_url": "https://example.test/source.pdf",
        "source_filename": "source.pdf",
        "canonical_filename": "tsa-throughput-week-ending-2026-06-06.pdf",
        "local_path": "tsa-throughput-week-ending-2026-06-06.pdf",
        "sha256": "abc123",
        "bytes": 123,
        "downloaded_at": "2026-06-08T00:00:00Z",
        "date_confidence": "title_url_match",
    }
    data.update(overrides)
    return RuntimeManifestEntry(**data)
