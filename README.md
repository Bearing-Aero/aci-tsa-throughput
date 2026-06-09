# tsa-throughput

`tsa-throughput` is a Python library and command-line tool for discovering, downloading, tracking, and parsing TSA public FOIA checkpoint throughput PDF reports.

The package is designed for people who want to use TSA throughput data in analytics pipelines, scheduled jobs, research workflows, airport data products, or local scripts.

This project is being developed in conjunction with ACI North America's (ACI-NA) Data Analytics Working Group (DAWG) to support broader access to and analysis of TSA throughput data.

## What it does

`tsa-throughput` is intended to:

* Discover TSA throughput PDF reports from the TSA FOIA Reading Room.
* Normalize report metadata such as report week start and week end dates.
* Download PDF reports idempotently.
* Preserve original TSA source URLs and filenames.
* Maintain a local manifest of downloaded reports.
* Parse TSA throughput PDFs into structured records.
* Support parser plugins for different TSA PDF layouts over time.
* Provide both a Python API and a command-line interface.

## What it does not do

Version 1 is focused on discovery, download, local tracking, and PDF parsing.

It does not initially provide:

* S3, Azure Blob, or Google Cloud Storage support.
* A database loader.
* A hosted API.
* A dashboard or web application.
* Guaranteed parsing coverage for every historical TSA PDF layout.

Historical parsing coverage will be added incrementally through parser plugins.

## Source data

The source data comes from the TSA public FOIA Reading Room.

Current listing URL:

```text
https://www.tsa.gov/foia/readingroom?title=&field_foia_tax_category_target_id=1132&page=0
```

The listing is paginated and contains links to weekly TSA throughput PDF reports.

Because the TSA has changed PDF table layouts over time, this package uses parser plugins rather than assuming every report has the same schema.

## Installation

```bash
pip install tsa-throughput
```

For local development:

```bash
git clone https://github.com/<owner>/tsa-throughput.git
cd tsa-throughput
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quick start

Download the latest known TSA throughput report:

```bash
tsa-throughput download --latest --output-dir data/raw
```

Parse a downloaded PDF to CSV:

```bash
tsa-throughput parse data/raw/tsa-throughput-week-ending-2026-06-06.pdf \
  --output data/parsed/tsa-throughput-week-ending-2026-06-06.csv
```

## Python usage

Discover reports from the TSA listing:

```python
from tsa_throughput import discover_reports

reports = discover_reports(max_pages=1)

for report in reports:
    print(report.week_start, report.week_end, report.url)
```

Download missing reports:

```python
from pathlib import Path

from tsa_throughput import discover_reports, download_missing_reports
from tsa_throughput.storage import LocalStorage

reports = discover_reports(max_pages=1)
storage = LocalStorage(Path("data/raw"))

results = download_missing_reports(reports, storage=storage)

for result in results:
    print(result.status, result.path)
```

Parse a report:

```python
from tsa_throughput import parse_report

result = parse_report("data/raw/tsa-throughput-week-ending-2026-06-06.pdf")

print(result.record_count)
print(result.records[0])
```

## Command-line usage

### Discover reports

Discover the latest page of reports:

```bash
tsa-throughput discover --latest
```

Discover all paginated reports:

```bash
tsa-throughput discover --all
```

Limit discovery to a fixed number of pages:

```bash
tsa-throughput discover --max-pages 3
```

Output as JSON:

```bash
tsa-throughput discover --latest --format json
```

### Download reports

Download the latest reports:

```bash
tsa-throughput download --latest --output-dir data/raw
```

Backfill all discovered reports:

```bash
tsa-throughput download --all --output-dir data/raw
```

Download from the installed source manifest:

```bash
tsa-throughput download --from-installed-manifest --output-dir data/raw
```

### Parse reports

Parse one PDF to CSV:

```bash
tsa-throughput parse data/raw/tsa-throughput-week-ending-2026-06-06.pdf \
  --output data/parsed/report.csv
```

Parse all PDFs in a directory:

```bash
tsa-throughput parse-all --input-dir data/raw --output data/parsed/throughput.csv
```

List available parser plugins:

```bash
tsa-throughput parsers list
```

Show which parser would match a report date:

```bash
tsa-throughput parsers match --week-ending 2026-06-06
```

Force a specific parser:

```bash
tsa-throughput parse report.pdf \
  --parser modern_total_pax_kcm_hourly_checkpoint_pdfplumber \
  --output report.csv
