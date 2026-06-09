# CODEX.md

## Project

This repository contains `tsa-throughput`, a reusable Python library and command-line tool for discovering, downloading, tracking, and parsing TSA public FOIA checkpoint throughput PDF reports.

The project is intended to support analytics pipelines, scheduled jobs, research workflows, airport data products, and local scripts that need structured TSA checkpoint throughput data.

This project is being developed in conjunction with ACI North America's Data Analytics Working Group (DAWG) to support broader access to and analysis of TSA throughput data.

## Package and CLI Names

Package/import name:

```text
tsa_throughput
```

Distribution / project name:

```text
tsa-throughput
```

CLI command:

```text
tsa-throughput
```

Author contact:

```text
joel@bearing.aero
```

## Development Environment

Assume development is performed using Conda or Miniconda.

Create and activate a development environment:

```bash
conda create -n tsa-throughput python=3.10
conda activate tsa-throughput
pip install -e ".[dev]"
```

If using an existing environment:

```bash
conda activate tsa-throughput
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

Build package:

```bash
python -m build
```

## Python Version

Support:

```text
Python >= 3.10
```

## Core Design Principles

Build a reusable library first and a CLI second.

The core package should not assume it is being run from a terminal, Lambda, notebook, cron job, or GitHub Action. Those should be thin wrappers around reusable library functions.

Keep responsibilities separated:

* HTTP fetching
* FOIA listing discovery
* PDF link extraction
* report metadata normalization
* download behavior
* storage
* manifests
* PDF parsing
* parser plugin registration
* CLI orchestration

Avoid one large end-to-end scraper function.

Prefer small, typed, testable modules.

Use boring, maintainable Python.

## Project Structure

Target structure:

```text
tsa-throughput/
  pyproject.toml
  README.md
  LICENSE
  CHANGELOG.md
  CODEX.md
  docs/
    design.md
    current_plugin_notes.md
  src/
    tsa_throughput/
      __init__.py
      assets/
        source_manifest.json
        parser_manifest.json
      client.py
      discovery.py
      normalization.py
      download.py
      storage.py
      manifest.py
      models.py
      exceptions.py
      logging.py
      cli.py
      parsing/
        __init__.py
        base.py
        registry.py
        plugins/
          __init__.py
          modern_total_pax_kcm_hourly_checkpoint_pdfplumber.py
  tests/
    fixtures/
      tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf
      pdfplumber_inspection_summary.json
    test_models.py
    test_modern_parser.py
    test_parser_registry.py
    test_cli.py
```

## Implementation Priority

Build in this order:

1. Package skeleton and dataclass models.
2. Package-specific exceptions.
3. Modern PDF parser plugin.
4. Parser registry and parser manifest.
5. CLI parse command.
6. Local filesystem storage.
7. Runtime download manifest.
8. TSA listing discovery from saved fixtures.
9. Report metadata normalization.
10. Idempotent downloader.
11. Installed source manifest refresh.
12. Historical parser plugins only as needed.

Do not start by building the whole scraper end-to-end.

## Current Priority

The first major implementation target is the modern TSA PDF parser.

The recent TSA PDF layout has this table structure:

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

The blank fourth header column is the airport name column.

The parser should use `pdfplumber` with line-based table extraction.

Recommended table settings:

```python
TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "intersection_tolerance": 3,
}
```

Observed from inspection:

* The recent sample PDF has 987 pages.
* The first five inspected pages each had one main table.
* The useful table extraction produced 53 rows and 8 columns per inspected page.
* `default`, `lines`, and `lines_strict` worked well.
* `text` and `mixed_vertical_lines_horizontal_text` were worse for the main parser.

Use `lines` unless implementation testing suggests otherwise.

## Modern Parser Rules

Parser name:

```text
modern_total_pax_kcm_hourly_checkpoint_pdfplumber
```

Layout family:

```text
hourly_checkpoint_total_pax_kcm
```

Metric name:

```text
total_pax_plus_kcm_pax
```

Metric source column:

```text
Total Pax + KCM PAX
```

Column mapping:

```python
COLUMN_MAP = {
    "Date": "throughput_date",
    "Hour of Day": "hour",
    "Airport": "airport_code",
    "": "airport_name",
    "City": "city",
    "State": "state",
    "Checkpoint": "checkpoint_name",
    "Total Pax + KCM PAX": "throughput_count",
}
```

Forward-fill these fields:

```text
throughput_date
hour
airport_code
airport_name
city
state
```

Do not forward-fill:

```text
checkpoint_name
throughput_count
```

The parser should fail clearly if required fields cannot be mapped.

Do not guess through unfamiliar layouts.

## Canonical Parsed Output

Canonical parsed records should support these fields:

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

Generally required fields:

```text
throughput_date
airport_code
throughput_count
source_file
parser_name
parser_version
```

For the modern hourly checkpoint parser, also require:

```text
hour
checkpoint_name
```

## Parser Plugin Architecture

TSA PDF layouts may change over time. Parsing must be plugin-based.

The core library should define:

* parser interface
* parser registry
* parser manifest loading
* canonical parsed record model
* shared normalization helpers
* common exceptions

Each parser plugin should define:

* supported layout
* source column expectations
* source-to-canonical column mapping
* required fields
* optional fields
* forward-fill fields
* value normalization
* `can_parse()` validation
* conservative failure behavior

Parser metadata belongs in:

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

Date ranges in the parser manifest should be conservative and backed by fixtures.

## Models

Create dataclasses in `src/tsa_throughput/models.py` for:

* `RawReportLink`
* `ThroughputReport`
* `DownloadResult`
* `ThroughputRecord`
* `ParseResult`

Use `pathlib.Path`, `datetime.date`, and `datetime.time` where appropriate.

Keep models plain and serializable.

## Exceptions

Create package-specific exceptions in `src/tsa_throughput/exceptions.py`.

Suggested exceptions:

```python
class TSAThroughputError(Exception):
    pass

