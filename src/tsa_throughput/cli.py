"""Command-line entry points for tsa-throughput."""

from __future__ import annotations

import argparse
import csv
import sys
import traceback
from collections.abc import Sequence
from datetime import date, time
from pathlib import Path
from typing import Any

from tsa_throughput.exceptions import ParseError, TSAThroughputError
from tsa_throughput.models import ThroughputRecord, ThroughputReport
from tsa_throughput.parsing.registry import (
    ParserManifestEntry,
    get_parser,
    list_parsers,
    match_parser_manifest_entry,
)

CANONICAL_COLUMNS = [
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
    "week_start",
    "week_end",
    "source_file",
    "source_url",
    "source_page",
    "source_table",
    "parser_name",
    "parser_version",
    "parse_confidence",
]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the tsa-throughput command-line interface."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        return args.handler(args)
    except TSAThroughputError as exc:
        if getattr(args, "debug", False):
            traceback.print_exc()
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tsa-throughput")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser("parse", help="Parse a TSA throughput PDF to CSV.")
    parse_parser.add_argument("pdf_path", type=Path, help="Path to the source TSA PDF.")
    parse_parser.add_argument(
        "--output",
        "-o",
        required=True,
        type=Path,
        help="Path to write the parsed CSV.",
    )
    parse_parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit parsing to the first N pages.",
    )
    parse_parser.add_argument(
        "--parser",
        dest="parser_name",
        default=None,
        help="Override parser selection by parser name.",
    )
    parse_parser.add_argument(
        "--debug",
        action="store_true",
        help="Show tracebacks for package-specific errors.",
    )
    parse_parser.set_defaults(handler=_handle_parse)

    parsers_parser = subparsers.add_parser(
        "parsers",
        help="Inspect available parser plugins.",
    )
    parsers_subparsers = parsers_parser.add_subparsers(dest="parsers_command", required=True)

    parsers_list_parser = parsers_subparsers.add_parser(
        "list",
        help="List parser plugins from the installed manifest.",
    )
    parsers_list_parser.add_argument(
        "--debug",
        action="store_true",
        help="Show tracebacks for package-specific errors.",
    )
    parsers_list_parser.set_defaults(handler=_handle_parsers_list)

    parsers_match_parser = parsers_subparsers.add_parser(
        "match",
        help="Show which parser would match a report week ending date.",
    )
    parsers_match_parser.add_argument(
        "--week-ending",
        required=True,
        help="Report week ending date in YYYY-MM-DD format.",
    )
    parsers_match_parser.add_argument(
        "--pdf-path",
        type=Path,
        default=None,
        help="Optional PDF path to validate with parser can_parse() behavior.",
    )
    parsers_match_parser.add_argument(
        "--debug",
        action="store_true",
        help="Show tracebacks for package-specific errors.",
    )
    parsers_match_parser.set_defaults(handler=_handle_parsers_match)

    return parser


def _handle_parse(args: argparse.Namespace) -> int:
    pdf_path = Path(args.pdf_path)
    output_path = Path(args.output)

    if not pdf_path.is_file():
        raise ParseError(f"PDF path does not exist or is not a file: {pdf_path}")

    report = ThroughputReport(source_url="", original_filename=pdf_path.name)
    parser = get_parser(report, pdf_path, parser_name=args.parser_name)
    result = parser.parse(pdf_path, max_pages=args.max_pages, report=report)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CANONICAL_COLUMNS)
        writer.writeheader()
        writer.writerows(_record_to_row(record) for record in result.records)

    print(f"Parsed {result.record_count} records to {output_path}")
    return 0


def _handle_parsers_list(args: argparse.Namespace) -> int:
    del args

    entries = list_parsers()
    for index, entry in enumerate(entries):
        if index:
            print()
        _print_parser_entry(entry)

    return 0


def _handle_parsers_match(args: argparse.Namespace) -> int:
    week_end = _parse_iso_date(args.week_ending, field_name="week-ending")

    if args.pdf_path is None:
        entry = match_parser_manifest_entry(week_end)
    else:
        pdf_path = Path(args.pdf_path)
        if not pdf_path.is_file():
            raise ParseError(f"PDF path does not exist or is not a file: {pdf_path}")

        report = ThroughputReport(
            source_url="",
            week_end=week_end,
            original_filename=pdf_path.name,
        )
        selected_parser = get_parser(report, pdf_path)
        entry = _find_parser_entry(selected_parser.parser_name)

    print("Selected parser:")
    _print_parser_entry(entry)
    return 0


def _find_parser_entry(parser_name: str) -> ParserManifestEntry:
    for entry in list_parsers():
        if entry.name == parser_name:
            return entry
    raise ParseError(f"selected parser is missing from parser manifest: {parser_name}")


def _print_parser_entry(entry: ParserManifestEntry) -> None:
    print(entry.name)
    print(f"  layout_family: {_display_value(entry.layout_family)}")
    print(f"  valid_from: {_display_value(entry.valid_from)}")
    print(f"  valid_to: {_display_value(entry.valid_to)}")
    print(f"  priority: {entry.priority}")
    print(f"  description: {_display_value(entry.description)}")


def _parse_iso_date(value: str, *, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ParseError(f"{field_name} must be a valid YYYY-MM-DD date: {value}") from exc


def _display_value(value: object | None) -> str:
    if value is None:
        return "None"
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _record_to_row(record: ThroughputRecord) -> dict[str, str]:
    return {column: _csv_value(getattr(record, column)) for column in CANONICAL_COLUMNS}


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat(timespec="minutes")
    if isinstance(value, Path):
        return value.name
    return str(value)