```

## Parsed output

The canonical parsed output is designed to support detailed hourly checkpoint-level records while allowing nullable fields for formats that do not provide every value.

Default CSV columns:

```text
throughput_date
hour
airport_code
airport_name
city
state
checkpoint_name
metric_name
metric_source_column
throughput_count
week_start
week_end
source_file
source_url
source_page
source_table
parser_name
parser_version
parse_confidence
```

Example conceptual record:

```json
{
  "throughput_date": "2026-05-31",
  "hour": "00:00",
  "airport_code": "ANC",
  "airport_name": "Ted Stevens Anchorage International",
  "city": "Anchorage",
  "state": "AK",
  "checkpoint_name": "South Checkpoint",
  "metric_name": "total_pax_plus_kcm_pax",
  "metric_source_column": "Total Pax + KCM PAX",
  "throughput_count": 208,
  "week_start": "2026-05-31",
  "week_end": "2026-06-06",
  "source_file": "tsa-throughput-week-ending-2026-06-06.pdf",
  "source_page": 1,
  "source_table": 1,
  "parser_name": "modern_total_pax_kcm_hourly_checkpoint_pdfplumber",
  "parser_version": "0.1.0",
  "parse_confidence": "high"
}
```

## Parser plugins

TSA PDF layouts may change over time, so parsing is handled by plugins.

Each parser plugin defines:

* The PDF layout it supports.
* The date range it is expected to cover.
* The source columns it expects.
* How source columns map to canonical output fields.
* Which fields should be forward-filled.
* How values should be normalized.
* Whether it can safely parse a given PDF.

Parser metadata is distributed with the package in:

```text
src/tsa_throughput/assets/parser_manifest.json
```

Example parser manifest entry:

```json
{
  "name": "modern_total_pax_kcm_hourly_checkpoint_pdfplumber",
  "module": "tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber",
  "class": "ModernTotalPaxKcmHourlyCheckpointPdfplumberParser",
  "valid_from": "2026-01-01",
  "valid_to": null,
  "priority": 100,
  "layout_family": "hourly_checkpoint_total_pax_kcm",
  "description": "Parser for modern hourly airport/checkpoint TSA throughput tables with Total Pax + KCM PAX counts."
}
```

If TSA changes the PDF layout, a new parser plugin can be added without changing the rest of the library.

## Current parser focus

The first parser focuses on the modern TSA PDF layout where the table structure is:

```text
Date
Hour of Day
Airport
[airport name]
City
State
Checkpoint
Total Pax + KCM PAX
```

The parser uses `pdfplumber` line-based table extraction.

Forward-filled fields:

```text
throughput_date
hour
airport_code
airport_name
city
state
```

Fields that are not forward-filled:

```text
checkpoint_name
throughput_count
```

## Manifests

The project uses two manifest concepts.

### Installed source manifest

The installed source manifest is distributed with the package:

```text
src/tsa_throughput/assets/source_manifest.json
```

It stores known TSA report links and metadata, including:

* Canonical report ID
* Week start
* Week end
* Original title
* Source URL
* Original TSA filename
* Canonical filename
* Date confidence
* Alternate URLs, if any

This manifest allows users to work from a known report catalog without scraping the live TSA listing every time.

### Runtime download manifest

When reports are downloaded, a local runtime manifest is written to the output directory:

```text
data/raw/manifest.json
```

It records:

* Downloaded reports
* Source URLs
* Original filenames
* Canonical local filenames
* SHA-256 checksums
* Download timestamps
* File sizes
* Date confidence

This makes scheduled jobs safe to rerun.

## Date handling

Each weekly report may have a start date and end date in the link title, source filename, or both.

The package stores both:

```text
week_start
week_end
```

The canonical report identity uses the week end date:

```text
tsa-throughput-week-ending-YYYY-MM-DD
```

Example filename:

```text
tsa-throughput-week-ending-2026-06-06.pdf
```

If the title and URL disagree, the report is marked with:

```text
date_confidence = "conflict"
```

Conflicting reports are preserved in metadata, but the downloader should not overwrite an existing canonical local file automatically.

## Development

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Run linting:

```bash
ruff check .
```

Build the package:

```bash
python -m build
```

## Testing

Tests should not make live network calls by default.

Fixtures should be stored under:

```text
tests/fixtures/
```

Recommended fixture types:

* Saved TSA listing pages
* Sample TSA PDFs
* Parser manifest examples
* Source manifest examples
* Duplicate report link examples
* Date conflict examples
* Malformed listing pages

Optional live tests may be marked separately:

```bash
pytest -m integration
```

Live tests should require an explicit environment variable:

```bash
TSA_THROUGHPUT_RUN_LIVE_TESTS=1
```

## Development roadmap

Recommended implementation order:

1. Package skeleton and data models.
2. Modern PDF parser plugin.
3. Parser registry and parser manifest.
4. CLI parse command.
5. Local storage abstraction.
6. Runtime download manifest.
7. TSA listing discovery from saved fixtures.
8. Report metadata normalization.
9. Idempotent downloader.
10. Installed source manifest refresh.
11. Historical parser plugins as needed.

## Contributing parser plugins

When adding support for a new TSA PDF layout:

1. Add a representative PDF fixture.
2. Create a new parser plugin.
3. Register it in `parser_manifest.json`.
4. Add tests for the new layout.
5. Confirm older parser tests still pass.
6. Document the new layout family.

Parser plugins should fail conservatively. If required fields cannot be mapped with reasonable confidence, the parser should raise a clear error rather than returning guessed records.
