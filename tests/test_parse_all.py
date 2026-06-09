import csv
import shutil
import socket
from datetime import date, time
from pathlib import Path

import pytest

import tsa_throughput.parsing.batch
from tsa_throughput.cli import CANONICAL_COLUMNS, main
from tsa_throughput.exceptions import ParseError
from tsa_throughput.manifest import save_runtime_manifest
from tsa_throughput.models import (
    ParseResult,
    RuntimeManifest,
    RuntimeManifestEntry,
    ThroughputRecord,
)
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    PARSER_NAME,
)

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf")


def test_parse_all_parses_one_fixture_pdf_successfully(tmp_path: Path) -> None:
    input_dir = _input_dir_with_fixture(tmp_path)
    output_path = tmp_path / "parsed" / "throughput.csv"

    exit_code = main(
        [
            "parse-all",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output_path),
            "--max-pages",
            "5",
        ]
    )

    assert exit_code == 0


def test_parse_all_creates_output_csv_with_canonical_columns_and_first_record(
    tmp_path: Path,
) -> None:
    input_dir = _input_dir_with_fixture(tmp_path)
    output_path = tmp_path / "parsed" / "throughput.csv"

    exit_code = main(
        [
            "parse-all",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output_path),
            "--max-pages",
            "5",
        ]
    )

    assert exit_code == 0
    assert output_path.is_file()

    rows = _read_csv(output_path)
    assert rows
    assert list(rows[0]) == CANONICAL_COLUMNS
    assert rows[0]["throughput_date"] == "2026-05-31"
    assert rows[0]["hour"] == "00:00"
    assert rows[0]["airport_code"] == "ANC"
    assert rows[0]["checkpoint_name"] == "South Checkpoint"
    assert rows[0]["throughput_count"] == "208"


def test_parse_all_creates_output_parent_directories(tmp_path: Path) -> None:
    input_dir = _input_dir_with_fixture(tmp_path)
    output_path = tmp_path / "nested" / "parsed" / "throughput.csv"

    exit_code = main(
        [
            "parse-all",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output_path),
            "--max-pages",
            "5",
        ]
    )

    assert exit_code == 0
    assert output_path.is_file()


def test_parse_all_pattern_is_honored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_fake_parser(monkeypatch)
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    (input_dir / "a.pdf").write_bytes(b"%PDF-1.7\n%%EOF\n")
    (input_dir / "b.txt").write_text("not a pdf", encoding="utf-8")
    (input_dir / "c.PDF").write_bytes(b"%PDF-1.7\n%%EOF\n")
    output_path = tmp_path / "parsed.csv"

    exit_code = main(
        [
            "parse-all",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output_path),
            "--pattern",
            "*.pdf",
        ]
    )

    assert exit_code == 0
    assert [call["source_file"].name for call in calls] == ["a.pdf"]


def test_parse_all_processes_files_in_deterministic_filename_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_fake_parser(monkeypatch)
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    (input_dir / "b.pdf").write_bytes(b"%PDF-1.7\n%%EOF\n")
    (input_dir / "a.pdf").write_bytes(b"%PDF-1.7\n%%EOF\n")
    output_path = tmp_path / "parsed.csv"

    exit_code = main(
        [
            "parse-all",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    rows = _read_csv(output_path)
    assert [row["source_file"] for row in rows] == ["a.pdf", "b.pdf"]


def test_parse_all_passes_max_pages_to_parser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_fake_parser(monkeypatch)
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    (input_dir / "report.pdf").write_bytes(b"%PDF-1.7\n%%EOF\n")
    output_path = tmp_path / "parsed.csv"

    exit_code = main(
        [
            "parse-all",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output_path),
            "--max-pages",
            "5",
        ]
    )

    assert exit_code == 0
    assert calls[0]["max_pages"] == 5


def test_parse_all_accepts_parser_override(tmp_path: Path) -> None:
    input_dir = _input_dir_with_fixture(tmp_path)
    output_path = tmp_path / "parsed.csv"

    exit_code = main(
        [
            "parse-all",
            "--input-dir",
            str(input_dir),
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


def test_parse_all_missing_input_dir_argument_exits_nonzero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["parse-all", "--output", "parsed.csv"])

    assert exc_info.value.code != 0


def test_parse_all_nonexistent_input_directory_exits_nonzero(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "parse-all",
            "--input-dir",
            str(tmp_path / "missing"),
            "--output",
            str(tmp_path / "parsed.csv"),
        ]
    )

    assert exit_code != 0
    assert "input directory does not exist" in capsys.readouterr().err


def test_parse_all_no_matching_pdfs_exits_nonzero(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()

    exit_code = main(
        [
            "parse-all",
            "--input-dir",
            str(input_dir),
            "--output",
            str(tmp_path / "parsed.csv"),
        ]
    )

    assert exit_code != 0
    assert "no PDF files found" in capsys.readouterr().err


def test_parse_all_parser_failure_exits_nonzero_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_fake_parser(monkeypatch)
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    (input_dir / "bad.pdf").write_bytes(b"%PDF-1.7\n%%EOF\n")

    exit_code = main(
        [
            "parse-all",
            "--input-dir",
            str(input_dir),
            "--output",
            str(tmp_path / "parsed.csv"),
        ]
    )

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "Failed: 1" in captured.out
    assert "synthetic parser failure" in captured.err


def test_parse_all_continue_on_error_continues_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = _patch_fake_parser(monkeypatch)
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    (input_dir / "a-good.pdf").write_bytes(b"%PDF-1.7\n%%EOF\n")
    (input_dir / "b-bad.pdf").write_bytes(b"%PDF-1.7\n%%EOF\n")
    (input_dir / "c-good.pdf").write_bytes(b"%PDF-1.7\n%%EOF\n")
    output_path = tmp_path / "parsed.csv"

    exit_code = main(
        [
            "parse-all",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output_path),
            "--continue-on-error",
        ]
    )

    assert exit_code == 0
    assert [call["source_file"].name for call in calls] == [
        "a-good.pdf",
        "b-bad.pdf",
        "c-good.pdf",
    ]
    assert len(_read_csv(output_path)) == 2
    captured = capsys.readouterr()
    assert "Parsed successfully: 2" in captured.out
    assert "Failed: 1" in captured.out


def test_parse_all_uses_runtime_manifest_metadata(tmp_path: Path) -> None:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    pdf_name = "tsa-throughput-week-ending-2026-06-06.pdf"
    shutil.copyfile(FIXTURE_PDF, input_dir / pdf_name)
    save_runtime_manifest(
        RuntimeManifest(
            schema_version=1,
            updated_at="2026-06-08T00:00:00Z",
            reports=[
                _manifest_entry(
                    source_url="https://example.test/from-manifest.pdf",
                    local_path=pdf_name,
                    canonical_filename=pdf_name,
                )
            ],
        ),
        input_dir / "manifest.json",
    )
    output_path = tmp_path / "parsed.csv"

    exit_code = main(
        [
            "parse-all",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output_path),
            "--max-pages",
            "5",
        ]
    )

    assert exit_code == 0
    first_row = _read_csv(output_path)[0]
    assert first_row["week_start"] == "2026-05-31"
    assert first_row["week_end"] == "2026-06-06"
    assert first_row["source_url"] == "https://example.test/from-manifest.pdf"


