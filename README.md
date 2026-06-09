# tsa-throughput

`tsa-throughput` is a Python package and command-line tool for discovering,
downloading, tracking, and parsing TSA public FOIA checkpoint throughput PDF
reports.

The project is being developed in conjunction with ACI North America's
Data Analytics Working Group (DAWG) to support broader access to and analysis
of TSA throughput data.

## What It Does

`tsa-throughput` currently provides:

- Discovery of TSA throughput PDF links from the public TSA FOIA Reading Room.
- Normalization of weekly report metadata, including week start and week end dates.
- A packaged installed source manifest of known report links.
- Idempotent local PDF downloads with a runtime manifest.
- Safe local filesystem storage for downloaded reports.
- A parser manifest and parser registry.
- A modern TSA PDF parser plugin for hourly checkpoint-level reports.
- A parser coverage scanner for identifying historical layout boundaries.
- CSV output for parsed throughput records.
- CLI commands for discovery, download, parsing, batch parsing, and parser inspection.
- Python APIs for each core step.

## What It Does Not Do Yet

The current package is focused on local discovery, download, manifest tracking,
and parsing.

It does not yet provide:

- Complete historical parser coverage for every TSA PDF layout.
- Cloud storage support such as S3, Azure Blob, or Google Cloud Storage.
- A database loader.
- A hosted API.
- A dashboard or web application.
- A guarantee that live TSA access works from every environment.

Historical layouts should be added incrementally as separate parser plugins.

## Source Data

The source data is published by TSA in the public FOIA Reading Room.

Current listing URL:

```text
https://www.tsa.gov/foia/readingroom?title=&field_foia_tax_category_target_id=1132&page=0
```

The listing is paginated and contains links to weekly throughput PDF reports.
The package can discover those links live, but live discovery and live download
depend on local network access and TSA site availability. Tests use fixtures or
injected fetchers and should not require live network access by default.

Because TSA has changed report layouts over time, parsing is plugin-based.

## Normalization Notes

Source report metadata can contain TSA-provided title and filename mistakes.
Normalization extracts dates from both the link title and URL/filename, validates
candidate weekly ranges, and keeps non-clean `date_confidence` values when the
sources disagree or one source appears invalid.

Handled edge cases include compact legacy ranges such as
`TSA Throughput February 12-18, 2017`, compact cross-month ranges such as
`TSA Throughput February 26-March 4, 2017`, obvious invalid ranges caused by
bad years or backward dates, and source filenames ending in `.xlsx.pdf`.
Known one-off TSA title/filename conflicts are handled by exact filename
overrides so canonical IDs are based on the trusted report period without
broadly preferring filenames over titles.

Canonical output filenames always use the normalized PDF form:
`tsa-throughput-week-ending-YYYY-MM-DD.pdf`.

## Installation

For users:

```bash
pip install tsa-throughput
```

For local development in this repository, use the Conda environment named
`bearing-tsa`:

```bash
conda activate bearing-tsa
pip install -e ".[dev]"
```

If the environment does not already exist:

```bash
conda create -n bearing-tsa python=3.10
conda activate bearing-tsa
pip install -e ".[dev]"
```

Python 3.10 or newer is required.

## Quick Start

Discover the latest listing page:

```bash
tsa-throughput discover --latest
```

Download the latest discovered reports into local storage:

```bash
tsa-throughput download --latest --output-dir data/raw
```

Refresh a source manifest from TSA FOIA discovery results:

```bash
tsa-throughput manifest refresh --output source_manifest.json
```

Parse one downloaded PDF to CSV:

```bash
tsa-throughput parse path/to/report.pdf --output data/parsed/report.csv
```

Parse all PDFs in a local directory to one CSV:

```bash
tsa-throughput parse-all --input-dir data/raw --output data/parsed/throughput.csv
```

Find the next historical parser boundary in downloaded PDFs:

```bash
tsa-throughput parsers coverage --input-dir data/raw --stop-on-first-error
```

## Command-Line Usage

### Discover Reports

Discover reports from the first listing page:

```bash
tsa-throughput discover --latest
```

Discover all paginated reports:

```bash
tsa-throughput discover --all
```

