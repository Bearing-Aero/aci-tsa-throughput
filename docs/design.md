# Design

This document describes the implemented architecture of `tsa-throughput`.

## Goals

`tsa-throughput` provides a reusable Python package and CLI for working with
TSA public FOIA checkpoint throughput PDF reports.

Current goals:

- Discover report links from the TSA FOIA Reading Room.
- Normalize source metadata into stable report identifiers.
- Download PDFs safely into local filesystem storage.
- Track local downloads in a runtime manifest.
- Load a packaged catalog of known report links from an installed source manifest.
- Parse supported PDFs into canonical records.
- Keep parser support plugin-based so historical layouts can be added safely.

## Non-Goals

The current implementation does not provide:

- Complete historical parsing coverage.
- Cloud storage backends.
- Database loading.
- A hosted API.
- A dashboard or web app.
- Live-network requirements for default tests.
- Guessing through unfamiliar PDF layouts.

## Package Layout

```text
src/tsa_throughput/
  __init__.py
  client.py
  cli.py
  discovery.py
  download.py
  exceptions.py
  logging.py
  manifest.py
  models.py
  normalization.py
  source_manifest.py
  storage.py
  assets/
    parser_manifest.json
    source_manifest.json
  parsing/
    __init__.py
    base.py
    batch.py
    registry.py
    plugins/
      __init__.py
      modern_total_pax_kcm_hourly_checkpoint_pdfplumber.py
```

## Core Models

Models live in `src/tsa_throughput/models.py`.

- `RawReportLink`: raw link data extracted from a TSA listing page.
- `ThroughputReport`: normalized metadata for a weekly report.
- `DownloadResult`: result metadata for a download attempt.
- `RuntimeManifestEntry`: one downloaded report entry in a local manifest.
- `RuntimeManifest`: local manifest of downloaded reports.
- `SourceManifest`: installed catalog of known source reports.
- `ThroughputRecord`: canonical parsed throughput row.
- `ParseResult`: parser output with records and metadata.

The models use dataclasses, `pathlib.Path`, `datetime.date`, and
`datetime.time` where appropriate. A few model fields preserve compatibility
between earlier and current names, such as `canonical_id` and `report_id`.

## Exceptions

Package-specific exceptions live in `src/tsa_throughput/exceptions.py`.

Implemented exceptions:

- `TSAThroughputError`
- `TSAThroughputHTTPError`
- `DiscoveryError`
- `PaginationError`
- `NormalizationError`
- `DownloadError`
- `ManifestError`
- `StorageError`
- `ParserNotFoundError`
- `ParseError`

Library modules raise these exceptions. CLI commands catch
`TSAThroughputError`, print readable errors, and only show tracebacks when
`--debug` is supplied.

## Discovery Flow

Discovery lives in `src/tsa_throughput/discovery.py`.

Public function:

```python
discover_report_links(start_url=TSA_READING_ROOM_URL, max_pages=None, fetch_html=None)
```

Behavior:

1. Start from the TSA FOIA Reading Room throughput listing.
2. Fetch one page at a time.
3. Parse links with Beautiful Soup.
4. Keep links that are PDFs and look like TSA throughput reports.
5. Preserve the listing URL, page number, source filename, title, and absolute URL.
6. Follow a `next` pagination link until there is no next page or `max_pages` is reached.
7. Detect pagination loops.
8. De-duplicate report URLs.

The default fetcher uses `httpx`. Tests can inject `fetch_html` so default tests
do not need live TSA access.

## Normalization Flow

Normalization lives in `src/tsa_throughput/normalization.py`.

Public functions:

```python
normalize_report_link(raw)
normalize_report_links(raw_links)
```

Behavior:

1. Derive the source filename from the raw link or URL.
2. Extract date ranges from the link title and URL/path.
3. Validate extracted ranges before choosing canonical dates.
4. Store `week_start` and `week_end` when available.
5. Assign a date confidence:
   - `title_url_match`
   - `title_only`
   - `url_only`
   - `title_url_conflict`
   - `title_invalid_url_used`
   - `url_invalid_title_used`
   - `missing`
6. Build canonical IDs from week end dates:
   `tsa-throughput-week-ending-YYYY-MM-DD`.
7. Build canonical PDF filenames:
   `tsa-throughput-week-ending-YYYY-MM-DD.pdf`.
