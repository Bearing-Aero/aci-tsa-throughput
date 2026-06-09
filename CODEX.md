# CODEX.md

## Project

`tsa-throughput` is a Python library and CLI for discovering, downloading,
tracking, and parsing TSA public FOIA checkpoint throughput PDF reports.

It is being developed in conjunction with ACI North America's Data Analytics
Working Group (DAWG) to support broader access to TSA throughput data.

Package/import name:

```text
tsa_throughput
```

Distribution and CLI name:

```text
tsa-throughput
```

Primary contact:

```text
joel@bearing.aero
```

## Development Environment

Use the existing Conda environment:

```bash
conda activate bearing-tsa
pip install -e ".[dev]"
```

If it must be recreated:

```bash
conda create -n bearing-tsa python=3.10
conda activate bearing-tsa
pip install -e ".[dev]"
```

Python support is `>=3.10`.

Common commands:

```bash
pytest
ruff check .
python -m build
```

Default tests must not require live network access.

## Normalization Edge Cases

`normalization.py` extracts report week ranges from titles and URL/filename
text, validates candidate ranges, and preserves visible `date_confidence`
markers when metadata is malformed or conflicting.

Supported date patterns include standard full ranges, compact legacy same-month
ranges such as `February 12-18, 2017`, and compact cross-month ranges such as
`February 26-March 4, 2017`. Impossible or non-weekly ranges are ignored when a
valid alternate source exists.

Known TSA title/filename conflicts where the filename is the trusted report
period are handled by exact filename overrides in `normalization.py`. Keep this
override list narrow and prefer exact `source_filename` keys. Source filenames
ending in `.xlsx.pdf` can still normalize to canonical `.pdf` filenames.

## Implemented Package Layout

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
    base.py
    batch.py
    registry.py
    plugins/
      modern_total_pax_kcm_hourly_checkpoint_pdfplumber.py
