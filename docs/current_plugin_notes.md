# Current Parser Plugin Notes

These notes document the currently implemented parser plugins.

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

## Historical Parser Identity

Parser name:

```text
historical_total_pax_kcm_hourly_checkpoint_pdfplumber
```

Class name:

```text
HistoricalTotalPaxKcmHourlyCheckpointPdfplumberParser
```

Module:

```text
tsa_throughput.parsing.plugins.historical_total_pax_kcm_hourly_checkpoint_pdfplumber
```

Layout family:

```text
hourly_checkpoint_total_pax_kcm
```

Supported date range:

```text
2023-01-07 through 2025-12-20
```

The historical parser uses the same 8-column `Total Pax + KCM PAX` table
structure as the modern parser, but has its own parser identity and conservative
manifest date range.

## Strict Historical Parser Identity

Parser name:

```text
historical_total_pax_kcm_hourly_checkpoint_strict_pdfplumber
```

Class name:

```text
HistoricalTotalPaxKcmHourlyCheckpointStrictPdfplumberParser
```

Module:

```text
tsa_throughput.parsing.plugins.historical_total_pax_kcm_hourly_checkpoint_strict_pdfplumber
```

Layout family:

```text
hourly_checkpoint_total_pax_kcm_strict_lines
```

Supported date range:

```text
2022-04-09 through 2022-12-31
```

The strict historical parser uses the same `Total Pax + KCM PAX` column mapping,
but requires stricter pdfplumber line settings to avoid an extra blank column in
the extracted table.

## PMIS Historical Parser Identity

Parser name:

```text
historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber
```

Class name:

```text
HistoricalPmisTotalCustomerThroughputHourlyCheckpointPdfplumberParser
```

Module:

```text
tsa_throughput.parsing.plugins.historical_pmis_total_customer_throughput_hourly_checkpoint_pdfplumber
```

Layout family:

```text
hourly_checkpoint_pmis_total_customer_throughput
```

Supported date range:

```text
2022-01-08 through 2022-02-26
2022-04-02 through 2022-04-02
```

Metric name:

```text
pmis_total_customer_throughput_unadjusted
```

Metric source column:

```text
PMIS - Total Customer Throughput (Unadjusted)
```

The PMIS historical parser handles a 9-column layout with a `Metrics` column and
the PMIS total customer throughput count column. Local coverage verifies the
same layout for week endings `2022-01-08` through `2022-02-26` and again at
`2022-04-02`; the manifest uses separate entries because the intervening March
2022 reports use the separate Total Pax + KCM PAX parser.

## Legacy PMIS Split-Year Parser Identity

Parser name:

```text
historical_legacy_pmis_split_year_dates_pdfplumber
```

Class name:

```text
HistoricalLegacyPmisSplitYearDatesPdfplumberParser
```

Module:

```text
tsa_throughput.parsing.plugins.historical_legacy_pmis_split_year_dates_pdfplumber
```

Layout family:

```text
hourly_checkpoint_pmis_total_customer_throughput_split_year_dates
```

Supported date range:

```text
2017-10-21 through 2018-06-23
2018-07-07 through 2022-01-01
```

The legacy PMIS split-year parser handles the same 9-column PMIS layout as the
PMIS historical parser, but tolerates date cells where pdfplumber splits the
final year digit, such as `12/26/202 1`. It only repairs that narrow pattern and
otherwise fails conservatively.

## Merged-Header PMIS Parser Identity

Parser name:

```text
historical_merged_header_pmis_pdfplumber
```

Class name:

```text
HistoricalMergedHeaderPmisPdfplumberParser
```

Module:

```text
tsa_throughput.parsing.plugins.historical_merged_header_pmis_pdfplumber
```

Layout family:

```text
hourly_checkpoint_pmis_total_customer_throughput_merged_header
```

Supported date range:

```text
2018-06-30 through 2018-06-30
```

