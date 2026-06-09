# Current Parser Plugin Notes

These notes document the currently implemented parser plugin.

## Parser Identity

Parser name:

```text
modern_total_pax_kcm_hourly_checkpoint_pdfplumber
```

Class name:

```text
ModernTotalPaxKcmHourlyCheckpointPdfplumberParser
```

Module:

```text
tsa_throughput.parsing.plugins.modern_total_pax_kcm_hourly_checkpoint_pdfplumber
```

Layout family:

```text
hourly_checkpoint_total_pax_kcm
```

Parser version:

```text
0.1.0
```

Metric name:

```text
total_pax_plus_kcm_pax
```

Metric source column:

```text
Total Pax + KCM PAX
```

Parse confidence for successfully parsed records:

```text
high
```

## Fixture

Primary parser fixture:

```text
tests/fixtures/tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf
```

Inspection summary fixture:

```text
tests/fixtures/pdfplumber_inspection_summary.json
```

The sample PDF covers:

```text
2026-05-31 through 2026-06-06
```

The inspected full sample has:

```text
987 pages
```

The first inspected pages each contain one useful main table with 8 columns and
about 53 extracted rows.

## Supported Layout

The parser supports the modern TSA hourly checkpoint-level layout with this
header:

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

The fourth column has a blank header in extracted tables. The implementation
maps that column by position to:

```text
airport_name
```

The parser validates the recognized header columns by position and requires 8
columns.

## pdfplumber Settings

The parser uses `pdfplumber` table extraction with line-based strategies:

```python
TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "intersection_tolerance": 3,
}
```

Inspection found that line-based extraction preserved the table grid well for
the fixture. Text-based extraction did not preserve the structure well enough
for the current parser.

## Column Mapping

Implemented source-to-canonical mapping:

```text
Date -> throughput_date
Hour of Day -> hour
Airport -> airport_code
[blank fourth column] -> airport_name
City -> city
State -> state
Checkpoint -> checkpoint_name
Total Pax + KCM PAX -> throughput_count
```

The parser normalizes:

- dates from `M/D/YYYY` to `datetime.date`
- hours from `HH:MM` to `datetime.time`
- airport codes to uppercase
- states to uppercase
- counts with optional commas to integers
- extracted text by stripping whitespace and replacing line breaks with spaces

## Forward-Fill Behavior

The source PDF visually merges repeated table cells. The parser keeps current
context and forward-fills these fields:

```text
throughput_date
hour
airport_code
airport_name
city
state
```

The parser does not forward-fill:

```text
checkpoint_name
throughput_count
```

A row with a blank airport code can inherit the current airport context. A row
with a checkpoint and count must still have date, hour, and airport context
available.

## Canonical Fields

Each successful record is a `ThroughputRecord` with the canonical parsed fields:

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

`week_start`, `week_end`, and `source_url` come from the optional
`ThroughputReport` passed into `parse()`. If no report metadata is supplied,
those fields may be empty.

## Fixture Expectations

Known first record from the fixture:

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

Known forward-fill expectation:

```text
airport_code = ATL
airport_name = Hartsfield - Jackson Atlanta International
city = Atlanta
state = GA
checkpoint_name = F Arrival Checkpoint
throughput_count = 4
```

Then a following row with blank airport context should inherit ATL metadata:

```text
airport_code = ATL
airport_name = Hartsfield - Jackson Atlanta International
city = Atlanta
state = GA
checkpoint_name = Main Checkpoint
throughput_count = 79
```

The fixture should parse at least the first five pages in tests. A one-page CLI
smoke parse currently produces 52 records.

## can_parse Behavior

`can_parse(report, pdf_path)` opens the PDF and checks up to the first five
pages. It returns true when at least one table matches the modern header. It
returns false for exceptions or non-matching layouts.

## Parse Failure Behavior

The parser raises `ParseError` when:

- no matching modern table is found on a processed page
- a table does not have 8 columns
- a required header column does not match the expected text
- a data row has an unexpected non-empty column count
- date, hour, or airport context is missing for a data row
- checkpoint is missing
- throughput count is missing
- throughput count is not numeric
- no records are produced

Errors include the parser name, source file, reason, and page/table details when
available.

## Current Limitations

- This plugin only supports the modern hourly checkpoint-level
  `Total Pax + KCM PAX` layout.
- It does not parse older TSA layouts with different metric columns.
- It does not attempt OCR.
- It does not repair malformed PDFs.
- It does not guess when the table header changes.
- Parser manifest validity begins at `2026-01-01`, but that is a conservative
  selection hint rather than a guarantee of coverage for every report after that
  date.

## Future Historical Parser Notes

Historical layouts should be implemented as separate parser plugins with their
own fixtures, manifest entries, and tests.

Known future direction:

```text
legacy_hourly_checkpoint_pdfplumber
```

Older layouts may include different fields such as:

```text
Hour
Metrics
PMIS - Total Customer Throughput (Unadjusted)
```

Those layouts should not be folded into the modern parser unless the source
tables are structurally compatible and well covered by fixtures.
