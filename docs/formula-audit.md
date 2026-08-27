# Workbook formula-audit contract

Source workbooks are evidence, not an Excel calculation engine.  Every
non-OSIP dataset parsed from a workbook now carries `summary.formula_audit`.
The contract is shared by all domains and is also copied onto `sheet_evidence`
records where a sheet-level record exists.

For `.xlsx` sources the parser inspects formula text and the cached value saved
by Excel.  It reports:

- `formula_count`
- `blank_cached_formula_count`
- `formula_error_count`
- `error_value_count` (literal cached error values outside formula cells)
- `external_formula_count`
- `formula_status` (`ok`, `blank_cached_results`, `formula_errors`,
  `source_errors`, or `no_formulas`)
- `cached_result_status: inspected`
- `recalculation_status: not_performed`

For legacy `.xls` sources, BIFF formula records can be counted, but the reader
used for source rows does not expose reliable formula text or cached results.
The audit therefore reports `formula_records_detected`, while explicitly
setting `cached_result_status: not_exposed_by_reader` and
`recalculation_status: not_available`.  This is not a claim that the workbook
has no errors.

The application does not evaluate arbitrary formulas.  A known, approved
OSIP carrying-price formula may still be reproduced by the OSIP parser when a
legacy workbook has an invalid cached result; that targeted fallback remains
separate from this generic evidence audit.