The merged-header PMIS parser handles a one-week extraction anomaly where the
first data row is merged into the table header, with `Date`/`Day` replacing the
clean `Date`/`Hour of Day` header. It carries date, hour, and airport context
across page breaks because the extracted table can begin mid-hour or mid-airport.

## Embedded-Hour Merged-Header PMIS Parser Identity

Parser name:

```text
historical_embedded_hour_merged_header_pmis_pdfplumber
```

Class name:

```text
HistoricalEmbeddedHourMergedHeaderPmisPdfplumberParser
```

Module:

```text
tsa_throughput.parsing.plugins.historical_embedded_hour_merged_header_pmis_pdfplumber
```

Layout family:

```text
hourly_checkpoint_pmis_total_customer_throughput_embedded_hour_merged_header
```

Supported date range:

```text
2017-10-14 through 2017-10-14
```

The embedded-hour merged-header PMIS parser handles a one-week extraction
anomaly where the first data row is merged into the table header and the
`Day` header cell also contains the first hour value. It is registered
separately from the 2018 merged-header parser because the airport code is
embedded inside the airport-name header value instead of leading that value.

## Hour-Header PMIS Parser Identity

Parser name:

```text
historical_hour_header_pmis_pdfplumber
```

Class name:

```text
HistoricalHourHeaderPmisPdfplumberParser
```

Module:

```text
tsa_throughput.parsing.plugins.historical_hour_header_pmis_pdfplumber
```

Layout family:

```text
hourly_checkpoint_pmis_total_customer_throughput_hour_header
```

Supported date range:

```text
2017-02-11 through 2017-10-07
```

The hour-header PMIS parser handles the same 9-column PMIS table as the later
PMIS parser, but accepts the shortened `Hour` column header instead of
`Hour of Day`. It is registered separately to keep the older header contract
explicit and conservative.

## Early Hour-of-Day PMIS Parser Identity

Parser name:

```text
historical_early_hour_of_day_pmis_pdfplumber
```

Class name:

```text
HistoricalEarlyHourOfDayPmisPdfplumberParser
```

Module:

```text
tsa_throughput.parsing.plugins.historical_early_hour_of_day_pmis_pdfplumber
```

Layout family:

```text
hourly_checkpoint_pmis_total_customer_throughput_early_hour_of_day
```

Supported date range:

```text
2017-02-04 through 2017-02-04
```

The early Hour-of-Day PMIS parser handles the same PMIS source column as the
later PMIS parser, but is registered separately because this local boundary
report spans `2017-01-15` through `2017-02-04` and interrupts the neighboring
shortened-`Hour` layout range.

## Early Hour-Header PMIS Parser Identity

Parser name:

```text
historical_early_hour_header_pmis_pdfplumber
```

Class name:

```text
HistoricalEarlyHourHeaderPmisPdfplumberParser
```

Module:

```text
tsa_throughput.parsing.plugins.historical_early_hour_header_pmis_pdfplumber
```

Layout family:

```text
hourly_checkpoint_pmis_total_customer_throughput_early_hour_header
```

Supported date range:

```text
2017-01-21 through 2017-01-28
```

The early hour-header PMIS parser handles the same shortened `Hour` PMIS header
as the later hour-header parser, but is registered separately because the local
corpus has an intervening `2017-02-04` Hour-of-Day PMIS report.

## 2015 Hour-of-Day PMIS Parser Identity

Parser name:

```text
historical_2015_hour_of_day_pmis_pdfplumber
```

Class name:

```text
Historical2015HourOfDayPmisPdfplumberParser
```

Module:

```text
tsa_throughput.parsing.plugins.historical_2015_hour_of_day_pmis_pdfplumber
```

Layout family:

```text
hourly_checkpoint_pmis_total_customer_throughput_2015_hour_of_day
```

Supported date range:

```text
2015-01-10 through 2015-01-27
```

