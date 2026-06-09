import csv
import socket
from pathlib import Path

from tsa_throughput.cli import CANONICAL_COLUMNS, main
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    PARSER_NAME,
)

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf")


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
