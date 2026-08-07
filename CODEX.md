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

Use a Python environment manager such as Conda, Miniconda, `venv`, `uv`, or
another tool of your choice. The project supports Python 3.10 or newer.

Example using Conda:

```bash
conda create -n tsa-throughput python=3.10
conda activate tsa-throughput
pip install -e ".[dev]"
```

Example using `venv`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

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
    coverage.py
    registry.py
    plugins/
      historical_2015_hour_of_day_pmis_pdfplumber.py
      historical_early_hour_header_pmis_pdfplumber.py
      historical_early_hour_of_day_pmis_pdfplumber.py
      historical_embedded_hour_merged_header_pmis_pdfplumber.py
      historical_hour_header_pmis_pdfplumber.py
      historical_legacy_pmis_split_year_dates_pdfplumber.py
      historical_march_2022_total_pax_kcm_hourly_checkpoint_pdfplumber.py
      historical_merged_header_pmis_pdfplumber.py
      historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber.py
      historical_total_pax_kcm_hourly_checkpoint_pdfplumber.py
      historical_total_pax_kcm_hourly_checkpoint_strict_pdfplumber.py
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
tsa-throughput manifest refresh --output source_manifest.json
tsa-throughput parse
tsa-throughput parse-all
tsa-throughput parsers list
tsa-throughput parsers match --week-ending 2026-06-06
tsa-throughput parsers coverage --input-dir data/raw
```

Important options:

- `discover`: `--latest`, `--all`, `--max-pages`, `--format text|json`, `--debug`
- `download`: `--latest`, `--all`, `--max-pages`, `--from-installed-manifest`,
  `--from-source-manifest`, `--output-dir`, `--overwrite`, `--debug`
- `manifest refresh`: `--output`, `--max-pages`, `--dry-run`,
  `--format text|json`, `--debug`
- `parse`: positional PDF path, `--output`, `--max-pages`, `--parser`, `--debug`
- `parse-all`: `--input-dir`, `--output`, `--pattern`, `--max-pages`,
  `--parser`, `--continue-on-error`, `--debug`
- `parsers match`: `--week-ending`, optional `--pdf-path`, `--debug`
- `parsers coverage`: `--input-dir`, `--pattern`, `--max-pages`,
  `--stop-on-first-error`, `--format text|json`, `--debug`

There is no implemented `manifest show` CLI command.

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

Current installed parsers:

```text
modern_total_pax_kcm_hourly_checkpoint_pdfplumber
historical_total_pax_kcm_hourly_checkpoint_pdfplumber
historical_total_pax_kcm_hourly_checkpoint_strict_pdfplumber
historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber
historical_legacy_pmis_split_year_dates_pdfplumber
historical_merged_header_pmis_pdfplumber
historical_embedded_hour_merged_header_pmis_pdfplumber
historical_hour_header_pmis_pdfplumber
historical_early_hour_of_day_pmis_pdfplumber
historical_early_hour_header_pmis_pdfplumber
historical_2015_hour_of_day_pmis_pdfplumber
historical_march_2022_total_pax_kcm_hourly_checkpoint_pdfplumber
```

The 12 parser implementations are registered through 14 manifest entries because
the legacy split-year PMIS parser and the standard historical PMIS parser each
cover two non-contiguous date windows. Current manifest coverage is:

| Parser | Valid week-ending dates |
| --- | --- |
| `historical_2015_hour_of_day_pmis_pdfplumber` | `2015-01-10` through `2015-01-27` |
| `historical_early_hour_header_pmis_pdfplumber` | `2017-01-21` through `2017-01-28` |
| `historical_early_hour_of_day_pmis_pdfplumber` | `2017-02-04` |
| `historical_hour_header_pmis_pdfplumber` | `2017-02-11` through `2017-10-07` |
| `historical_embedded_hour_merged_header_pmis_pdfplumber` | `2017-10-14` |
| `historical_legacy_pmis_split_year_dates_pdfplumber` | `2017-10-21` through `2018-06-23`; `2018-07-07` through `2022-01-01` |
| `historical_merged_header_pmis_pdfplumber` | `2018-06-30` |
| `historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber` | `2022-01-08` through `2022-02-26`; `2022-04-02` |
| `historical_march_2022_total_pax_kcm_hourly_checkpoint_pdfplumber` | `2022-03-05` through `2022-03-26` |
| `historical_total_pax_kcm_hourly_checkpoint_strict_pdfplumber` | `2022-04-09` through `2022-12-31` |
| `historical_total_pax_kcm_hourly_checkpoint_pdfplumber` | `2023-01-07` through `2025-12-20` |
| `modern_total_pax_kcm_hourly_checkpoint_pdfplumber` | `2025-12-27` onward |

The plugins support two source metrics:

- `Total Pax + KCM PAX`, normalized as `total_pax_plus_kcm_pax`.
- `PMIS - Total Customer Throughput (Unadjusted)`, normalized as
  `pmis_total_customer_throughput_unadjusted`.

The modern Total Pax + KCM PAX table has:

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

PMIS tables add a `Metrics` column and use the PMIS count column. Historical
plugins isolate extraction differences such as strict line settings, shortened
`Hour` headers, split year digits, and data embedded in table headers. Parsers
forward-fill date/hour/airport context where the layout requires it, but do not
guess missing checkpoint names or throughput counts. Manifest boundaries are
fixture-backed and conservative; a matching date window is still validated by
the parser's `can_parse()` method.

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

Refresh workflow:

```bash
tsa-throughput manifest refresh --output source_manifest.json
tsa-throughput manifest refresh --output source_manifest.json --max-pages 3
tsa-throughput manifest refresh --output source_manifest.json --dry-run
tsa-throughput manifest refresh --output source_manifest.json --format json
```

Only write to `src/tsa_throughput/assets/source_manifest.json` when the committed
installed manifest should be intentionally updated. Treat the installed source
manifest as a known catalog, not a guarantee of live TSA availability. Review
non-clean `date_confidence` values before publishing a refreshed manifest.

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

Source manifest refresh:

1. `refresh_source_manifest()` composes discovery, normalization, manifest
   creation, and optional manifest writing.
2. The CLI command writes stable indented JSON to the requested output path
   unless `--dry-run` is supplied.
3. Refresh tests must use fixture-backed or monkeypatched discovery and must not
   require live TSA network access.

Download:

1. `download_missing_reports()` calls `download_report()` for each normalized
   report.
2. Downloads are written through `LocalStorage`.
3. PDF content is validated by header, SHA-256 is computed, and the runtime
   manifest is updated.
4. Existing manifest entries and files are skipped unless `overwrite=True`.

Parsing:

1. `get_parser()` selects a parser from the parser manifest.
2. The selected plugin parses matching tables into `ThroughputRecord` objects
   while preserving source page, table, parser identity, and parse confidence.
3. CLI output uses the canonical CSV columns from `cli.CANONICAL_COLUMNS`.
4. `parse-all` processes matching PDFs in deterministic filename order and can
   continue after parser failures when requested.
5. Historical parser work first ensures a real local PDF corpus exists. Use
   `tsa-throughput download --from-installed-manifest --output-dir data/raw` to
   create or update `data/raw` and `data/raw/manifest.json`; if the installed
   manifest is stale, refresh `data/source_manifest.json` and download with
   `tsa-throughput download --from-source-manifest data/source_manifest.json --output-dir data/raw`.
6. `parsers coverage` processes downloaded PDFs in reverse chronological order
   and reports the first parser coverage boundary for historical plugin work.

## Current Status

Implemented:

- Package skeleton, models, and exceptions.
- Twelve TSA PDF parser plugins covering the known modern and historical layout
  families in the installed source catalog, with fixture-backed tests.
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
- Source manifest refresh API and CLI command.
- Parse-all CLI command.
- Parser coverage scanner and CLI command.

## Remaining Roadmap

- Keep the local PDF corpus synchronized with the installed or a freshly
  generated source manifest before running coverage scans.
- Re-run `tsa-throughput parsers coverage --input-dir data/raw` whenever the
  catalog grows or TSA introduces a new layout. Add a focused plugin and fixture
  for the first confirmed failure rather than broadening an existing parser
  speculatively.
- Keep parser date windows conservative and backed by fixtures and coverage
  results.
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
