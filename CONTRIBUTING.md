# Contributing to `tsa-throughput`

Thank you for your interest in contributing to `tsa-throughput`.

`tsa-throughput` is a Python library and command-line tool for discovering, downloading, tracking, and parsing TSA public FOIA checkpoint throughput reports. The project is intended to support airport analytics, research workflows, scheduled data pipelines, and local analysis.

This project is being developed in conjunction with ACI North America's Data Analytics Working Group (DAWG) to support broader access to and analysis of TSA throughput data.

## Ways to contribute

Useful contributions include:

* Reporting issues with TSA report discovery or downloads.
* Reporting PDF files that do not parse correctly.
* Adding parser support for historical TSA PDF layouts.
* Improving tests and fixtures.
* Improving documentation.
* Fixing bugs in normalization, manifests, CLI behavior, or parser selection.
* Proposing small, well-scoped enhancements.

## Development setup

Use a Python environment manager such as Conda, Miniconda, `venv`, `uv`, or another tool of your choice. The project supports Python 3.10 or newer.

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


## Project structure

The package uses a `src/` layout:

```text
src/
  tsa_throughput/
    discovery.py
    normalization.py
    download.py
    storage.py
    manifest.py
    source_manifest.py
    models.py
    exceptions.py
    cli.py
    parsing/
      base.py
      registry.py
      coverage.py
      plugins/
```

Tests are under:

```text
tests/
```

Fixtures are under:

```text
tests/fixtures/
```

## Development principles

Please keep contributions aligned with the project’s design:

* Build reusable library functions first.
* Keep CLI commands thin.
* Use typed, testable functions.
* Use `pathlib.Path` for filesystem paths.
* Use package-specific exceptions.
* Do not print from reusable library modules.
* Do not make live network calls in default tests.
* Avoid hidden global state.
* Avoid broad refactors in bug-fix pull requests.
* Prefer small, focused changes.

## Tests and fixtures

Default tests should not depend on live TSA network access.

Use saved HTML, PDF, JSON, or synthetic fixtures for tests. If live integration tests are added, they must be skipped by default and require an explicit environment variable, such as:

```bash
TSA_THROUGHPUT_RUN_LIVE_TESTS=1
```

Live tests should also be marked clearly, for example:

```bash
pytest -m integration
```

## Reporting parser issues

When reporting a PDF that does not parse correctly, please include:

* The TSA report title.
* The source URL.
* The source filename.
* The expected week start and week end dates, if known.
* The command you ran.
* The error message or incorrect output.
* Whether the file is discoverable from the TSA FOIA Reading Room.

Helpful example:

```text
Title: TSA Throughput Data to May 31, 2026 to June 6, 2026
Source filename: tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf
Expected week_start: 2026-05-31
Expected week_end: 2026-06-06
Command: tsa-throughput parse report.pdf --output report.csv
Problem: parser failed to recognize the table header
```

## Adding a parser plugin

TSA has changed PDF layouts over time. Parser support should be added through plugins rather than by making one parser handle every format.

A parser plugin should:

* Support one layout family.
* Define clear expected source columns.
* Map source fields to canonical output fields.
* Fail conservatively when the layout does not match.
* Include fixture-based tests.
* Be registered in `src/tsa_throughput/assets/parser_manifest.json`.
* Use a conservative date range based on actual fixtures and coverage results.

Parser plugins live under:

```text
src/tsa_throughput/parsing/plugins/
```

The standard parsed output fields are:

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

## Historical parser workflow

To extend historical parser coverage, use the parser coverage utility to work backward through downloaded PDFs:

```bash
tsa-throughput parsers coverage --input-dir data/raw --stop-on-first-error --max-pages 3
```

If a local corpus is not available, download one first:

```bash
tsa-throughput download --from-installed-manifest --output-dir data/raw
```

The preferred historical parser workflow is:

1. Run parser coverage.
2. Identify the first unsupported historical layout.
3. Inspect that PDF.
4. Implement one new parser plugin for that layout family.
5. Add a representative fixture.
6. Add parser tests.
7. Register the parser in the parser manifest.
8. Re-run coverage.
9. Repeat for the next layout boundary.

Do not add a broad, speculative parser for uninspected historical formats.

## Normalization edge cases

TSA report titles and filenames sometimes contain typos or inconsistent dates. Normalization changes should be conservative and test-driven.

When fixing a title or filename issue:

* Add a regression test with the exact title and filename.
* Preserve the original title and source filename.
* Do not silently mark conflicting metadata as clean.
* Prefer general parsing rules for recognizable patterns.
* Use explicit overrides only for true one-off TSA data errors.

## Pull request checklist

Before submitting a pull request:

* Run `pytest`.
* Run `ruff check .`.
* Add or update tests for behavior changes.
* Update documentation if user-facing behavior changed.
* Keep the change focused.
* Avoid live network calls in tests.
* Confirm parser changes do not break existing parser fixtures.

## Documentation updates

Update documentation when changing:

* CLI commands.
* Public Python APIs.
* Parser behavior.
* Manifest formats.
* Output schema.
* Development workflow.
* Supported parser coverage.

Relevant files may include:

```text
README.md
CODEX.md
docs/design.md
docs/current_plugin_notes.md
CHANGELOG.md
```

## Code style

Use clear, boring Python.

Prefer:

* small functions
* dataclasses
* explicit names
* type hints
* package-specific exceptions
* deterministic ordering
* readable tests

Avoid:

* one giant scraper function
* broad parser guesses
* silent failures
* unstructured dictionaries as the main API
* adding dependencies without a clear need
* mixing CLI behavior into reusable library modules

## Questions and issues

For bugs, parser failures, or feature requests, please open an issue with enough detail to reproduce the behavior.

For parser failures, include the TSA source title, filename, URL, and expected date range whenever possible.
