"""Authoritative FX rates used only by presentation exports.

The operational dashboard deliberately keeps the OSIP report's own FX fields
for its derived carrying-value calculation.  Excel presentation exports may
need a common USD equivalent, so they use the National Bank of Kazakhstan's
dated official USD/KZT RSS feed.  A source-workbook rate is retained as a
transparent offline fallback; callers must disclose which source was used.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import xml.etree.ElementTree as ET

import httpx


NBK_RSS_URL = "https://nationalbank.kz/rss/get_rates.cfm"


@dataclass(frozen=True)
class FxRate:
    rate: Decimal
    effective_date: date
    source: str
    source_url: str
    fallback: bool = False


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _nbk_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


@lru_cache(maxsize=64)
def _fetch_nbk_exact(effective_date: date, currency: str = "USD") -> FxRate | None:
    """Read the NBK dated official <currency>/KZT rate, returning None when this date's feed has no rate for it.

    The feed's ``<item><title>`` is the three-letter currency code (e.g.
    "USD", "EUR", "GBP") and ``<description>`` is the KZT rate for
    ``<quant>`` units - confirmed against the live feed, not just guessed
    from field names, since the two are easy to swap.

    Deliberately does NOT catch connectivity/feed-parse failures here:
    this function is ``lru_cache``d by (date, currency), and a transient
    network error caught and turned into a cached ``None`` would silently
    and permanently suppress every later, would-succeed lookup for that
    date for the rest of the process's lifetime - long after the network
    recovers. Only a successfully-parsed feed that genuinely has no row
    for this currency is a stable, cacheable "no rate" result. Callers
    must catch ``httpx.HTTPError``/``ET.ParseError`` around this call.
    """
    url = f"{NBK_RSS_URL}?fdate={_nbk_date(effective_date)}"
    response = httpx.get(url, timeout=5.0, follow_redirects=True)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    date_node = root.find("date")
    feed_date = date_node.text.strip() if date_node is not None and date_node.text else _nbk_date(effective_date)
    parsed_date = date.fromisoformat(f"{feed_date[6:10]}-{feed_date[3:5]}-{feed_date[0:2]}")
    for item in root.findall("item"):
        title = (item.findtext("title") or "").strip().upper()
        if title != currency:
            continue
        value_text = (item.findtext("description") or "").strip().replace(",", ".")
        quantity_text = (item.findtext("quant") or "1").strip().replace(",", ".")
        try:
            value = Decimal(value_text) / Decimal(quantity_text)
        except (InvalidOperation, ZeroDivisionError):
            # A malformed row for this currency is a feed-content problem,
            # not a connectivity one - stable and safe to cache as "no rate".
            continue
        if value <= 0:
            continue
        return FxRate(
            rate=value,
            effective_date=parsed_date,
            source=f"National Bank of Kazakhstan — official daily {currency}/KZT rate",
            source_url=url,
        )
    return None


def _fetch_nbk_exact_safe(*args: date | str) -> FxRate | None:
    """Call ``_fetch_nbk_exact``, treating a connectivity/parse failure as no rate this attempt.

    Kept separate from the cached function itself so the failure is never
    memoized - see that function's docstring. Forwards args as-is (rather
    than fixing a ``(date, currency)`` signature) so callers keep passing
    only the arguments they actually have, matching ``_fetch_nbk_exact``'s
    own ``currency="USD"`` default.
    """
    try:
        return _fetch_nbk_exact(*args)
    except (httpx.HTTPError, ET.ParseError, ValueError):
        return None


def resolve_export_usd_kzt_rate(report_date: date, workbook_rate: Decimal | None) -> FxRate | None:
    """Resolve a dated USD/KZT rate for an Excel export.

    The exact report date is preferred.  If it is a non-publishing day, the
    latest NBK rate from the preceding seven calendar days is used and its
    effective date is disclosed.  If the feed cannot be reached, the common
    positive USD rate carried by the OSIP workbook is used as an offline,
    source-reported fallback.  No conversion is performed when neither source
    is available.
    """
    for offset in range(8):
        candidate = report_date - timedelta(days=offset)
        result = _fetch_nbk_exact_safe(candidate)
        if result is not None:
            return result
    if workbook_rate is not None and workbook_rate > 0:
        return FxRate(
            rate=workbook_rate,
            effective_date=report_date,
            source="OSIP workbook — source-reported report FX rate (NBK feed unavailable)",
            source_url="",
            fallback=True,
        )
    return None


def resolve_export_fx_rate(currency: str, report_date: date, workbook_rate: Decimal | None = None) -> FxRate | None:
    """Resolve a dated <currency>/KZT rate for an Excel export.

    Generalizes ``resolve_export_usd_kzt_rate`` to any NBK-quoted currency
    (used by the brokerage turnover export, which spans EUR/GBP/USD/KZT, not
    just USD) - same lookback-then-fallback policy: the exact report date is
    preferred, then up to seven preceding calendar days for a non-publishing
    day, then an optional caller-supplied offline rate as a disclosed
    fallback. No conversion is performed when neither source is available -
    the caller must show the amount as unavailable, not silently drop it or
    guess.
    """
    if currency == "KZT":
        return FxRate(rate=Decimal("1"), effective_date=report_date, source="KZT — base currency", source_url="")
    for offset in range(8):
        candidate = report_date - timedelta(days=offset)
        result = _fetch_nbk_exact_safe(candidate, currency)
        if result is not None:
            return result
    if workbook_rate is not None and workbook_rate > 0:
        return FxRate(
            rate=workbook_rate,
            effective_date=report_date,
            source=f"Source workbook — offline fallback rate (NBK feed unavailable) for {currency}",
            source_url="",
            fallback=True,
        )
    return None
