"""Shared brokerage classification helpers.

The source workbook does not always expose a dedicated ``repo`` column.  Keep
the classification conservative and content-based: only explicit repo labels
in instrument/deal fields are treated as repo trades.  Client names and free
text evidence are deliberately excluded so an unrelated name cannot change
turnover totals.
"""

from __future__ import annotations

import re
from typing import Any, Mapping


_REPO_FIELDS = (
    "security_type",
    "instrument",
    "instrument_type",
    "trade_type",
    "deal_type",
    "transaction_type",
    "counterparty",
)


def is_repo_trade(payload: Mapping[str, Any]) -> bool:
    """Return ``True`` only when a trade explicitly identifies a repo."""

    for field in _REPO_FIELDS:
        value = str(payload.get(field) or "").strip().casefold()
        if not value:
            continue
        if "репо" in value or re.search(r"\brepo\b", value):
            return True
    return bool(payload.get("is_repo") is True)
