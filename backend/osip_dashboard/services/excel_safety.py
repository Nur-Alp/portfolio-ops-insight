"""Guard against formula injection when re-exporting source-workbook text.

Source workbooks are uploaded by back-office actors and may contain
free-text fields (issuer names, client names, comments) copied from
external systems. openpyxl auto-detects any string cell value starting
with ``=`` as a live formula (see ``Cell._bind_value``), so re-exporting
such a value verbatim into a "controlled" report would ship a live
formula that executes when an approver or publisher opens it in Excel.
None of this application's exports ever write an intentional formula, so
resetting every auto-detected formula cell back to a plain string is safe
across the board.

CSV exports carry the same risk in a more exposed form: a .csv file has
no cell-type metadata at all, so Excel decides purely from a cell's
leading character whether to treat it as a formula when the file is
opened, regardless of what the value actually is.
"""

from __future__ import annotations

import csv
import re
from typing import IO, Any, Iterable

from openpyxl import Workbook


def neutralize_formulas(workbook: Workbook) -> None:
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    cell.data_type = "s"


_CSV_FORMULA_TRIGGER = re.compile(r"^[=+\-@]")
_CSV_PLAIN_SIGNED_NUMBER = re.compile(r"^[+-]?\d+(\.\d+)?$")


def _sanitize_csv_value(value: Any) -> Any:
    # Only strings can carry a formula trigger; a plain signed number
    # (e.g. a negative settlement amount rendered as text) is left alone
    # so real financial figures are never visually corrupted.
    if isinstance(value, str) and _CSV_FORMULA_TRIGGER.match(value) and not _CSV_PLAIN_SIGNED_NUMBER.match(value):
        return "'" + value
    return value


class SafeCsvWriter:
    """Drop-in wrapper for ``csv.writer`` that defuses formula triggers."""

    def __init__(self, output: IO[str]):
        self._writer = csv.writer(output)

    def writerow(self, row: Iterable[Any]) -> None:
        self._writer.writerow([_sanitize_csv_value(value) for value in row])

    def writerows(self, rows: Iterable[Iterable[Any]]) -> None:
        for row in rows:
            self.writerow(row)
