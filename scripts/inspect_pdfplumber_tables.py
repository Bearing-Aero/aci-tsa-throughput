#!/usr/bin/env python3
"""
Inspect TSA throughput PDF structure with pdfplumber.

Purpose:
    Diagnostic script for designing the first tsa_throughput parser plugin.
    This does not attempt to produce final clean records. It inspects how
    pdfplumber sees the PDF: text, tables, rows, columns, and extraction
    behavior under different table settings.

Usage:
    python scripts/inspect_pdfplumber_tables.py path/to/report.pdf

Example:
    python scripts/inspect_pdfplumber_tables.py tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import pdfplumber


TABLE_SETTINGS_PRESETS: dict[str, dict[str, Any]] = {
    "default": {},
    "lines": {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 3,
        "join_tolerance": 3,
        "intersection_tolerance": 3,
    },
    "lines_strict": {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 1,
        "join_tolerance": 1,
        "intersection_tolerance": 1,
    },
    "text": {
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
        "snap_tolerance": 3,
        "join_tolerance": 3,
        "intersection_tolerance": 3,
        "min_words_vertical": 3,
        "min_words_horizontal": 1,
    },
    "mixed_vertical_lines_horizontal_text": {
        "vertical_strategy": "lines",
        "horizontal_strategy": "text",
        "snap_tolerance": 3,
        "join_tolerance": 3,
        "intersection_tolerance": 3,
        "min_words_horizontal": 1,
    },
}


def clean_cell(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value)
    text = text.replace("\n", " ")
    text = " ".join(text.split())
    return text or None


def clean_row(row: list[Any]) -> list[str | None]:
    return [clean_cell(cell) for cell in row]


def write_csv(path: Path, rows: list[list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow([clean_cell(cell) or "" for cell in row])


def summarize_table(table: list[list[Any]], max_rows: int = 12) -> dict[str, Any]:
    cleaned = [clean_row(row) for row in table]

    row_lengths = [len(row) for row in cleaned]
    non_empty_counts = [
        sum(1 for cell in row if cell not in (None, ""))
        for row in cleaned
    ]

    return {
        "row_count": len(cleaned),
        "min_columns": min(row_lengths) if row_lengths else 0,
        "max_columns": max(row_lengths) if row_lengths else 0,
        "row_lengths_sample": row_lengths[:max_rows],
        "non_empty_counts_sample": non_empty_counts[:max_rows],
        "first_rows": cleaned[:max_rows],
    }


def inspect_pdf(pdf_path: Path, output_dir: Path, max_pages: int | None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "pdf_path": str(pdf_path),
        "pages": [],
        "table_settings_presets": list(TABLE_SETTINGS_PRESETS.keys()),
    }

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        pages_to_process = total_pages if max_pages is None else min(total_pages, max_pages)

        summary["total_pages"] = total_pages
        summary["pages_processed"] = pages_to_process

        print(f"Opened: {pdf_path}")
        print(f"Total pages: {total_pages}")
        print(f"Pages processed: {pages_to_process}")
        print()

        for page_index in range(pages_to_process):
            page = pdf.pages[page_index]
            page_number = page_index + 1

            print("=" * 80)
            print(f"PAGE {page_number}")
            print("=" * 80)
            print(f"Width: {page.width}, Height: {page.height}")
            print(f"Chars: {len(page.chars)}")
            print(f"Lines: {len(page.lines)}")
            print(f"Rects: {len(page.rects)}")
            print(f"Curves: {len(page.curves)}")
            print()

            page_summary: dict[str, Any] = {
                "page_number": page_number,
                "width": page.width,
                "height": page.height,
                "char_count": len(page.chars),
                "line_count": len(page.lines),
                "rect_count": len(page.rects),
                "curve_count": len(page.curves),
                "text_preview_path": None,
                "presets": {},
            }

            text = page.extract_text() or ""
            text_preview_path = output_dir / f"page_{page_number:03d}_text.txt"
            text_preview_path.write_text(text, encoding="utf-8")
            page_summary["text_preview_path"] = str(text_preview_path)

            print("TEXT PREVIEW")
            print("-" * 80)
            print(text[:1500])
            print()

            for preset_name, table_settings in TABLE_SETTINGS_PRESETS.items():
                print(f"TABLE PRESET: {preset_name}")
                print("-" * 80)

                try:
                    tables = page.extract_tables(table_settings=table_settings)
                except Exception as exc:
                    print(f"ERROR extracting tables with preset {preset_name}: {exc}")
                    page_summary["presets"][preset_name] = {
                        "error": repr(exc),
                        "table_count": 0,
                        "tables": [],
                    }
                    continue

                preset_summary: dict[str, Any] = {
                    "table_count": len(tables),
                    "tables": [],
                }

                print(f"Tables found: {len(tables)}")

                for table_index, table in enumerate(tables, start=1):
                    table_summary = summarize_table(table)
                    preset_summary["tables"].append(table_summary)

                    csv_path = (
                        output_dir
                        / f"page_{page_number:03d}_{preset_name}_table_{table_index:02d}.csv"
                    )
                    write_csv(csv_path, table)
                    table_summary["csv_path"] = str(csv_path)

                    print(f"  Table {table_index}")
                    print(f"    Rows: {table_summary['row_count']}")
                    print(
                        f"    Columns: "
                        f"{table_summary['min_columns']}–{table_summary['max_columns']}"
                    )
                    print(f"    CSV: {csv_path}")
                    print("    First rows:")

                    for row in table_summary["first_rows"][:8]:
                        print(f"      {row}")

                print()

                page_summary["presets"][preset_name] = preset_summary

            summary["pages"].append(page_summary)

    summary_path = output_dir / "pdfplumber_inspection_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )

    print("=" * 80)
    print("DONE")
    print("=" * 80)
    print(f"Summary JSON: {summary_path}")
    print(f"Output directory: {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect TSA throughput PDF table extraction with pdfplumber."
    )
    parser.add_argument(
        "pdf_path",
        type=Path,
        help="Path to TSA throughput PDF.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("pdfplumber_inspection"),
        help="Directory where inspection outputs should be written.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=3,
        help=(
            "Maximum number of pages to inspect. "
            "Use 0 or a negative value to inspect all pages."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    pdf_path: Path = args.pdf_path
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    max_pages = None if args.max_pages <= 0 else args.max_pages

    inspect_pdf(
        pdf_path=pdf_path,
        output_dir=args.output_dir,
        max_pages=max_pages,
    )


if __name__ == "__main__":
    main()