"""Command-line inspection of OSIP workbook snapshots."""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

from osip_dashboard.ingestion import parse_osip_workbook


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _summary(path: Path, portfolio_code: str) -> dict[str, object]:
    snapshot = parse_osip_workbook(path, portfolio_code=portfolio_code)
    return {
        "portfolio": snapshot.portfolio_code,
        "reportDate": snapshot.report_date.isoformat(),
        "source": snapshot.source_path.name,
        "sha256": snapshot.source_sha256,
        "positions": len(snapshot.positions),
        "uniqueIsins": len(snapshot.unique_isins),
        "rawSettlements": len(snapshot.raw_settlements),
        "uniqueSettlements": len(snapshot.settlements),
        "cashRows": len(snapshot.cash_balances),
        "activeCashRows": sum(balance.is_active for balance in snapshot.cash_balances),
        "purchaseAmountKzt": _money(snapshot.purchase_amount_kzt),
        "derivedCarryingValueKzt": _money(snapshot.derived_carrying_value_kzt),
        "cashKzt": _money(snapshot.cash_kzt),
        "derivedOperationalTotalKzt": _money(snapshot.derived_operational_total_kzt),
        "dataQuality": dict(sorted(Counter(issue.code for issue in snapshot.issues).items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse OSIP legacy workbooks and print a source-traceable snapshot summary."
    )
    parser.add_argument("workbooks", type=Path, nargs="+", help="One or more OSIP .xls files")
    parser.add_argument("--portfolio-code", required=True, help="Business portfolio code assigned by the operator")
    args = parser.parse_args()
    print(json.dumps([_summary(path, args.portfolio_code) for path in args.workbooks], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
