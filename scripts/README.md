# PDF Inspection Scripts

This directory contains development and diagnostic scripts used to understand how TSA throughput PDFs are structured before implementing production parser plugins in `tsa_throughput`.

These scripts are not the core library API. They are intended to help inspect PDF layouts, compare `pdfplumber` extraction strategies, and generate fixtures or notes for parser development.

## `inspect_pdfplumber_tables.py`

`inspect_pdfplumber_tables.py` is a diagnostic script for inspecting how `pdfplumber` sees a TSA throughput PDF.

It does not produce final parsed throughput records. Instead, it extracts and summarizes:

* Basic PDF page metadata
* Page text previews
* Detected table counts
* Table dimensions
* Sample extracted rows
* CSV exports of extracted tables
* A JSON inspection summary

The purpose is to determine which `pdfplumber` table extraction settings work best for a given TSA PDF layout.

## Why this script exists

TSA throughput PDFs have changed layout over time. Some reports use older table formats, while recent reports use a modern hourly checkpoint-level format.

Before creating a parser plugin, it is useful to inspect:

* Whether `pdfplumber` detects the table correctly
* Whether the table columns are stable
* Whether rows are split or merged
* Whether repeated values need to be forward-filled
* Which table extraction settings produce the cleanest output

The results from this script are used to design parser plugins such as:

```text
modern_total_pax_kcm_hourly_checkpoint_pdfplumber
```

## Installation

From the project root, install the package and development dependencies:

```bash
pip install -e ".[dev]"
```

Or install `pdfplumber` directly if running the script standalone:

```bash
pip install pdfplumber
```

## Usage

Run the script against a TSA throughput PDF:

```bash
python inspect_pdfplumber_tables.py path/to/report.pdf
```

Example:

```bash
python inspect_pdfplumber_tables.py tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf \
  --output-dir inspection_2026 \
  --max-pages 5
```

To inspect the full PDF, use `--max-pages 0`:

```bash
python inspect_pdfplumber_tables.py tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf \
  --output-dir inspection_2026_full \
  --max-pages 0
```

## Arguments

### `pdf_path`

Path to the PDF file to inspect.

Example:

```bash
python inspect_pdfplumber_tables.py tests/fixtures/sample.pdf
```

### `--output-dir`

Directory where inspection outputs should be written.

Default:

```text
pdfplumber_inspection
```

Example:

```bash
--output-dir inspection_2026
```

### `--max-pages`

Maximum number of pages to inspect.

Default:

```text
3
```

Use `0` or a negative value to inspect all pages.

Example:

```bash
--max-pages 0
```

## Output files

The script writes several files to the output directory.

### `pdfplumber_inspection_summary.json`

A JSON summary of the inspection results.

This includes:

* PDF path
* total page count
* pages processed
* page dimensions
* character/line/rect counts
* table counts by extraction preset
* table row and column counts
* sample rows from each detected table
* paths to generated CSV files

This file is useful as a fixture for parser development.

### `page_###_text.txt`

Plain-text extraction from each inspected page.

Example:

```text
page_001_text.txt
```

This is useful for quickly checking page titles, report dates, and visible text that may not appear cleanly in extracted tables.

### `page_###_<preset>_table_##.csv`

CSV exports of tables detected by each `pdfplumber` extraction preset.

Example:

```text
page_001_default_table_01.csv
page_001_lines_table_01.csv
page_001_lines_strict_table_01.csv
page_001_text_table_01.csv
page_001_mixed_vertical_lines_horizontal_text_table_02.csv
```

These files allow side-by-side comparison of different extraction strategies.

## Table extraction presets

The script tests several `pdfplumber` table extraction settings.

### `default`

Uses `pdfplumber` default table extraction behavior.

### `lines`

Uses visible PDF lines for both vertical and horizontal table boundaries.

This has worked well for the recent TSA throughput PDF layout.

### `lines_strict`

A stricter line-based extraction preset with lower tolerance values.

### `text`

Uses text positioning to infer table boundaries.

This may be useful for PDFs without strong grid lines, but it can split rows or headers poorly.

### `mixed_vertical_lines_horizontal_text`

Uses vertical lines and horizontal text positioning.

This can be useful for some PDFs, but it may separate title/date content from the main table body.

## Interpreting results

For the recent TSA throughput layout, the preferred extraction has been:

```text
lines
```

The useful table structure observed in the recent sample was:

```text
Date
Hour of Day
Airport
[blank airport name column]
City
State
Checkpoint
Total Pax + KCM PAX
```

The fourth column has a blank header in extraction output, but contains the airport name.

A good extraction should usually show:

* One main throughput table per page
* Consistent column count
* Recognizable header row
* Checkpoint and throughput count in separate columns
* Repeated fields left blank where the PDF visually merges cells

Those blank repeated fields are expected and should be handled later by parser forward-fill logic.

## What this script does not do

This script does not:

* Normalize report metadata
* Download PDFs
* Update manifests
* Produce final parser records
* Apply parser plugins
* Guarantee that a PDF layout is supported
* Validate all historical TSA formats

It is a development aid only.

## Recommended workflow

1. Download a representative TSA throughput PDF.
2. Run this script against the first few pages.
3. Compare the generated CSV files.
4. Identify the cleanest extraction preset.
5. Document the observed layout in `docs/current_plugin_notes.md`.
6. Implement or update a parser plugin.
7. Add the PDF and inspection summary as test fixtures if appropriate.
8. Write parser tests against the fixture.

## Example development command

```bash
python inspect_pdfplumber_tables.py tests/fixtures/tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf \
  --output-dir inspection_2026 \
  --max-pages 5
```

Useful files to inspect after running:

```text
inspection_2026/pdfplumber_inspection_summary.json
inspection_2026/page_001_lines_table_01.csv
inspection_2026/page_001_default_table_01.csv
inspection_2026/page_001_text.txt
```

## Notes for parser development

For the modern TSA layout, parser logic should likely:

* Use line-based table extraction
* Map the blank fourth column to `airport_name`
* Forward-fill `throughput_date`
* Forward-fill `hour`
* Forward-fill `airport_code`
* Forward-fill `airport_name`
* Forward-fill `city`
* Forward-fill `state`
* Never forward-fill `checkpoint_name`
* Never forward-fill `throughput_count`
* Treat `Total Pax + KCM PAX` as the metric source column
* Set `metric_name` to `total_pax_plus_kcm_pax`

Parser plugins should fail conservatively if the expected structure is not detected.