class TSAThroughputHTTPError(TSAThroughputError):
    pass

class DiscoveryError(TSAThroughputError):
    pass

class PaginationError(DiscoveryError):
    pass

class NormalizationError(TSAThroughputError):
    pass

class DownloadError(TSAThroughputError):
    pass

class ManifestError(TSAThroughputError):
    pass

class ParserNotFoundError(TSAThroughputError):
    pass

class ParseError(TSAThroughputError):
    pass
```

Library functions should raise package-specific exceptions.

CLI commands should catch package-specific exceptions and exit nonzero with a readable message.

Only show tracebacks with `--debug`.

## Logging Rules

Use the standard `logging` module.

Library modules should use:

```python
import logging

logger = logging.getLogger(__name__)
```

Do not configure global logging inside library code.

Do not use `print()` in reusable library code.

The CLI may print user-facing messages.

## Testing Rules

Tests must not make live TSA network calls by default.

Use fixtures under:

```text
tests/fixtures/
```

Live tests, if added, must be skipped by default and require:

```bash
TSA_THROUGHPUT_RUN_LIVE_TESTS=1
```

Optional live test command:

```bash
pytest -m integration
```

Important parser tests for the modern plugin:

* parse first five pages of the sample PDF
* `record_count > 0`
* first record is:

  * date `2026-05-31`
  * hour `00:00`
  * airport `ANC`
  * checkpoint `South Checkpoint`
  * count `208`
* ATL `Main Checkpoint` appears with count `79`
* forward-filled ATL metadata is correct
* `metric_name == "total_pax_plus_kcm_pax"`
* `metric_source_column == "Total Pax + KCM PAX"`
* parser fails clearly when the expected header is not found

## Discovery and Download Rules

Discovery and download are not the first implementation priority, but they should follow this design.

The TSA listing URL is:

```text
https://www.tsa.gov/foia/readingroom?title=&field_foia_tax_category_target_id=1132&page=0
```

Discovery should:

* start at `page=0`
* extract PDF links
* follow pagination until no `Next` link exists
* support `max_pages`
* detect suspicious pagination changes
* not assume listing order is chronological

Downloads should:

* be idempotent
* write temporary files before final files
* validate that content appears to be PDF
* compute SHA-256
* preserve source URL and original TSA filename
* update the runtime manifest

## Manifest Rules

There are two manifest concepts.

### Installed Source Manifest

Path:

```text
src/tsa_throughput/assets/source_manifest.json
```

Purpose:

* known TSA report links
* report date ranges
* original source URLs
* original TSA filenames
* canonical filenames
* date confidence
* alternate URLs

This manifest is committed to git and distributed with the package.

### Runtime Download Manifest

Default path:

```text
<output_dir>/manifest.json
```

Purpose:

* downloaded reports
* local filenames
* checksums
* source URLs
* original filenames
* file sizes
* download timestamps

This makes scheduled jobs safe to rerun.

## Date Handling

Store both:

```text
week_start
week_end
```

Canonical report identity should use `week_end`:

```text
tsa-throughput-week-ending-YYYY-MM-DD
```

Example:

```text
tsa-throughput-week-ending-2026-06-06.pdf
```

If title and URL disagree, mark:

```text
date_confidence = "conflict"
```

Do not overwrite an existing canonical file automatically when date confidence is `conflict`.

## CLI Rules

Implement the CLI as a thin wrapper around library functions.

Recommended CLI commands:

```bash
tsa-throughput discover
tsa-throughput discover --all
tsa-throughput download --latest --output-dir data/raw
tsa-throughput download --all --output-dir data/raw
tsa-throughput parse report.pdf --output report.csv
tsa-throughput parse-all --input-dir data/raw --output throughput.csv
tsa-throughput manifest show
tsa-throughput manifest refresh
tsa-throughput parsers list
tsa-throughput parsers match --week-ending 2026-06-06
```

CSV should be the default parsed output format.

## Style Rules

Use:

* type hints
* dataclasses
* `pathlib.Path`
* small functions
* explicit names
* package-specific exceptions
* dependency injection for HTTP and storage where useful

Avoid:

* hidden global state
* hard-coded output paths
* silent failures
* live network calls in tests
* notebook-style package code
* unstructured dictionaries as the main API
* one giant scraper function
* parsing guesses that silently produce bad data

## Task Size Guidance

Keep implementation tasks narrow.

Good task:

```text
Implement the modern parser plugin and tests against the provided fixture.
```

Bad task:

```text
Build the entire TSA throughput library.
```

Recommended first Codex tasks:

1. Implement model dataclasses and exceptions.
2. Implement the modern parser plugin and tests.
3. Implement parser manifest and registry.
4. Implement CLI parse command.
5. Implement local storage and manifests.
6. Implement discovery from saved listing fixtures.
7. Implement download behavior.

## Documentation

Keep the full technical design in:

```text
docs/design.md
```

Keep current parser notes in:

```text
docs/current_plugin_notes.md
```

Keep this file concise enough for Codex to use as operating instructions.

When behavior changes, update the relevant documentation and tests in the same task.