8. De-duplicate by canonical ID when dates are known.
9. Sort normalized reports newest first.

Date extraction supports full month-day-year ranges, compact legacy same-month
ranges such as `February 12-18, 2017`, and compact cross-month ranges such as
`February 26-March 4, 2017`. Ranges that go backward or are not close to a
weekly report period are treated as invalid and do not produce canonical IDs
when a better source is available.

When title and URL/filename dates are both valid but disagree, normalization
keeps conservative conflict behavior by default. A small exact filename override
table handles known TSA data errors where the filename period is the trusted
canonical report period. This includes selected malformed titles and legacy
`.xlsx.pdf` source filenames. Override cases are not marked as clean
`title_url_match` values.

If dates cannot be found, the report is still preserved with an unknown-date
canonical filename based on a sanitized source filename.

## Installed Source Manifest

The installed source manifest is packaged at:

```text
src/tsa_throughput/assets/source_manifest.json
```

Manifest helpers live in `src/tsa_throughput/source_manifest.py`.

Public functions:

```python
load_installed_source_manifest()
load_source_manifest(path)
save_source_manifest(manifest, path)
create_source_manifest(reports, generated_at=None)
refresh_source_manifest(output_path=None, max_pages=None, fetch_html=None, dry_run=False)
list_source_reports(manifest=None)
find_source_report(canonical_id, manifest=None)
```

The manifest schema records:

- `schema_version`
- `generated_at`
- source name and listing URL
- report canonical ID
- week start/end
- title
- source URL
- source filename
- canonical filename
- date confidence
- listing URL
- alternate URLs

The CLI uses this manifest for:

```bash
tsa-throughput download --from-installed-manifest --output-dir data/raw
```

The installed manifest is a known catalog of discovered TSA FOIA links, not a
guarantee that the live TSA site or every linked PDF is currently available.

Refresh behavior:

1. Discover raw FOIA report links with `discover_report_links()`.
2. Normalize and de-duplicate them with `normalize_report_links()`.
3. Create a `SourceManifest` sorted by week ending date descending.
4. Preserve alternate URLs and `date_confidence` values.
5. Write stable indented JSON only when an output path is supplied and
   `dry_run=False`.

The CLI command is:

```bash
tsa-throughput manifest refresh --output source_manifest.json
```

Only write to `src/tsa_throughput/assets/source_manifest.json` when intentionally
refreshing the committed installed asset. Non-clean date confidence values,
including `title_url_conflict`, should be reviewed before publishing. Default
tests use injected or monkeypatched discovery and must not require live TSA
network access.

## Local Storage

Local storage lives in `src/tsa_throughput/storage.py`.

Implemented objects:

- `Storage` protocol
- `LocalStorage`

`LocalStorage` creates a root directory, normalizes keys as relative POSIX-style
paths, rejects absolute paths and `..` path segments, and verifies resolved
paths stay inside the storage root.

Writes are performed through temporary files and then moved or linked into
place. Existing keys are rejected unless `overwrite=True`.

Only local filesystem storage is implemented.

## Downloader

Download behavior lives in `src/tsa_throughput/download.py`.

Public functions:

```python
download_report(report, storage, manifest_path=None, fetch_bytes=None, overwrite=False)
download_missing_reports(reports, storage, manifest_path=None, fetch_bytes=None, overwrite=False)
```

Behavior:

1. Require normalized report fields such as source URL, canonical ID, and
   canonical filename.
2. Load or create the runtime manifest.
3. Skip existing manifest entries and files unless `overwrite=True`.
4. Register an existing local PDF if the file exists but no manifest entry does.
5. Fetch PDF bytes through the default `httpx` fetcher or injected `fetch_bytes`.
6. Validate that downloaded content starts with `%PDF`.
7. Write through `LocalStorage`.
8. Compute SHA-256 and byte size.
9. Upsert the runtime manifest entry.

For `title_url_conflict` reports, the downloader avoids overwriting a different
source URL that maps to the same canonical filename unless `overwrite=True`.

## Runtime Download Manifest

Runtime manifest helpers live in `src/tsa_throughput/manifest.py`.

Default path:

```text
<output-dir>/manifest.json
```

Public functions:

```python
load_runtime_manifest(path)
save_runtime_manifest(manifest, path)
create_empty_runtime_manifest()
upsert_downloaded_report(manifest, entry)
find_manifest_entry(manifest, canonical_id)
```