Limit discovery to a fixed number of listing pages:

```bash
tsa-throughput discover --max-pages 3
```

Output discovered, normalized report metadata as JSON:

```bash
tsa-throughput discover --latest --format json
```

Text output is tab-separated:

```text
canonical_id  week_start  week_end  source_filename  date_confidence  source_url
```

### Refresh the Source Manifest

Refresh a source manifest from TSA FOIA discovery results:

```bash
tsa-throughput manifest refresh --output source_manifest.json
```

Limit discovery to a fixed number of listing pages:

```bash
tsa-throughput manifest refresh --output source_manifest.json --max-pages 3
```

Run discovery and normalization without writing a file:

```bash
tsa-throughput manifest refresh --output source_manifest.json --dry-run
```

Print the generated manifest JSON to stdout:

```bash
tsa-throughput manifest refresh --output source_manifest.json --format json
```

Only pass `src/tsa_throughput/assets/source_manifest.json` as `--output` when
you intentionally want to refresh the committed installed manifest. Review any
non-clean `date_confidence` values such as `title_url_conflict` before
publishing a refreshed manifest.

### Download Reports

Download reports from the first listing page:

```bash
tsa-throughput download --latest --output-dir data/raw
```

Download all reports discovered by following pagination:

```bash
tsa-throughput download --all --output-dir data/raw
```

Download from the installed source manifest distributed with the package:

```bash
tsa-throughput download --from-installed-manifest --output-dir data/raw
```

Download from a refreshed source manifest file:

```bash
tsa-throughput manifest refresh --output data/source_manifest.json --max-pages 30
tsa-throughput download --from-source-manifest data/source_manifest.json --output-dir data/raw
```

Download reports discovered from at most three listing pages:

```bash
tsa-throughput download --max-pages 3 --output-dir data/raw
```

Force re-downloads of reports that already exist:

```bash
tsa-throughput download --latest --output-dir data/raw --overwrite
```

Download output is tab-separated and includes the status, canonical report ID,
and local path. Common statuses are `downloaded`, `skipped_existing`, and
`overwritten`.

### Parse Reports

Parse one PDF to CSV:

```bash
tsa-throughput parse path/to/report.pdf --output data/parsed/report.csv
```

Limit parsing to the first five pages during development:

```bash
tsa-throughput parse path/to/report.pdf --output data/parsed/report.csv --max-pages 5
```

Force a specific parser:

```bash
tsa-throughput parse path/to/report.pdf \
  --parser modern_total_pax_kcm_hourly_checkpoint_pdfplumber \
  --output data/parsed/report.csv
```

### Parse a Directory

Parse all matching PDFs in a directory:

```bash
tsa-throughput parse-all --input-dir data/raw --output data/parsed/throughput.csv
```

Use a custom glob pattern:

```bash
tsa-throughput parse-all \
  --input-dir data/raw \
  --pattern "tsa-throughput-week-ending-2026-*.pdf" \
  --output data/parsed/throughput.csv
```

Keep going after parser failures:

```bash
tsa-throughput parse-all \
  --input-dir data/raw \
  --output data/parsed/throughput.csv \
  --continue-on-error
```

`parse-all` reads `manifest.json` from the input directory when present. That
manifest supplies week dates, source URLs, source filenames, and canonical
filenames. If no manifest entry matches a PDF, `parse-all` falls back to a
minimal report inferred from filenames like
`tsa-throughput-week-ending-YYYY-MM-DD.pdf`.

### Inspect Parsers

List parser plugins from the installed parser manifest:

```bash
tsa-throughput parsers list
```

Show which parser matches a report week ending date:

```bash
tsa-throughput parsers match --week-ending 2026-06-06
```

Optionally validate parser selection against a PDF:

```bash
tsa-throughput parsers match \
  --week-ending 2026-06-06 \
  --pdf-path path/to/report.pdf
```

Scan downloaded PDFs from newest to oldest to identify where installed parser
coverage stops:

```bash
tsa-throughput download --from-installed-manifest --output-dir data/raw
tsa-throughput parsers coverage --input-dir data/raw
```

Useful development options:

