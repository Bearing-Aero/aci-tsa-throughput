import json
from datetime import date
from importlib import import_module
from pathlib import Path
from typing import ClassVar

import pytest

from tsa_throughput.exceptions import ParserNotFoundError
from tsa_throughput.models import ParseResult, ThroughputReport
from tsa_throughput.parsing.base import ThroughputParser
from tsa_throughput.parsing.plugins.historical_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    PARSER_NAME as HISTORICAL_PARSER_NAME,
)
from tsa_throughput.parsing.plugins.historical_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    HistoricalTotalPaxKcmHourlyCheckpointPdfplumberParser,
)
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    PARSER_NAME as MODERN_PARSER_NAME,
)
from tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber import (
    ModernTotalPaxKcmHourlyCheckpointPdfplumberParser,
)
from tsa_throughput.parsing.registry import (
    ParserManifestEntry,
    get_parser,
    list_parsers,
    load_parser_manifest,
)

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf")
HISTORICAL_FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2025-12-20.pdf")
STRICT_HISTORICAL_FIXTURE_PDF = Path(
    "tests/fixtures/tsa-throughput-week-ending-2022-12-31.pdf"
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
strict_parser = import_module(
    "tsa_throughput.parsing.plugins."
    "historical_total_pax_kcm_hourly_checkpoint_strict_pdfplumber"
)
STRICT_HISTORICAL_PARSER_NAME = strict_parser.PARSER_NAME
StrictHistoricalParser = (
    strict_parser.HistoricalTotalPaxKcmHourlyCheckpointStrictPdfplumberParser
)
pmis_parser = import_module(
    "tsa_throughput.parsing.plugins."
    "historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber"
)
PMIS_PARSER_NAME = pmis_parser.PARSER_NAME
PmisParser = (
    pmis_parser.HistoricalPmisTotalCustomerThroughputHourlyCheckpointPdfplumberParser
)
legacy_pmis_parser = import_module(
    "tsa_throughput.parsing.plugins.historical_legacy_pmis_split_year_dates_pdfplumber"
)
LEGACY_PMIS_PARSER_NAME = legacy_pmis_parser.PARSER_NAME
LegacyPmisParser = legacy_pmis_parser.HistoricalLegacyPmisSplitYearDatesPdfplumberParser
march_2022_parser = import_module(
    "tsa_throughput.parsing.plugins."
    "historical_march_2022_total_pax_kcm_hourly_checkpoint_pdfplumber"
)
MARCH_2022_PARSER_NAME = march_2022_parser.PARSER_NAME
March2022Parser = (
    march_2022_parser.HistoricalMarch2022TotalPaxKcmHourlyCheckpointPdfplumberParser
)


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


def test_parser_manifest_contains_registered_parser_entries() -> None:
    manifest = load_parser_manifest()

    parser_names = {entry["name"] for entry in manifest["parsers"]}

    assert MODERN_PARSER_NAME in parser_names
    assert HISTORICAL_PARSER_NAME in parser_names
    assert STRICT_HISTORICAL_PARSER_NAME in parser_names
    assert PMIS_PARSER_NAME in parser_names
    assert LEGACY_PMIS_PARSER_NAME in parser_names
    assert MARCH_2022_PARSER_NAME in parser_names


def test_list_parsers_returns_modern_parser_metadata() -> None:
    parsers = list_parsers()
    modern_parser = next(entry for entry in parsers if entry.name == MODERN_PARSER_NAME)

    assert isinstance(modern_parser, ParserManifestEntry)
    assert modern_parser.module.endswith("modern_total_pax_kcm_hourly_checkpoint_pdfplumber")
    assert modern_parser.class_name == "ModernTotalPaxKcmHourlyCheckpointPdfplumberParser"
    assert modern_parser.valid_from == date(2025, 12, 27)
    assert modern_parser.valid_to is None
    assert modern_parser.priority == 100
    assert modern_parser.layout_family == "hourly_checkpoint_total_pax_kcm"


def test_list_parsers_returns_historical_parser_metadata() -> None:
    parsers = list_parsers()
    historical_parser = next(
        entry for entry in parsers if entry.name == HISTORICAL_PARSER_NAME
    )

    assert isinstance(historical_parser, ParserManifestEntry)
    assert historical_parser.module.endswith(
        "historical_total_pax_kcm_hourly_checkpoint_pdfplumber"
    )
    assert historical_parser.class_name == (
        "HistoricalTotalPaxKcmHourlyCheckpointPdfplumberParser"
    )
    assert historical_parser.valid_from == date(2023, 1, 7)
    assert historical_parser.valid_to == date(2025, 12, 20)
    assert historical_parser.priority == 90
    assert historical_parser.layout_family == "hourly_checkpoint_total_pax_kcm"


def test_list_parsers_returns_strict_historical_parser_metadata() -> None:
    parsers = list_parsers()
    strict_parser = next(
        entry for entry in parsers if entry.name == STRICT_HISTORICAL_PARSER_NAME
    )

    assert isinstance(strict_parser, ParserManifestEntry)
    assert strict_parser.module.endswith(
        "historical_total_pax_kcm_hourly_checkpoint_strict_pdfplumber"
    )
    assert strict_parser.class_name == (
        "HistoricalTotalPaxKcmHourlyCheckpointStrictPdfplumberParser"
    )
    assert strict_parser.valid_from == date(2022, 4, 9)
    assert strict_parser.valid_to == date(2022, 12, 31)
    assert strict_parser.priority == 90
    assert strict_parser.layout_family == "hourly_checkpoint_total_pax_kcm_strict_lines"


def test_list_parsers_returns_pmis_parser_metadata() -> None:
    parsers = list_parsers()
    pmis_parsers = [entry for entry in parsers if entry.name == PMIS_PARSER_NAME]
    pmis_parser = pmis_parsers[0]

    assert len(pmis_parsers) == 2
    assert isinstance(pmis_parser, ParserManifestEntry)
    assert pmis_parser.module.endswith(
        "historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber"
    )
    assert pmis_parser.class_name == (
        "HistoricalPmisTotalCustomerThroughputHourlyCheckpointPdfplumberParser"
    )
    assert pmis_parser.valid_from == date(2022, 1, 8)
    assert pmis_parser.valid_to == date(2022, 2, 26)
    assert pmis_parser.priority == 90
    assert pmis_parser.layout_family == "hourly_checkpoint_pmis_total_customer_throughput"
    assert pmis_parsers[1].valid_from == date(2022, 4, 2)
    assert pmis_parsers[1].valid_to == date(2022, 4, 2)


def test_list_parsers_returns_legacy_pmis_parser_metadata() -> None:
    parsers = list_parsers()
    legacy_pmis_parser = next(
        entry for entry in parsers if entry.name == LEGACY_PMIS_PARSER_NAME
    )

    assert isinstance(legacy_pmis_parser, ParserManifestEntry)
    assert legacy_pmis_parser.module.endswith(
        "historical_legacy_pmis_split_year_dates_pdfplumber"
    )
    assert legacy_pmis_parser.class_name == (
        "HistoricalLegacyPmisSplitYearDatesPdfplumberParser"
    )
    assert legacy_pmis_parser.valid_from == date(2018, 7, 7)
    assert legacy_pmis_parser.valid_to == date(2022, 1, 1)
    assert legacy_pmis_parser.priority == 90
    assert legacy_pmis_parser.layout_family == (
        "hourly_checkpoint_pmis_total_customer_throughput_split_year_dates"
    )


def test_list_parsers_returns_march_2022_parser_metadata() -> None:
    parsers = list_parsers()
    march_2022_parser = next(
        entry for entry in parsers if entry.name == MARCH_2022_PARSER_NAME
    )

    assert isinstance(march_2022_parser, ParserManifestEntry)
    assert march_2022_parser.module.endswith(
        "historical_march_2022_total_pax_kcm_hourly_checkpoint_pdfplumber"
    )
    assert march_2022_parser.class_name == (
        "HistoricalMarch2022TotalPaxKcmHourlyCheckpointPdfplumberParser"
    )
    assert march_2022_parser.valid_from == date(2022, 3, 5)
    assert march_2022_parser.valid_to == date(2022, 3, 26)
    assert march_2022_parser.priority == 90
    assert march_2022_parser.layout_family == (
        "hourly_checkpoint_total_pax_kcm_march_2022"
    )


def test_get_parser_selects_modern_parser_for_matching_week_end() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2026, 6, 6),
    )

    parser = get_parser(report, FIXTURE_PDF)

    assert isinstance(parser, ModernTotalPaxKcmHourlyCheckpointPdfplumberParser)


