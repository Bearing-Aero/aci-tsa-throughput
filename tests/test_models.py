from datetime import date, time
from pathlib import Path

from tsa_throughput.models import (
    DownloadResult,
    ParseResult,
    RawReportLink,
    ThroughputRecord,
    ThroughputReport,
)


def test_raw_report_link_can_be_instantiated() -> None:
    link = RawReportLink(
        title="TSA Throughput Data to May 31, 2026 to June 6, 2026",
        url="https://www.tsa.gov/example.pdf",
        source_page_url="https://www.tsa.gov/foia/readingroom?page=0",
        source_page=0,
    )

    assert link.title.startswith("TSA Throughput")
    assert link.source_page == 0


def test_throughput_report_can_be_instantiated() -> None:
    report = ThroughputReport(
        source_url="https://www.tsa.gov/example.pdf",
        week_start=date(2026, 5, 31),
        week_end=date(2026, 6, 6),
        report_id="tsa-throughput-week-ending-2026-06-06",
        title="TSA Throughput Data to May 31, 2026 to June 6, 2026",
        original_filename="tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf",
        canonical_filename="tsa-throughput-week-ending-2026-06-06.pdf",
        date_confidence="high",
    )

    assert report.week_end == date(2026, 6, 6)
    assert report.alternate_urls == []


def test_download_result_can_be_instantiated() -> None:
    report = ThroughputReport(source_url="https://www.tsa.gov/example.pdf")
    result = DownloadResult(
        report=report,
        status="downloaded",
        path=Path("data/raw/tsa-throughput-week-ending-2026-06-06.pdf"),
        sha256="abc123",
        size_bytes=123,
    )

    assert result.status == "downloaded"
    assert result.path == Path("data/raw/tsa-throughput-week-ending-2026-06-06.pdf")


def test_throughput_record_can_be_instantiated() -> None:
    record = ThroughputRecord(
        throughput_date=date(2026, 5, 31),
        hour=time(0, 0),
        airport_code="ANC",
        airport_name="Ted Stevens Anchorage International",
        city="Anchorage",
        state="AK",
        checkpoint_name="South Checkpoint",
        metric_name="total_pax_plus_kcm_pax",
        metric_source_column="Total Pax + KCM PAX",
        throughput_count=208,
        week_start=date(2026, 5, 31),
        week_end=date(2026, 6, 6),
        source_file=Path("tsa-throughput-week-ending-2026-06-06.pdf"),
        source_url="https://www.tsa.gov/example.pdf",
        source_page=1,
        source_table=1,
        parser_name="modern_total_pax_kcm_hourly_checkpoint_pdfplumber",
        parser_version="0.1.0",
        parse_confidence="high",
    )

    assert record.hour == time(0, 0)
    assert record.throughput_count == 208


def test_parse_result_can_be_instantiated() -> None:
    record = ThroughputRecord(
        throughput_date=date(2026, 5, 31),
        airport_code="ANC",
        throughput_count=208,
        source_file=Path("tsa-throughput-week-ending-2026-06-06.pdf"),
        parser_name="modern_total_pax_kcm_hourly_checkpoint_pdfplumber",
        parser_version="0.1.0",
    )
    result = ParseResult(
        source_file=Path("tsa-throughput-week-ending-2026-06-06.pdf"),
        parser_name="modern_total_pax_kcm_hourly_checkpoint_pdfplumber",
        parser_version="0.1.0",
        records=[record],
        record_count=1,
        week_start=date(2026, 5, 31),
        week_end=date(2026, 6, 6),
    )

    assert result.record_count == 1
    assert result.records == [record]