```bash
tsa-throughput parsers coverage --input-dir data/raw --pattern "*.pdf"
tsa-throughput parsers coverage --input-dir data/raw --max-pages 3
tsa-throughput parsers coverage --input-dir data/raw --stop-on-first-error
tsa-throughput parsers coverage --input-dir data/raw --format json
```

The coverage scanner reads `manifest.json` when available and falls back to
canonical filenames like `tsa-throughput-week-ending-YYYY-MM-DD.pdf`. It reports
the earliest successful week ending date and the first failure, which is the PDF
to inspect when adding the next historical parser plugin.

Historical parser development requires real local TSA PDFs. Before coverage
scanning, make sure `data/raw` exists and contains downloaded PDFs plus
`data/raw/manifest.json`. Start with the installed manifest:

```bash
tsa-throughput download --from-installed-manifest --output-dir data/raw
tsa-throughput parsers coverage --input-dir data/raw --stop-on-first-error --max-pages 3
```

If the installed manifest is stale or incomplete, refresh a development source
manifest first and then download from it:

```bash
tsa-throughput manifest refresh --output data/source_manifest.json --max-pages 30
tsa-throughput download --from-source-manifest data/source_manifest.json --output-dir data/raw
tsa-throughput parsers coverage --input-dir data/raw --stop-on-first-error --max-pages 3
```

The downloader is idempotent and uses `data/raw/manifest.json` to skip existing
files on repeated runs unless `--overwrite` is supplied. These live download
commands are manual development workflow steps; default tests continue to use
fixtures and injected fetchers.

## Python Usage

### Discover Report Links

```python
from tsa_throughput.discovery import discover_report_links

raw_links = discover_report_links(max_pages=1)

for link in raw_links:
    print(link.title, link.url)
```

### Normalize Report Links

```python
from tsa_throughput.discovery import discover_report_links
from tsa_throughput.normalization import normalize_report_links

raw_links = discover_report_links(max_pages=1)
reports = normalize_report_links(raw_links)

for report in reports:
    print(report.canonical_id, report.week_start, report.week_end)
```

### Load the Installed Source Manifest

```python
from tsa_throughput.source_manifest import (
    list_source_reports,
    load_installed_source_manifest,
)

manifest = load_installed_source_manifest()
reports = list_source_reports(manifest)

print(manifest.generated_at)
print(reports[0].canonical_filename)
```

### Refresh a Source Manifest

```python
from pathlib import Path

from tsa_throughput.source_manifest import refresh_source_manifest

manifest = refresh_source_manifest(output_path=Path("source_manifest.json"), max_pages=3)

print(len(manifest.reports))
```

### Download Missing Reports

```python
from pathlib import Path

from tsa_throughput.download import download_missing_reports
from tsa_throughput.source_manifest import list_source_reports
from tsa_throughput.storage import LocalStorage

reports = list_source_reports()
storage = LocalStorage(Path("data/raw"))

results = download_missing_reports(
    reports,
    storage=storage,
    manifest_path=storage.root / "manifest.json",
)

for result in results:
    print(result.status, result.path)
```

### Parse One Report

```python
from pathlib import Path

from tsa_throughput.models import ThroughputReport
from tsa_throughput.parsing.registry import get_parser

pdf_path = Path("data/raw/tsa-throughput-week-ending-2026-06-06.pdf")
report = ThroughputReport(
    source_url="",
    week_end=None,
    source_filename=pdf_path.name,
    canonical_filename=pdf_path.name,
)

parser = get_parser(report, pdf_path)
result = parser.parse(pdf_path, report=report)

print(result.record_count)
print(result.records[0])
```

## Parsed CSV Schema

The CLI writes parsed records with these columns:

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

Dates are written as `YYYY-MM-DD`. Hours are written as `HH:MM`. Missing values
are written as empty CSV fields. `source_file` is written as the source filename.

