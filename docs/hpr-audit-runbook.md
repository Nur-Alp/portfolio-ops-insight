# HPR audit runbook

Use this check before publishing a new OSIP holdings export.

## Inputs

- The immutable OSIP source workbook (`.xls`).
- The generated holdings export (`.xlsx`).
- The latest Bloomberg dividend dictionary (`.xlsx`).

## Command

From the repository root:

```bash
.venv/bin/python scripts/audit_hpr_export.py \
  /path/to/source.xls \
  /path/to/holdings_export.xlsx \
  --portfolio-code TABYS \
  --dividends "/path/to/dividends 28.07.26..xlsx" \
  --as-of 2026-07-28
```

The command compares source lot order, carrying value, purchase amount, source carrying price, HPR amount in KZT/FX, and the explicit `HPR (расч.), KZT, %` and `HPR (расч.), FX, %` percentage-point columns. The FX basis is the USD-equivalent return where supported. It also applies the same strict dividend rule used by the application: `ex_date > purchase_date` and `pay_date < as_of`, with 15% withholding for tickers containing the standalone `US` market token. For coupon-bearing lots, the export adds the disclosed gross estimate `nominal × quantity × coupon_rate × holding_days / 360` less the current accrued coupon already included in carrying value; this is not treated as a payment-history assertion.

The audit fails if a formula-backed OSIP `Балансовая цена` is exported as
`Недоступно`, if a source carrying-price value changes beyond tolerance, or if
the export uses the old USD percentage header instead of the explicit FX label.

## Release criteria

- `passed` is `true` and `issues` is empty.
- `source_lots` equals `export_lots`.
- The dividend dictionary status is reviewed. Future pay dates are intentionally excluded until their pay date.
- The workbook opens in Excel without a repair prompt.
- DQ-04/DQ-05 are reviewed as source-metadata limitations; they do not override a clean arithmetic reconciliation.