def test_parse_all_without_runtime_manifest_still_parses_known_modern_fixture(
    tmp_path: Path,
) -> None:
    input_dir = _input_dir_with_fixture(tmp_path)
    output_path = tmp_path / "parsed.csv"

    exit_code = main(
        [
            "parse-all",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output_path),
            "--max-pages",
            "5",
        ]
    )

    assert exit_code == 0
    assert _read_csv(output_path)


def test_parse_all_makes_no_network_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = _input_dir_with_fixture(tmp_path)
    output_path = tmp_path / "parsed.csv"

    def fail_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network calls are not allowed in parse-all")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket.socket, "connect", fail_network)

    exit_code = main(
        [
            "parse-all",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output_path),
            "--max-pages",
            "5",
        ]
    )

    assert exit_code == 0


def _input_dir_with_fixture(tmp_path: Path) -> Path:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    shutil.copyfile(FIXTURE_PDF, input_dir / FIXTURE_PDF.name)
    return input_dir


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def _patch_fake_parser(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def fake_get_parser(report, pdf_path, parser_name=None):
        calls.append(
            {
                "report": report,
                "source_file": Path(pdf_path),
                "parser_name": parser_name,
                "max_pages": None,
            }
        )
        return _FakeParser(calls[-1])

    monkeypatch.setattr(tsa_throughput.parsing.batch, "get_parser", fake_get_parser)
    return calls


class _FakeParser:
    parser_name = "fake_parser"
    parser_version = "test"

    def __init__(self, call: dict[str, object]) -> None:
        self.call = call

    def parse(self, source_file, *, max_pages=None, report=None):
        self.call["max_pages"] = max_pages
        source_file = Path(source_file)

        if "bad" in source_file.name:
            raise ParseError(f"synthetic parser failure for {source_file.name}")

        record = ThroughputRecord(
            throughput_date=date(2026, 5, 31),
            hour=time(0, 0),
            airport_code=source_file.stem.upper()[:3],
            airport_name="Test Airport",
            city="Test City",
            state="TS",
            checkpoint_name="Test Checkpoint",
            metric_name="test_metric",
            metric_source_column="Test Metric",
            throughput_count=1,
            week_start=report.week_start if report else None,
            week_end=report.week_end if report else None,
            source_file=source_file,
            source_url=report.source_url if report else None,
            source_page=1,
            source_table=1,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            parse_confidence="test",
        )
        return ParseResult(
            source_file=source_file,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            records=[record],
            record_count=1,
        )


def _manifest_entry(**overrides: object) -> RuntimeManifestEntry:
    data = {
        "canonical_id": "tsa-throughput-week-ending-2026-06-06",
        "week_start": date(2026, 5, 31),
        "week_end": date(2026, 6, 6),
        "source_url": (
            "https://www.tsa.gov/sites/default/files/foia-readingroom/"
            "tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf"
        ),
        "source_filename": "tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf",
        "canonical_filename": "tsa-throughput-week-ending-2026-06-06.pdf",
        "local_path": "tsa-throughput-week-ending-2026-06-06.pdf",
        "sha256": "abc123",
        "bytes": 123456,
        "downloaded_at": "2026-06-08T00:00:00Z",
        "date_confidence": "title_url_match",
    }
    data.update(overrides)
    return RuntimeManifestEntry(**data)
