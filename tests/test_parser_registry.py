import json
from datetime import date
from pathlib import Path
from typing import ClassVar

import pytest

from tsa_throughput.exceptions import ParserNotFoundError
from tsa_throughput.models import ParseResult, ThroughputReport
from tsa_throughput.parsing.base import ThroughputParser
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    PARSER_NAME,
    ModernTotalPaxKcmHourlyCheckpointPdfplumberParser,
)
from tsa_throughput.parsing.registry import (
    ParserManifestEntry,
    get_parser,
    list_parsers,
    load_parser_manifest,
)

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf")


class LowPriorityTestParser(ThroughputParser):
    parser_name = "low_priority_test_parser"
    parser_version = "0.1.0"
    layout_family = "test"

    def can_parse(self, report: ThroughputReport, pdf_path: Path) -> bool:
        return True

    def parse(
        self,
        source_file: Path,
        *,
        max_pages: int | None = None,
        report: ThroughputReport | None = None,
    ) -> ParseResult:
        raise NotImplementedError


class HighPriorityTestParser(ThroughputParser):
    parser_name = "high_priority_test_parser"
    parser_version = "0.1.0"
    layout_family = "test"

    def can_parse(self, report: ThroughputReport, pdf_path: Path) -> bool:
        return True

    def parse(
        self,
        source_file: Path,
        *,
        max_pages: int | None = None,
        report: ThroughputReport | None = None,
    ) -> ParseResult:
        raise NotImplementedError


class CannotParseTestParser(ThroughputParser):
    parser_name = "cannot_parse_test_parser"
    parser_version = "0.1.0"
    layout_family = "test"

    calls: ClassVar[int] = 0

    def can_parse(self, report: ThroughputReport, pdf_path: Path) -> bool:
        type(self).calls += 1
        return False

    def parse(
        self,
        source_file: Path,
        *,
        max_pages: int | None = None,
        report: ThroughputReport | None = None,
    ) -> ParseResult:
        raise NotImplementedError


class RecordingTestParser(ThroughputParser):
    parser_name = "recording_test_parser"
    parser_version = "0.1.0"
    layout_family = "test"

    calls: ClassVar[int] = 0

    def can_parse(self, report: ThroughputReport, pdf_path: Path) -> bool:
        type(self).calls += 1
        return True

    def parse(
        self,
        source_file: Path,
        *,
        max_pages: int | None = None,
        report: ThroughputReport | None = None,
    ) -> ParseResult:
        raise NotImplementedError


def test_parser_manifest_loads_successfully() -> None:
    manifest = load_parser_manifest()

    assert manifest["schema_version"] == 1
    assert isinstance(manifest["parsers"], list)


def test_parser_manifest_contains_modern_parser_entry() -> None:
    manifest = load_parser_manifest()

    parser_names = {entry["name"] for entry in manifest["parsers"]}

    assert PARSER_NAME in parser_names


def test_list_parsers_returns_modern_parser_metadata() -> None:
    parsers = list_parsers()
    modern_parser = next(entry for entry in parsers if entry.name == PARSER_NAME)

    assert isinstance(modern_parser, ParserManifestEntry)
    assert modern_parser.module.endswith("modern_total_pax_kcm_hourly_checkpoint_pdfplumber")
    assert modern_parser.class_name == "ModernTotalPaxKcmHourlyCheckpointPdfplumberParser"
    assert modern_parser.valid_from == date(2026, 1, 1)
    assert modern_parser.valid_to is None
    assert modern_parser.priority == 100
    assert modern_parser.layout_family == "hourly_checkpoint_total_pax_kcm"


def test_get_parser_selects_modern_parser_for_matching_week_end() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2026, 6, 6),
    )

    parser = get_parser(report, FIXTURE_PDF)

    assert isinstance(parser, ModernTotalPaxKcmHourlyCheckpointPdfplumberParser)


def test_get_parser_supports_exact_parser_override_by_name() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2026, 6, 6),
    )

    parser = get_parser(report, FIXTURE_PDF, parser_name=PARSER_NAME)

    assert parser.parser_name == PARSER_NAME


def test_get_parser_raises_for_unknown_parser_override() -> None:
    report = ThroughputReport(source_url="https://www.tsa.gov/example.pdf")

    with pytest.raises(ParserNotFoundError, match="parser not found"):
        get_parser(report, FIXTURE_PDF, parser_name="unknown_parser")


def test_get_parser_raises_when_no_parser_date_range_matches() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2025, 12, 31),
    )

    with pytest.raises(ParserNotFoundError, match="no parser found"):
        get_parser(report, FIXTURE_PDF)


def test_parser_priority_is_respected_with_test_manifest(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        [
            _parser_entry("low_priority_test_parser", "LowPriorityTestParser", priority=10),
            _parser_entry("high_priority_test_parser", "HighPriorityTestParser", priority=100),
        ],
    )
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2026, 6, 6),
    )

    parser = get_parser(report, Path("fake.pdf"), manifest_path=manifest_path)

    assert isinstance(parser, HighPriorityTestParser)


def test_can_parse_is_called_before_parser_is_returned(tmp_path: Path) -> None:
    CannotParseTestParser.calls = 0
    RecordingTestParser.calls = 0
    manifest_path = _write_manifest(
        tmp_path,
        [
            _parser_entry("cannot_parse_test_parser", "CannotParseTestParser", priority=100),
            _parser_entry("recording_test_parser", "RecordingTestParser", priority=10),
        ],
    )
    report = ThroughputReport(source_url="https://www.tsa.gov/example.pdf")

    parser = get_parser(report, Path("fake.pdf"), manifest_path=manifest_path)

    assert isinstance(parser, RecordingTestParser)
    assert CannotParseTestParser.calls == 1
    assert RecordingTestParser.calls == 1


def test_list_parsers_works_with_temporary_manifest_path(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        [_parser_entry("recording_test_parser", "RecordingTestParser", priority=42)],
    )

    parsers = list_parsers(manifest_path)

    assert len(parsers) == 1
    assert parsers[0].name == "recording_test_parser"
    assert parsers[0].priority == 42


def _write_manifest(tmp_path: Path, parser_entries: list[dict[str, object]]) -> Path:
    manifest_path = tmp_path / "parser_manifest.json"
    manifest_path.write_text(
        json.dumps({"schema_version": 1, "parsers": parser_entries}),
        encoding="utf-8",
    )
    return manifest_path


def _parser_entry(name: str, class_name: str, priority: int) -> dict[str, object]:
    return {
        "name": name,
        "module": __name__,
        "class": class_name,
        "valid_from": "2026-01-01",
        "valid_to": None,
        "priority": priority,
        "layout_family": "test",
        "description": "Test parser.",
    }