```

Core models in `models.py`:

- `RawReportLink`
- `ThroughputReport`
- `DownloadResult`
- `RuntimeManifestEntry`
- `RuntimeManifest`
- `SourceManifest`
- `ThroughputRecord`
- `ParseResult`

Package-specific exceptions live in `exceptions.py`, including discovery,
normalization, download, storage, manifest, parser selection, and parse errors.

## Implemented CLI

Implemented command families:

```bash
tsa-throughput discover
tsa-throughput download
tsa-throughput parse
tsa-throughput parse-all
tsa-throughput parsers list
tsa-throughput parsers match --week-ending 2026-06-06
tsa-throughput parsers coverage --input-dir data/raw
```

Important options:

- `discover`: `--latest`, `--all`, `--max-pages`, `--format text|json`, `--debug`
- `download`: `--latest`, `--all`, `--max-pages`, `--from-installed-manifest`,
  `--output-dir`, `--overwrite`, `--debug`
- `parse`: positional PDF path, `--output`, `--max-pages`, `--parser`, `--debug`
- `parse-all`: `--input-dir`, `--output`, `--pattern`, `--max-pages`,
  `--parser`, `--continue-on-error`, `--debug`
- `parsers match`: `--week-ending`, optional `--pdf-path`, `--debug`
- `parsers coverage`: `--input-dir`, `--pattern`, `--max-pages`,
  `--stop-on-first-error`, `--format text|json`, `--debug`

There are no implemented `manifest show` or `manifest refresh` CLI commands.

## Parser Architecture

Parsers implement `tsa_throughput.parsing.base.ThroughputParser`:

- `parser_name`
- `parser_version`
- `layout_family`
- `can_parse(report, pdf_path)`
- `parse(source_file, max_pages=None, report=None)`

The parser registry in `parsing/registry.py` loads
`assets/parser_manifest.json`, filters by week ending date when available, sorts
by priority, imports parser classes, and calls `can_parse()` before selecting a
parser.

Current installed parser:

```text
modern_total_pax_kcm_hourly_checkpoint_pdfplumber
```

Class:

```text
ModernTotalPaxKcmHourlyCheckpointPdfplumberParser
```

Layout family:

```text
hourly_checkpoint_total_pax_kcm
```

It supports the modern hourly checkpoint table with:

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

It uses `pdfplumber` line-based table extraction, maps the blank fourth header
column to `airport_name`, forward-fills date/hour/airport context fields, and
does not forward-fill `checkpoint_name` or `throughput_count`.

## Manifests

### Parser Manifest

Path:

```text
src/tsa_throughput/assets/parser_manifest.json
```

Purpose:

- Parser metadata.
- Import module and class.
- Valid date range.
- Priority.
- Layout family and description.

### Installed Source Manifest

Path:

```text
src/tsa_throughput/assets/source_manifest.json
```

Purpose:

- Packaged catalog of known TSA FOIA report links.
- Canonical report IDs and filenames.
- Week start/end dates.
- Source URLs and filenames.
- Date confidence and alternate URLs.

Use `source_manifest.py` APIs or
`tsa-throughput download --from-installed-manifest`.

### Runtime Download Manifest

Default path:

```text
<output-dir>/manifest.json
```

Purpose:

- Local record of downloaded PDFs.
- SHA-256 checksums.
- Byte sizes.
- Download timestamps.
- Source and canonical filenames.

`download.py` uses it for idempotent local downloads. `parse-all` reads it when
available to attach report metadata to parsed records.

## Implemented Flow

Discovery:

1. `discover_report_links()` fetches TSA FOIA listing pages, extracts PDF links,
   follows pagination, de-duplicates URLs, and returns `RawReportLink` objects.
2. `normalize_report_links()` extracts date ranges from titles/URLs, builds
   canonical IDs and filenames, applies narrow known-error overrides,
   de-duplicates by canonical report, and sorts newest first.

Download:

1. `download_missing_reports()` calls `download_report()` for each normalized
   report.
2. Downloads are written through `LocalStorage`.
3. PDF content is validated by header, SHA-256 is computed, and the runtime
   manifest is updated.
4. Existing manifest entries and files are skipped unless `overwrite=True`.

Parsing:

1. `get_parser()` selects a parser from the parser manifest.
2. The modern plugin parses matching tables into `ThroughputRecord` objects.
3. CLI output uses the canonical CSV columns from `cli.CANONICAL_COLUMNS`.
4. `parse-all` processes matching PDFs in deterministic filename order and can
   continue after parser failures when requested.
5. `parsers coverage` processes downloaded PDFs in reverse chronological order
   and reports the first parser coverage boundary for historical plugin work.

## Current Status

Implemented:

- Package skeleton, models, and exceptions.
- Modern TSA PDF parser plugin and tests.
- Parser manifest and registry.
- CLI parse command.
- CLI parser inspection commands.
- Safe local filesystem storage.
- Runtime download manifest.
- FOIA listing discovery.
- Report metadata normalization.
- Installed source manifest.
- Idempotent downloader.
- Discovery and download CLI commands.
- Parse-all CLI command.
- Parser coverage scanner and CLI command.

## Remaining Roadmap

- Use `tsa-throughput parsers coverage --input-dir data/raw --stop-on-first-error`
  to identify the next historical layout boundary, then add a focused parser
  plugin and fixture for that first failure PDF.
- Add source manifest refresh tooling if needed.
- Broaden parser manifests with conservative valid date ranges backed by tests.
- Add richer integration tests behind explicit live-network opt-in.
- Add downstream export/load helpers only after core parsing coverage is stable.

Non-goals for now:

- Cloud storage backends.
- Database loading.
- Hosted API.
- Dashboard/web application.
- Silent parsing guesses for unfamiliar PDF layouts.

## Development Notes

- Keep library code reusable; the CLI should stay a thin wrapper.
- Prefer small typed functions and dataclasses over unstructured dictionaries.
- Use `pathlib.Path`.
- Raise package-specific exceptions from library modules.
- Do not configure global logging in library code.
- Do not add live network requirements to default tests.
- Update docs and tests in the same task when behavior changes.
