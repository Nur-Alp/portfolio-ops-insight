"""Date provenance helpers shared by source-backed exports and APIs."""

from __future__ import annotations

from datetime import date
import re


_DOTTED_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[._-](\d{1,2})[._-](\d{2}|\d{4})(?!\d)")
_ISO_DATE_RE = re.compile(r"(?<!\d)(\d{4})[._-](\d{1,2})[._-](\d{1,2})(?!\d)")
_COMPACT_DATE_RE = re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)")


def extract_filename_date(filename: str | None) -> date | None:
    """Extract a date-shaped token from a filename without making it authoritative.

    Source parsers deliberately read dates from workbook content.  This helper
    is only for provenance warnings when a human-entered filename disagrees
    with that internal date.  It supports dotted, ISO-like, and compact
    ``DDMMYYYY`` forms used by the supplied workbooks.
    """
    text = filename or ""
    # Check the unambiguous year-first form before the day-first expression;
    # the latter also accepts hyphens and would otherwise consume ``2026-07-01``
    # as day=2026 and fail before the ISO parser gets a chance.
    match = _ISO_DATE_RE.search(text)
    if match:
        year, month, day = (int(part) for part in match.groups())
    else:
        match = _DOTTED_DATE_RE.search(text)
        if match:
            day, month, year = (int(part) for part in match.groups())
            if year < 100:
                year += 2000
        else:
            match = _COMPACT_DATE_RE.search(text)
            if not match:
                return None
            day, month, year = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def filename_date_mismatch(filename: str | None, internal_date: date | None) -> bool:
    """Return whether a parseable filename date conflicts with workbook content."""
    filename_date = extract_filename_date(filename)
    return filename_date is not None and internal_date is not None and filename_date != internal_date


def filename_date_warning(filename: str | None, internal_date: date | None) -> str | None:
    """Return a localized warning string for an evidence-only mismatch."""
    filename_date = extract_filename_date(filename)
    if filename_date is None or internal_date is None or filename_date == internal_date:
        return None
    return (
        "Предупреждение: дата в имени файла "
        f"{filename_date:%d.%m.%Y} не совпадает с датой внутри книги "
        f"{internal_date:%d.%m.%Y}."
    )
