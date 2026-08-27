"""Deterministic ISIN dictionary supplied by the portfolio team.

The dictionary is a presentation/classification aid. It never overwrites the
raw workbook values; callers may fall back to the parsed source when an ISIN is
not present.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# The packaged default is git-tracked source and stays read-only: an upload
# never writes here. Uploaded replacements live in a separate runtime
# directory (configured per app instance, see configure_reference_data_root)
# so a bad upload can never dirty the repo's tracked file and a redeploy
# without that runtime directory cleanly reverts to the packaged default.
REQUIRED_COLUMNS = ("ISIN", "Класс актива", "Class", "Rating group", "Focus/sector/factor")

DICTIONARY_PATH = Path(__file__).resolve().parent.parent / "data" / "classes_and_ratings.csv"
_override_path: Path | None = None


class DictionaryValidationError(ValueError):
    """The uploaded dictionary file is missing columns or has no usable rows."""


def configure_reference_data_root(root: Path | None) -> None:
    """Point uploaded-dictionary storage at `root`; called once per app instance.

    Also clears the cached dictionary, so a previously-created app/test
    instance's uploaded dictionary never leaks into a new one that happens
    to share this worker process.
    """
    global _override_path
    _override_path = (root / "classes_and_ratings.csv") if root is not None else None
    instrument_dictionary.cache_clear()


def dictionary_source_path() -> Path:
    if _override_path is not None and _override_path.exists():
        return _override_path
    return DICTIONARY_PATH


@lru_cache(maxsize=1)
def instrument_dictionary() -> dict[str, dict[str, str]]:
    with dictionary_source_path().open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            row["ISIN"].strip().upper(): {key: (value or "").strip() for key, value in row.items()}
            for row in csv.DictReader(handle)
            if row.get("ISIN")
        }


def instrument_class(isin: str | None) -> str | None:
    row = instrument_dictionary().get((isin or "").strip().upper())
    return row.get("Class") if row else None


def instrument_rating_group(isin: str | None) -> str | None:
    row = instrument_dictionary().get((isin or "").strip().upper())
    return row.get("Rating group") if row else None


def instrument_focus(isin: str | None) -> str | None:
    row = instrument_dictionary().get((isin or "").strip().upper())
    return row.get("Focus/sector/factor") if row else None


_TRUE_CLASS_BY_SECURITY = {
    # The OSIP workbook labels these exchange-traded funds as «АКЦИИ»/ETF,
    # while their stated underlying sector is government bonds.  Keep this
    # small source-backed map explicit and auditable; unknown ETFs remain ETF.
    "SGOV": "Government bond",
    "TIP": "Government bond",
    "SPTL": "Government bond",
    "SCHQ": "Government bond",
}

_DICTIONARY_CLASS_MAP = {
    "Government bonds": "Government bond",
    "Corporate bonds": "Corporate bond",
    "Supranational bonds": "Corporate bond",
    "Equities": "Equity",
    "Repo": "Repo",
}


def true_asset_class(
    normalized_asset_class: str,
    raw_security_type: str,
    raw_sector: str,
    security_code: str,
    dictionary_class: str | None = None,
) -> str:
    """Return the economic class used in allocation/risk views.

    The parser's normalized class describes the workbook section (e.g. ETF),
    not necessarily the underlying exposure. Government-bond ETF identifiers
    are therefore reclassified using their stable source instrument code;
    other ETFs remain equities only when the workbook explicitly supplies an
    equity-style sector, otherwise the original ETF class is retained.

    Auto-repo agreements are always "Repo", checked before any dictionary
    lookup: their ISIN is minted fresh every rollover, so a per-ISIN
    dictionary entry can neither be relied on to exist nor, if one happens
    to match a stale/different ISIN, be trusted over the workbook's own
    section label.

    This is the single source of truth for "true class" - both the
    aggregated holdings view and the raw per-lot export call this, so they
    can never silently disagree with each other.
    """
    if normalized_asset_class == "Repo":
        return "Repo"
    if dictionary_class:
        mapped = _DICTIONARY_CLASS_MAP.get(dictionary_class, dictionary_class)
        if mapped:
            return mapped
    if normalized_asset_class in {"Government bond", "Corporate bond", "Equity", "Commodity"}:
        return normalized_asset_class
    code = (security_code or "").split()[0].upper()
    if code in _TRUE_CLASS_BY_SECURITY:
        return _TRUE_CLASS_BY_SECURITY[code]
    sector = (raw_sector or "").casefold()
    if any(token in sector for token in ("government bond", "гцб", "treasury", "sovereign")):
        return "Government bond"
    if any(token in sector for token in ("commodity", "commodities", "сырь")):
        return "Commodity"
    if normalized_asset_class == "ETF" and (
        raw_security_type.casefold() in {"акции", "equity", "equities"}
        or any(token in sector for token in ("financials", "information technology", "equity", "акци"))
    ):
        return "Equity"
    return normalized_asset_class or "Not supplied"


@dataclass
class DictionaryReplaceResult:
    row_count: int
    previous_row_count: int
    added_isins: list[str] = field(default_factory=list)
    removed_isins: list[str] = field(default_factory=list)
    changed_isins: list[str] = field(default_factory=list)


def _parse_rows(filename: str, content: bytes) -> list[dict[str, str]]:
    lower = filename.lower()
    if lower.endswith((".xlsx", ".xls")):
        try:
            import openpyxl
        except ImportError as exc:  # pragma: no cover - openpyxl is a hard dependency
            raise DictionaryValidationError("Не удалось прочитать Excel-файл") from exc
        workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        sheet = workbook.worksheets[0]
        rows_iter = sheet.iter_rows(values_only=True)
        try:
            header = [str(cell).strip() if cell is not None else "" for cell in next(rows_iter)]
        except StopIteration:
            raise DictionaryValidationError("Файл словаря пуст") from None
        rows = []
        for values in rows_iter:
            if all(value is None or str(value).strip() == "" for value in values):
                continue
            rows.append({key: ("" if value is None else str(value).strip()) for key, value in zip(header, values)})
        return rows
    text = content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def replace_instrument_dictionary(*, filename: str, content: bytes) -> DictionaryReplaceResult:
    """Validate and install a new version of the classes-and-ratings dictionary.

    Accepts either the same CSV format the app ships with, or an Excel
    workbook with the same header row (the format the portfolio team
    typically maintains it in). Writes the new dictionary to disk and
    invalidates the in-process cache so it takes effect immediately.
    """
    rows = _parse_rows(filename, content)
    if not rows:
        raise DictionaryValidationError("Файл словаря пуст")
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in rows[0]]
    if missing_columns:
        raise DictionaryValidationError(
            "В файле отсутствуют столбцы: " + ", ".join(missing_columns)
        )
    new_by_isin: dict[str, dict[str, str]] = {}
    for row in rows:
        isin = (row.get("ISIN") or "").strip().upper()
        if not isin:
            continue
        new_by_isin[isin] = {column: (row.get(column) or "").strip() for column in REQUIRED_COLUMNS}
    if not new_by_isin:
        raise DictionaryValidationError("В файле нет строк с заполненным ISIN")

    previous = instrument_dictionary()
    added = sorted(set(new_by_isin) - set(previous))
    removed = sorted(set(previous) - set(new_by_isin))
    changed = sorted(
        isin
        for isin in set(new_by_isin) & set(previous)
        if new_by_isin[isin] != previous[isin]
    )

    if _override_path is None:
        raise DictionaryValidationError("Хранилище загруженных словарей не настроено")
    _override_path.parent.mkdir(parents=True, exist_ok=True)
    with _override_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REQUIRED_COLUMNS))
        writer.writeheader()
        for isin in sorted(new_by_isin):
            writer.writerow(new_by_isin[isin])

    instrument_dictionary.cache_clear()

    return DictionaryReplaceResult(
        row_count=len(new_by_isin),
        previous_row_count=len(previous),
        added_isins=added,
        removed_isins=removed,
        changed_isins=changed,
    )
