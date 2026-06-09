#!/usr/bin/env python3
"""
Prototype parser for modern TSA throughput PDFs.

This is intended as a spike for the first tsa_throughput parser plugin.
It targets the recent layout with columns:

Date
Hour of Day
Airport
[airport name blank header]
City
State
Checkpoint
Total Pax + KCM PAX

Usage:
    python parse_modern_tsa_pdf.py tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf \
        --output parsed_tsa_throughput.csv \
        --max-pages 10

Use --max-pages 0 to parse the full PDF.
"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pdfplumber

TABLE_SETTINGS: dict[str, Any] = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "intersection_tolerance": 3,
}


@dataclass(frozen=True)
class ThroughputRecord:
    throughput_date: date
    hour: time
    airport_code: str
    airport_name: str | None
    city: str | None
    state: str | None
    checkpoint_name: str
    metric_name: str
    metric_source_column: str
    throughput_count: int
    source_file: str
    source_page: int
    source_table: int
    parser_name: str
    parser_version: str
    parse_confidence: str


def clean_cell(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).replace("\n", " ")
    text = " ".join(text.split()).strip()
    return text or None


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%m/%d/%Y").date()


def parse_hour(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def parse_int(value: str) -> int:
    return int(value.replace(",", "").strip())


def looks_like_header(row: list[str | None]) -> bool:
    normalized = [cell.lower() if cell else "" for cell in row]

    return (
        "date" in normalized[0]
        and "hour" in normalized[1]
        and "airport" in normalized[2]
        and "city" in normalized[4]
        and "state" in normalized[5]
        and "checkpoint" in normalized[6]
        and "total pax" in normalized[7]
    )


def parse_table(
    table: list[list[Any]],
    *,
    source_file: str,
    source_page: int,
    source_table: int,
) -> list[ThroughputRecord]:
    records: list[ThroughputRecord] = []

    current_date: date | None = None
    current_hour: time | None = None
    current_airport_code: str | None = None
    current_airport_name: str | None = None
    current_city: str | None = None
    current_state: str | None = None

    if not table:
        return records

    cleaned_rows = [[clean_cell(cell) for cell in row] for row in table]

    header = cleaned_rows[0]
    if len(header) < 8 or not looks_like_header(header):
        raise ValueError(
            f"Unexpected table header on page {source_page}, table {source_table}: {header}"
        )

    metric_source_column = header[7] or "Total Pax + KCM PAX"
    metric_name = "total_pax_plus_kcm_pax"

    for row_index, row in enumerate(cleaned_rows[1:], start=2):
        if len(row) < 8:
            continue

        raw_date = row[0]
        raw_hour = row[1]
        raw_airport_code = row[2]
        raw_airport_name = row[3]
        raw_city = row[4]
        raw_state = row[5]
        raw_checkpoint = row[6]
        raw_count = row[7]

        if raw_date:
            current_date = parse_date(raw_date)

        if raw_hour:
            current_hour = parse_hour(raw_hour)

        if raw_airport_code:
            current_airport_code = raw_airport_code.upper()
            current_airport_name = raw_airport_name
            current_city = raw_city
            current_state = raw_state.upper() if raw_state else None

        if not raw_checkpoint and not raw_count:
            continue

        if current_date is None:
            raise ValueError(
                f"Missing date context on page {source_page}, table {source_table}, row {row_index}"
            )

        if current_hour is None:
            raise ValueError(
                f"Missing hour context on page {source_page}, table {source_table}, row {row_index}"
            )

        if current_airport_code is None:
            raise ValueError(
                f"Missing airport context on page {source_page}, table {source_table}, "
                f"row {row_index}"
            )

        if not raw_checkpoint:
            raise ValueError(
                f"Missing checkpoint on page {source_page}, table {source_table}, row {row_index}"
            )

        if raw_count is None:
            raise ValueError(
                f"Missing throughput count on page {source_page}, table {source_table}, "
                f"row {row_index}"
            )

        if not re.fullmatch(r"[\d,]+", raw_count):
            raise ValueError(
                f"Invalid throughput count {raw_count!r} on page {source_page}, "
                f"table {source_table}, row {row_index}"
            )

        records.append(
            ThroughputRecord(
                throughput_date=current_date,
                hour=current_hour,
                airport_code=current_airport_code,
                airport_name=current_airport_name,
                city=current_city,
                state=current_state,
                checkpoint_name=raw_checkpoint,
                metric_name=metric_name,
                metric_source_column=metric_source_column,
                throughput_count=parse_int(raw_count),
                source_file=source_file,
                source_page=source_page,
                source_table=source_table,
                parser_name="modern_total_pax_kcm_hourly_checkpoint_pdfplumber",
                parser_version="0.1.0",
                parse_confidence="high",
            )
        )

    return records


def parse_pdf(pdf_path: Path, max_pages: int | None = None) -> list[ThroughputRecord]:
    all_records: list[ThroughputRecord] = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        pages_to_process = total_pages if max_pages is None else min(total_pages, max_pages)

        for page_index in range(pages_to_process):
            page = pdf.pages[page_index]
            source_page = page_index + 1

            tables = page.extract_tables(table_settings=TABLE_SETTINGS)

            if not tables:
                raise ValueError(f"No tables found on page {source_page}")

            main_tables = [
                table
                for table in tables
                if table
                and len(table) > 1
                and len(table[0]) >= 8
                and looks_like_header([clean_cell(cell) for cell in table[0]])
            ]

            if not main_tables:
                raise ValueError(f"No matching throughput table found on page {source_page}")

            for table_index, table in enumerate(main_tables, start=1):
                records = parse_table(
                    table,
                    source_file=pdf_path.name,
                    source_page=source_page,
                    source_table=table_index,
                )
                all_records.extend(records)

            if source_page % 25 == 0:
                print(f"Parsed page {source_page:,}/{total_pages:,}...")

    return all_records


def write_csv(records: list[ThroughputRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(asdict(records[0]).keys()) if records else [
        "throughput_date",
        "hour",
        "airport_code",
        "airport_name",
        "city",
        "state",
        "checkpoint_name",
        "metric_name",
        "metric_source_column",
        "throughput_count",
        "source_file",
        "source_page",
        "source_table",
        "parser_name",
        "parser_version",
        "parse_confidence",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for record in records:
            row = asdict(record)
            row["throughput_date"] = record.throughput_date.isoformat()
            row["hour"] = record.hour.strftime("%H:%M")
            writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prototype parser for modern TSA throughput PDFs."
    )
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("parsed_tsa_throughput.csv"),
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Maximum pages to parse. Use 0 or negative to parse all pages.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.pdf_path.exists():
        raise SystemExit(f"PDF not found: {args.pdf_path}")

    max_pages = None if args.max_pages <= 0 else args.max_pages

    records = parse_pdf(args.pdf_path, max_pages=max_pages)
    write_csv(records, args.output)

    print(f"Records parsed: {len(records):,}")
    print(f"Output written: {args.output}")


if __name__ == "__main__":
    main()