def test_get_parser_selects_modern_parser_for_verified_2025_boundary() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2025, 12, 27),
    )

    parser = get_parser(report, FIXTURE_PDF)

    assert isinstance(parser, ModernTotalPaxKcmHourlyCheckpointPdfplumberParser)


def test_get_parser_supports_exact_parser_override_by_name() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2026, 6, 6),
    )

    parser = get_parser(report, FIXTURE_PDF, parser_name=MODERN_PARSER_NAME)

    assert parser.parser_name == MODERN_PARSER_NAME


def test_get_parser_selects_historical_parser_for_matching_week_end() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2025, 12, 20),
    )

    parser = get_parser(report, HISTORICAL_FIXTURE_PDF)

    assert isinstance(parser, HistoricalTotalPaxKcmHourlyCheckpointPdfplumberParser)


def test_get_parser_selects_historical_parser_for_start_boundary() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2023, 1, 7),
    )

    parser = get_parser(report, HISTORICAL_FIXTURE_PDF)

    assert isinstance(parser, HistoricalTotalPaxKcmHourlyCheckpointPdfplumberParser)


def test_get_parser_selects_strict_historical_parser_for_matching_week_end() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2022, 12, 31),
    )

    parser = get_parser(report, STRICT_HISTORICAL_FIXTURE_PDF)

    assert isinstance(parser, StrictHistoricalParser)