Example record:

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
  "source_url": "https://www.tsa.gov/sites/default/files/foia-readingroom/tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf",
  "source_page": 1,
  "source_table": 1,
  "parser_name": "modern_total_pax_kcm_hourly_checkpoint_pdfplumber",
  "parser_version": "0.1.0",
  "parse_confidence": "high"
}
```

## Manifests

### Parser Manifest

The parser manifest is distributed with the package:

```text
src/tsa_throughput/assets/parser_manifest.json
```

It records parser name, module, class, valid date range, priority, layout family,
and description. The registry loads this manifest, selects candidates by week
ending date when available, and then calls parser `can_parse()` before parsing.

### Installed Source Manifest

The installed source manifest is distributed with the package:

```text
src/tsa_throughput/assets/source_manifest.json
```

It stores known TSA report metadata:

- Canonical report ID.
- Week start and week end.
- Original title.
- Source URL.
- Original TSA filename.
- Canonical local filename.
- Date confidence.
- Listing URL.
- Alternate URLs.

Use `tsa-throughput download --from-installed-manifest` when you want to download
from this packaged catalog instead of scraping the live listing first. Use
`tsa-throughput download --from-source-manifest path/to/source_manifest.json`
when parser development needs a freshly discovered source manifest.

The installed source manifest is a known catalog of TSA FOIA report links, not a
guarantee that the live TSA site is reachable or that every linked PDF is
currently available. Refresh tests use fixtures or monkeypatched discovery and
should not require live TSA network access.

### Runtime Download Manifest

When reports are downloaded, a local runtime manifest is written under the output
directory:

```text
data/raw/manifest.json
```

It records downloaded reports, local filenames, source URLs, original filenames,
SHA-256 checksums, byte sizes, download timestamps, and date confidence. The
downloader uses this manifest to skip existing files unless `--overwrite` is
provided.

## Parser Plugins

Parser plugins implement `tsa_throughput.parsing.base.ThroughputParser`.

Each parser provides:

- `parser_name`
- `parser_version`
- `layout_family`
- `can_parse(report, pdf_path)`
- `parse(source_file, max_pages=None, report=None)`

The current installed parsers are:

```text
modern_total_pax_kcm_hourly_checkpoint_pdfplumber
historical_total_pax_kcm_hourly_checkpoint_pdfplumber
historical_total_pax_kcm_hourly_checkpoint_strict_pdfplumber
historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber
historical_march_2022_total_pax_kcm_hourly_checkpoint_pdfplumber
```

Most supported reports use the hourly checkpoint layout with these columns:

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

The parsers use `pdfplumber` line-based table extraction and emit the canonical
CSV schema above. It forward-fills repeated date, hour, airport code, airport
name, city, and state values. It does not forward-fill checkpoint names or
throughput counts.

The modern parser manifest is valid from week ending `2025-12-27`, backed by
the verified `tests/fixtures/tsa-throughput-week-ending-2025-12-27.pdf`
fixture. The historical parser manifest is valid from week ending `2023-01-07`
through `2025-12-20`, backed by representative fixtures at both ends of that
range. The strict historical parser manifest is valid from week ending
`2022-04-09` through `2022-12-31`; it uses stricter pdfplumber line extraction
for the same `Total Pax + KCM PAX` columns. The PMIS historical parser manifest
is valid for week ending `2022-04-02`; it uses the
`PMIS - Total Customer Throughput (Unadjusted)` source column. The March 2022
historical parser manifest is valid from week ending `2022-03-05` through
`2022-03-26` for the earlier 8-column `Total Pax + KCM PAX` layout. The next
local historical boundary found by coverage is week ending `2022-02-26`.

Current limitations:

- Only the `Total Pax + KCM PAX` layout families and one PMIS hourly checkpoint
  layout are implemented.
- Historical layouts must be added as separate parser plugins.
- Parser manifest date ranges should be treated as conservative hints, not proof
  of universal coverage.
- The parser fails conservatively when required headers or fields are missing.

## Development

Use the project Conda environment:

```bash
conda activate bearing-tsa
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

Useful CLI verification commands:

```bash
tsa-throughput --help
tsa-throughput discover --help
tsa-throughput download --help
tsa-throughput parse --help
tsa-throughput parse-all --help
tsa-throughput parsers list
tsa-throughput parsers match --week-ending 2026-06-06
```

Default tests should not make live network calls. Live or integration tests, if
added, should be marked separately and require explicit opt-in.
