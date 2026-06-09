# Current Plugin Notes

## Purpose

These notes document the current first parser target for `tsa-throughput`.

The first parser should focus on the most recent known TSA throughput PDF layout and should not attempt to support historical layouts yet.

Historical formats should be added later as separate parser plugins once the modern parser is stable.

## Current Parser Target

Parser name:

```text
modern_total_pax_kcm_hourly_checkpoint_pdfplumber
```

Parser class:

```text
ModernTotalPaxKcmHourlyCheckpointPdfplumberParser
```

Layout family:

```text
hourly_checkpoint_total_pax_kcm
```

Recommended source file for development/testing:

```text
tests/fixtures/tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf
```

Recommended inspection summary fixture:

```text
tests/fixtures/pdfplumber_inspection_summary.json
```

## Source PDF Observations

The recent sample PDF is titled:

```text
TSA Total Throughput
```

The visible page-level report date in the sample is:

```text
6/8/2026
```

The report data itself covers a weekly range reflected in the source filename:

```text
May 31, 2026 to June 6, 2026
```

The inspected full sample PDF has:

```text
987 pages
```

The first five inspected pages each produced one useful main table when using `pdfplumber` line-based table extraction.

Observed useful extraction characteristics:

```text
one main table per page
53 rows per inspected page
8 columns per inspected page
```

## Recommended pdfplumber Settings

Use `pdfplumber` line-based table extraction.

```python
TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "intersection_tolerance": 3,
}
```

The following presets worked well during inspection:

```text
default
lines
lines_strict
```

Use `lines` for the first implementation because it is explicit and matches the visible table grid.

The following presets were not suitable for the first parser:

```text
text
mixed_vertical_lines_horizontal_text
```

The `text` preset split rows and headers poorly. The `mixed_vertical_lines_horizontal_text` preset separated some title/date content from the table body and did not preserve the full useful row structure for the main parser.

## Observed Table Header

The useful table extraction produces an 8-column table with this header:

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

The fourth column header is blank in the extracted table, but the column contains airport names.

Treat the blank fourth header column as:

```text
airport_name
```

## Column Mapping

Use this source-to-canonical mapping for the current plugin:

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

Because the airport name source column has a blank header, the plugin may map it by position instead of by header text.

Recommended positional mapping:

```python
COLUMN_INDEX_MAP = {
    0: "throughput_date",
    1: "hour",
    2: "airport_code",
    3: "airport_name",
    4: "city",
    5: "state",
    6: "checkpoint_name",
    7: "throughput_count",
}
```

## Metric Handling

The modern layout does not include a separate `Metrics` column.

The metric meaning is embedded in the throughput count column header.

Set:

```text
metric_name = total_pax_plus_kcm_pax
```

Set:

```text
metric_source_column = Total Pax + KCM PAX
```

## Forward-Fill Rules

PDF tables visually merge repeated cells. The parser should forward-fill context fields across rows.

Forward-fill these fields:

```text
throughput_date
hour
airport_code
airport_name
city
state
```

Do not forward-fill these fields:

```text
checkpoint_name
throughput_count
```

A row with a new airport code should update the airport context.

A row with a blank airport code but a checkpoint and count should inherit the previous airport context.

## Required Fields

The modern parser should require:

```text
throughput_date
hour
airport_code
checkpoint_name
throughput_count
source_file
source_page
source_table
parser_name
parser_version
```

The parser should fail clearly if any required field cannot be produced.

## Optional Fields

The modern parser should produce these fields when available:

```text
airport_name
city
state
week_start
week_end
source_url
parse_confidence
```

For the current PDF layout, `airport_name`, `city`, and `state` are expected to be available after forward-fill.

`week_start`, `week_end`, and `source_url` may come from the surrounding `ThroughputReport` metadata rather than the PDF table itself.

## Canonical Output Fields

The parser should return records using the canonical parsed output model:

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

## Expected First Records

The first parsed record from the sample PDF should be:

```text
throughput_date = 2026-05-31
hour = 00:00
airport_code = ANC
airport_name = Ted Stevens Anchorage International
city = Anchorage
state = AK
checkpoint_name = South Checkpoint
metric_name = total_pax_plus_kcm_pax
metric_source_column = Total Pax + KCM PAX
throughput_count = 208
source_page = 1
source_table = 1
parser_name = modern_total_pax_kcm_hourly_checkpoint_pdfplumber
parser_version = 0.1.0
parse_confidence = high
```

