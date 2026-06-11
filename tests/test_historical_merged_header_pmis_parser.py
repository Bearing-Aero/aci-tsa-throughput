from datetime import date, time
from importlib import import_module
from pathlib import Path

import pytest

from tsa_throughput.exceptions import ParseError

merged_header_parser = import_module(
    "tsa_throughput.parsing.plugins.historical_merged_header_pmis_pdfplumber"
)
METRIC_NAME = merged_header_parser.METRIC_NAME
METRIC_SOURCE_COLUMN = merged_header_parser.METRIC_SOURCE_COLUMN
PARSER_NAME = merged_header_parser.PARSER_NAME
MergedHeaderPmisParser = merged_header_parser.HistoricalMergedHeaderPmisPdfplumberParser

FIXTURE_PDF = Path("tests/fixtures/tsa-throughput-week-ending-2018-06-30.pdf")


def test_historical_merged_header_pmis_parser_parses_fixture() -> None:
    parser = MergedHeaderPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    first_record = result.records[0]

    assert result.record_count > 0
    assert first_record.throughput_date == date(2018, 6, 24)
    assert first_record.hour == time(0, 0)
    assert first_record.airport_code == "ABQ"
    assert first_record.airport_name == "Albuquerque International Sunport"
    assert first_record.city == "Albuquerque"
    assert first_record.state == "NM"
    assert first_record.checkpoint_name == "Checkpoint for A/B Gates"
    assert first_record.throughput_count == 1
    assert first_record.metric_name == METRIC_NAME
    assert first_record.metric_source_column == METRIC_SOURCE_COLUMN
    assert first_record.parser_name == PARSER_NAME


def test_historical_merged_header_pmis_parser_carries_context_across_pages() -> None:
    parser = MergedHeaderPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    sfo_checkpoint_b = next(
        record
        for record in result.records
        if record.airport_code == "SFO"
        and record.checkpoint_name == "Security Checkpoint B"
    )

    assert sfo_checkpoint_b.throughput_date == date(2018, 6, 24)
    assert sfo_checkpoint_b.hour == time(0, 0)
    assert sfo_checkpoint_b.airport_name == "San Francisco International"
    assert sfo_checkpoint_b.city == "San Francisco"
    assert sfo_checkpoint_b.state == "CA"
    assert sfo_checkpoint_b.throughput_count == 89
    assert sfo_checkpoint_b.source_page == 2


def test_historical_merged_header_pmis_parser_updates_hour_context() -> None:
    parser = MergedHeaderPmisParser()

    result = parser.parse(FIXTURE_PDF, max_pages=3)
    ord_checkpoint = next(
        record
        for record in reversed(result.records)
        if record.airport_code == "ORD" and record.checkpoint_name == "4B"
    )

    assert ord_checkpoint.throughput_date == date(2018, 6, 24)
    assert ord_checkpoint.hour == time(1, 0)
    assert ord_checkpoint.airport_name == "Chicago-OHare International"
    assert ord_checkpoint.city == "Chicago"
    assert ord_checkpoint.state == "IL"
    assert ord_checkpoint.throughput_count == 27


def test_historical_merged_header_pmis_parser_rejects_clean_pmis_header() -> None:
    parser = MergedHeaderPmisParser()
    table = [
        [
            "Date",
            "Hour of Day",
            "Airport",
            None,
            "City",
            "State",
            "Checkpoint",
            "Metrics",
            "PMIS - Total Customer Throughput (Unadjusted)",
        ],
        [
            "6/24/2018",
            "00:00",
            "ABQ",
            "Albuquerque International Sunport",
            "Albuquerque",
            "NM",
            "Checkpoint for A/B Gates",
            None,
            "1",
        ],
    ]

    with pytest.raises(ParseError, match="clean PMIS header found"):
        parser._data_rows_from_table(
            table,
            source_file=Path("bad.pdf"),
            source_page=1,
            source_table=1,
        )