Each entry records:

- canonical ID
- week start/end
- source URL
- source filename
- canonical filename
- local path
- SHA-256
- byte count
- download timestamp
- date confidence

The manifest is sorted and written as stable indented JSON.

## Parser Registry

Parser registry code lives in `src/tsa_throughput/parsing/registry.py`.

The parser manifest is packaged at:

```text
src/tsa_throughput/assets/parser_manifest.json
```

Public functions:

```python
load_parser_manifest(path=None)
list_parsers(path=None)
match_parser_manifest_entry(week_end, path=None)
get_parser(report, pdf_path, parser_name=None, manifest_path=None)
```

Selection behavior:

1. Load parser manifest entries.
2. If a parser name is provided, filter to that name.
3. Otherwise, filter by `report.week_end` when available.
4. Sort candidates by priority descending.
5. Import and instantiate each candidate parser.
6. Return the first parser whose `can_parse()` returns true.
7. Raise `ParserNotFoundError` if no parser can parse the report.

## Parser Plugins

Parser plugins implement `ThroughputParser` from
`src/tsa_throughput/parsing/base.py`.

Required interface:

```python
class ThroughputParser(ABC):
    parser_name: str
    parser_version: str
    layout_family: str

    def can_parse(self, report: ThroughputReport, pdf_path: Path) -> bool: ...
    def parse(self, source_file: Path, *, max_pages=None, report=None) -> ParseResult: ...
```

Current plugin:

```text
modern_total_pax_kcm_hourly_checkpoint_pdfplumber
```

Class:

```text
ModernTotalPaxKcmHourlyCheckpointPdfplumberParser
```

Supported layout:

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

The plugin uses `pdfplumber`, validates the modern header, forward-fills
date/hour/airport context fields, parses counts as integers, and raises
`ParseError` rather than guessing through unfamiliar tables.

## CLI Commands

The CLI lives in `src/tsa_throughput/cli.py`.

Implemented commands:

```bash
tsa-throughput discover [--latest | --all | --max-pages N] [--format text|json]
tsa-throughput download [--latest | --all | --max-pages N | --from-installed-manifest] --output-dir DIR [--overwrite]
tsa-throughput manifest refresh --output JSON [--max-pages N] [--dry-run] [--format text|json]
tsa-throughput parse PDF --output CSV [--max-pages N] [--parser NAME]
tsa-throughput parse-all --input-dir DIR --output CSV [--pattern GLOB] [--max-pages N] [--parser NAME] [--continue-on-error]
tsa-throughput parsers list
tsa-throughput parsers match --week-ending YYYY-MM-DD [--pdf-path PDF]
```

All commands that call package code support `--debug` for tracebacks.

The CLI writes parsed CSV with `CANONICAL_COLUMNS`:

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

## Parse-All Behavior

Batch parsing lives in `src/tsa_throughput/parsing/batch.py`.

Public function:

```python
parse_reports_in_directory(
    input_dir,
    pattern="*.pdf",
    max_pages=None,
    parser_name=None,
    continue_on_error=False,
)
```

Behavior:

1. Require `input_dir` to exist.
2. Find matching files using `Path.glob(pattern)`.
3. Process files in deterministic filename order.
4. Load `<input-dir>/manifest.json` if present.
5. Match manifest entries by local, source, or canonical filename.
6. Fall back to minimal report metadata inferred from
   `tsa-throughput-week-ending-YYYY-MM-DD.pdf`.
7. Select and run a parser for each PDF.
8. Stop at the first parser failure by default.
9. Continue and collect failures when `continue_on_error=True`.

The CLI writes the combined records only if at least one record is produced.

## Testing Approach

Tests live under `tests/`.

Current coverage includes:

- Models and exceptions.
- Local storage path safety and writes.
- Runtime manifest loading and saving.
- Source manifest loading.
- Discovery from saved listing fixtures.
- Report normalization.
- Downloader idempotency and manifest updates using injected PDF bytes.
- Parser registry and manifest loading.
- Modern parser behavior against the PDF fixture.
- CLI discovery, download, parse, parser inspection, and parse-all behavior.

Default tests should not make live network calls. Live tests, if added, should
be marked `integration` and require explicit opt-in such as:

```bash
TSA_THROUGHPUT_RUN_LIVE_TESTS=1 pytest -m integration
```

Routine verification:

```bash
pytest
ruff check .
```