A useful forward-fill test case appears shortly after the first row.

For ATL, the parser should produce:

```text
airport_code = ATL
airport_name = Hartsfield - Jackson Atlanta International
city = Atlanta
state = GA
checkpoint_name = F Arrival Checkpoint
throughput_count = 4
```

Then a following row with only checkpoint/count should forward-fill the ATL metadata:

```text
airport_code = ATL
airport_name = Hartsfield - Jackson Atlanta International
city = Atlanta
state = GA
checkpoint_name = Main Checkpoint
throughput_count = 79
```

## Validation Rules

The plugin should validate that the extracted table looks like the modern layout before parsing.

At minimum, require:

```text
column count == 8
column 0 resembles Date
column 1 resembles Hour of Day
column 2 resembles Airport
column 4 resembles City
column 5 resembles State
column 6 resembles Checkpoint
column 7 resembles Total Pax + KCM PAX
```

Because column 3 has a blank header, validate it by position rather than by text.

The parser should reject tables where:

* the header is not recognized
* fewer than 8 columns are found
* no records are produced
* a required field cannot be normalized
* a throughput count is missing or non-numeric
* date or hour context is missing for a data row
* airport context is missing for a data row

## Normalization Rules

Normalize dates from:

```text
M/D/YYYY
```

to `datetime.date`.

Example:

```text
5/31/2026 -> date(2026, 5, 31)
```

Normalize hours from:

```text
HH:MM
```

to `datetime.time`.

Example:

```text
00:00 -> time(0, 0)
```

Normalize airport codes to uppercase.

Normalize states to uppercase.

Normalize throughput counts to integers.

Allow comma-separated counts.

Example:

```text
1,234 -> 1234
```

Strip whitespace from text fields.

Collapse internal whitespace caused by PDF extraction.

## Parse Confidence

Set:

```text
parse_confidence = high
```

when:

* the expected header is found
* required columns are mapped
* required fields normalize successfully
* at least one record is produced
* no required field is inferred from weak positional guessing except the known blank airport-name column

Raise a parse error rather than returning low-confidence records if the required structure is not detected.

## Parser Failure Behavior

Parser plugins should fail conservatively.

Do not guess through unfamiliar layouts.

If the table does not match the modern layout, raise a package-specific parse error so another parser plugin can be selected or developed.

Recommended exception:

```python
ParseError
```

The error message should include:

```text
source file
page number
table number, if available
parser name
reason for failure
```

## Tests to Implement

Create tests in:

```text
tests/test_modern_parser.py
```

Minimum tests:

1. Parser can parse the first five pages of the sample PDF.
2. `record_count > 0`.
3. First record matches:

   * date `2026-05-31`
   * hour `00:00`
   * airport `ANC`
   * checkpoint `South Checkpoint`
   * count `208`
4. ATL `Main Checkpoint` appears with count `79`.
5. ATL metadata is forward-filled correctly.
6. `metric_name == "total_pax_plus_kcm_pax"`.
7. `metric_source_column == "Total Pax + KCM PAX"`.
8. `parse_confidence == "high"`.
9. Parser fails clearly when the expected header is missing.
10. Parser does not forward-fill `checkpoint_name`.
11. Parser does not forward-fill `throughput_count`.

## Development Notes

Start with parsing only the first five pages during development.

Example CLI or test behavior:

```bash
tsa-throughput parse tests/fixtures/tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf \
  --output parsed_first_5_pages.csv \
  --max-pages 5
```

After the first five pages pass, run against the full PDF.

Expected full-file checks:

* Parsed dates should cover only `2026-05-31` through `2026-06-06`.
* Parsed hours should include `00:00` through `23:00`.
* No records should have missing `airport_code`.
* No records should have missing `checkpoint_name`.
* No records should have missing `throughput_count`.
* Counts should be integers.
* Source page should be populated for every record.

## Not in Scope for This Plugin

Do not attempt to support the 2017 legacy layout in this plugin.

The legacy format appears to use different fields, including:

```text
Hour
Metrics
PMIS - Total Customer Throughput (Unadjusted)
```

That should be handled later by a separate plugin.

Potential future parser name:

```text
legacy_hourly_checkpoint_pdfplumber
```

## Implementation Reminder

This file documents the current parser target only.

The full project design belongs in:

```text
docs/design.md
```

General Codex/project operating instructions belong in:

```text
CODEX.md
```