The 2015 Hour-of-Day PMIS parser handles the two locally available 2015 PMIS
reports. It uses the same PMIS source column as later PMIS parsers and keeps a
separate identity because the local corpus jumps from January 2015 to January
2017.

## March 2022 Historical Parser Identity

Parser name:

```text
historical_march_2022_total_pax_kcm_hourly_checkpoint_pdfplumber
```

Class name:

```text
HistoricalMarch2022TotalPaxKcmHourlyCheckpointPdfplumberParser
```

Module:

```text
tsa_throughput.parsing.plugins.historical_march_2022_total_pax_kcm_hourly_checkpoint_pdfplumber
```

Layout family:

```text
hourly_checkpoint_total_pax_kcm_march_2022
```

Supported date range:

```text
2022-03-05 through 2022-03-26
```

The March 2022 historical parser handles an 8-column `Total Pax + KCM PAX`
layout. It is registered separately because local coverage shows neighboring
week ending `2022-04-02` uses the PMIS 9-column layout, while week ending
`2022-02-26` returns to the PMIS layout and should be handled as a separate
boundary.

## Fixture

Primary parser fixture:

```text
tests/fixtures/tsa-throughput-data-to-may-31-2026-to-june-6-2026.pdf
```

Verified boundary fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2025-12-27.pdf
```

Historical parser representative fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2025-12-20.pdf
```

Historical parser start-boundary fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2023-01-07.pdf
```

Strict historical parser representative fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2022-12-31.pdf
```

Strict historical parser start-boundary fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2022-04-09.pdf
```

PMIS historical parser representative fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2022-04-02.pdf
```

PMIS historical parser early-boundary fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2022-02-26.pdf
```

PMIS historical parser start-boundary fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2022-01-08.pdf
```

Legacy PMIS split-year representative fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2022-01-01.pdf
```

Legacy PMIS split-year start-boundary fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2017-10-21.pdf
```

Merged-header PMIS representative fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2018-06-30.pdf
```

Embedded-hour merged-header PMIS representative fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2017-10-14.pdf
```

Hour-header PMIS representative fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2017-10-07.pdf
```

Hour-header PMIS start-boundary fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2017-02-11.pdf
```

Early Hour-of-Day PMIS representative fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2017-02-04.pdf
```

Early hour-header PMIS representative fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2017-01-28.pdf
```

Early hour-header PMIS start-boundary fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2017-01-21.pdf
```

2015 Hour-of-Day PMIS representative fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2015-01-27.pdf
```

2015 Hour-of-Day PMIS start-boundary fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2015-01-10.pdf
```

March 2022 historical parser representative fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2022-03-26.pdf
```

March 2022 historical parser start-boundary fixture:

```text
tests/fixtures/tsa-throughput-week-ending-2022-03-05.pdf
```

## Known Historical Boundary

All locally available PDFs in `data/raw` parse successfully through week ending
`2015-01-10`. No next local uncovered boundary was found by the latest parser
coverage scan.

Inspection summary fixture:

```text
tests/fixtures/pdfplumber_inspection_summary.json
```

The sample PDF covers:

```text
2026-05-31 through 2026-06-06
```

The boundary fixture covers:

```text
2025-12-21 through 2025-12-27
```

The historical parser fixtures cover:

```text
2025-12-14 through 2025-12-20
2023-01-01 through 2023-01-07
```

The strict historical parser fixtures cover:

```text
2022-12-25 through 2022-12-31
2022-04-03 through 2022-04-09
```

The PMIS historical parser fixture covers:

```text
2022-03-27 through 2022-04-02
```

The legacy PMIS split-year parser fixtures cover:

```text
2021-12-26 through 2022-01-01
2017-10-15 through 2017-10-21
```

The merged-header PMIS parser fixture covers:

```text
2018-06-24 through 2018-06-30
```

The embedded-hour merged-header PMIS parser fixture covers:

```text
2017-10-08 through 2017-10-14
```

The hour-header PMIS parser fixtures cover:

```text
2017-10-01 through 2017-10-07
2017-02-05 through 2017-02-11
```

The early Hour-of-Day PMIS parser fixture covers:

```text
2017-01-15 through 2017-02-04
```

The early hour-header PMIS parser fixtures cover:

```text
2017-01-22 through 2017-01-28
2017-01-15 through 2017-01-21
```

The 2015 Hour-of-Day PMIS parser fixtures cover:

```text
2015-01-21 through 2015-01-27
2015-01-04 through 2015-01-10
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

- These plugins only support the hourly checkpoint-level `Total Pax + KCM PAX`
  layout and selected PMIS hourly checkpoint layouts.
- They do not parse older TSA layouts with different table/header structures.
- They do not attempt OCR.
- They do not repair malformed PDFs.
- They do not guess when the table header changes.
- Parser manifest validity begins at week ending `2025-12-27`, backed by the
  modern boundary fixture and local coverage scan.
- The historical plugin supports week ending `2023-01-07` through
  `2025-12-20`, backed by local coverage scan and fixtures at both ends of the
  range.
- The strict historical plugin supports week ending `2022-04-09` through
  `2022-12-31`, backed by local coverage scan and fixtures at both ends of the
  range.
- The PMIS historical plugin supports week endings `2022-01-08` through
  `2022-02-26` and `2022-04-02`, backed by local coverage scan and fixtures.
- The legacy PMIS split-year plugin supports week endings `2017-10-21` through
  `2018-06-23` and `2018-07-07` through `2022-01-01`, backed by local coverage
  scan and fixtures.
- The merged-header PMIS plugin supports week ending `2018-06-30`, backed by
  local coverage scan and its representative fixture.
- The embedded-hour merged-header PMIS plugin supports week ending
  `2017-10-14`, backed by local coverage scan and its representative fixture.
- The hour-header PMIS plugin supports week endings `2017-02-11` through
  `2017-10-07`, backed by local coverage scan and fixtures at both ends of the
  range.
- The early Hour-of-Day PMIS plugin supports week ending `2017-02-04`, backed
  by local coverage scan and its representative fixture.
- The early hour-header PMIS plugin supports week endings `2017-01-21` through
  `2017-01-28`, backed by local coverage scan and fixtures at both ends of the
  range.
- The 2015 Hour-of-Day PMIS plugin supports week endings `2015-01-10` through
  `2015-01-27`, backed by local coverage scan and fixtures at both ends of the
  range.
- The March 2022 historical plugin supports week ending `2022-03-05` through
  `2022-03-26`, backed by local coverage scan and fixtures at both ends of the
  range.
- No next uncovered local boundary was found in `data/raw`.

## Future Historical Parser Notes

Historical layouts should be implemented as separate parser plugins with their
own fixtures, manifest entries, and tests.

Use the parser coverage scanner against a downloaded corpus to find the next
boundary before implementing a historical plugin:

```bash
tsa-throughput download --from-installed-manifest --output-dir data/raw
tsa-throughput parsers coverage --input-dir data/raw --stop-on-first-error
```

If the installed source manifest is stale or incomplete, refresh a development
manifest first and download from that file:

```bash
tsa-throughput manifest refresh --output data/source_manifest.json --max-pages 30
tsa-throughput download --from-source-manifest data/source_manifest.json --output-dir data/raw
tsa-throughput parsers coverage --input-dir data/raw --stop-on-first-error --max-pages 3
```

The downloader preserves `data/raw/manifest.json` and skips already downloaded
PDFs on repeated runs unless `--overwrite` is supplied. Parser coverage should
not be used to infer historical gaps from fixtures alone; real local TSA PDFs
are required for parser development.

The first failure after one or more successful modern parses is the best
candidate PDF for the next fixture and parser plugin.

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