def test_get_parser_selects_strict_historical_parser_for_start_boundary() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2022, 4, 9),
    )

    parser = get_parser(report, STRICT_HISTORICAL_FIXTURE_PDF)

    assert isinstance(parser, StrictHistoricalParser)


def test_get_parser_selects_pmis_parser_for_matching_week_end() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2022, 4, 2),
    )

    parser = get_parser(report, PMIS_FIXTURE_PDF)

    assert isinstance(parser, PmisParser)


def test_get_parser_selects_pmis_parser_for_early_boundary() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2022, 2, 26),
    )

    parser = get_parser(report, PMIS_EARLY_BOUNDARY_FIXTURE_PDF)

    assert isinstance(parser, PmisParser)


def test_get_parser_selects_pmis_parser_for_start_boundary() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2022, 1, 8),
    )

    parser = get_parser(report, PMIS_START_BOUNDARY_FIXTURE_PDF)

    assert isinstance(parser, PmisParser)


def test_get_parser_selects_legacy_pmis_parser_for_matching_week_end() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2022, 1, 1),
    )

    parser = get_parser(report, LEGACY_PMIS_FIXTURE_PDF)

    assert isinstance(parser, LegacyPmisParser)


def test_get_parser_selects_legacy_pmis_parser_for_start_boundary() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2018, 7, 7),
    )

    parser = get_parser(report, LEGACY_PMIS_START_BOUNDARY_FIXTURE_PDF)

    assert isinstance(parser, LegacyPmisParser)


def test_get_parser_selects_march_2022_parser_for_matching_week_end() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2022, 3, 26),
    )

    parser = get_parser(report, MARCH_2022_FIXTURE_PDF)

    assert isinstance(parser, March2022Parser)


def test_get_parser_selects_march_2022_parser_for_start_boundary() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2022, 3, 5),
    )

    parser = get_parser(report, MARCH_2022_BOUNDARY_FIXTURE_PDF)

    assert isinstance(parser, March2022Parser)


def test_get_parser_raises_for_unknown_parser_override() -> None:
    report = ThroughputReport(source_url="https://www.tsa.gov/example.pdf")

    with pytest.raises(ParserNotFoundError, match="parser not found"):
        get_parser(report, FIXTURE_PDF, parser_name="unknown_parser")


def test_get_parser_raises_when_no_parser_date_range_matches() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_end=date(2018, 6, 30),
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
