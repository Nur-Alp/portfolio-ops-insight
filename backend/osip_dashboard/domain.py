"""Canonical, source-traceable models for OSIP workbook snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any


ZERO = Decimal("0")


class Severity(StrEnum):
    BLOCKER = "blocker"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class SourceRef:
    workbook_name: str
    sheet_name: str
    row_number: int


@dataclass(frozen=True)
class PositionLotSnapshot:
    portfolio_code: str
    report_date: date
    source: SourceRef
    source_section: str
    security_code: str
    isin: str
    raw_security_type: str
    issuer: str
    valuation_method: str
    instrument_currency: str
    raw_sector: str
    rating_sp: str
    rating_moodys: str
    rating_fitch: str
    coupon_or_repo_rate: Decimal | None
    nominal_value: Decimal | None
    open_date: date | None
    close_date: date | None
    quantity: Decimal
    purchase_date: date | None
    purchase_price: Decimal | None
    purchase_yield: Decimal | None
    current_ytm: Decimal | None
    purchase_amount_native: Decimal | None
    purchase_amount_kzt: Decimal | None
    carrying_amount_native: Decimal | None
    carrying_price_native: Decimal | None
    reserve_kzt: Decimal | None
    organizer_fee_kzt: Decimal | None
    broker_fee_kzt: Decimal | None
    accrued_income_kzt: Decimal | None
    principal_indexation: Decimal | None
    report_fx_rate: Decimal | None
    next_coupon_date: date | None
    previous_coupon_date: date | None
    listing_rating: str
    expected_coupon_cached: Decimal | None = None
    unavailable_fields: tuple[str, ...] = ()
    raw_row: tuple[Any, ...] = field(default_factory=tuple, repr=False)

    @property
    def derived_carrying_value_kzt(self) -> Decimal | None:
        """Transparent operational value; never an official NAV/market value."""
        if self.carrying_amount_native is None or self.report_fx_rate is None:
            return None
        indexation = self.principal_indexation if self.principal_indexation is not None else Decimal("1")
        accrued = self.accrued_income_kzt if self.accrued_income_kzt is not None else ZERO
        return self.carrying_amount_native * self.report_fx_rate * indexation + accrued

@dataclass(frozen=True)
class SettlementEvent:
    portfolio_code: str
    report_date: date
    security_code: str
    isin: str
    raw_security_type: str
    issuer: str
    currency: str
    quantity: Decimal
    settlement_date: date | None
    purchase_price: Decimal | None
    amount_native: Decimal | None
    amount_kzt: Decimal | None
    source_refs: tuple[SourceRef, ...]
    raw_rows: tuple[tuple[Any, ...], ...] = field(default_factory=tuple, repr=False)

    @property
    def signature(self) -> tuple[Any, ...]:
        return (
            self.portfolio_code,
            self.security_code,
            self.isin,
            self.raw_security_type,
            self.currency,
            self.quantity,
            self.settlement_date,
            self.purchase_price,
            self.amount_native,
            self.amount_kzt,
        )


@dataclass(frozen=True)
class CashBalanceSnapshot:
    portfolio_code: str
    report_date: date
    source: SourceRef
    raw_label: str
    currency: str
    custodian: str | None
    native_amount: Decimal
    kzt_amount: Decimal
    raw_row: tuple[Any, ...] = field(default_factory=tuple, repr=False)

    @property
    def is_active(self) -> bool:
        return self.native_amount != ZERO or self.kzt_amount != ZERO


@dataclass(frozen=True)
class DataQualityIssue:
    code: str
    severity: Severity
    message: str
    source_refs: tuple[SourceRef, ...] = ()
    affected_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class PortfolioSnapshot:
    portfolio_code: str
    report_date: date
    source_path: Path
    source_sha256: str
    positions: tuple[PositionLotSnapshot, ...]
    raw_settlements: tuple[SettlementEvent, ...]
    settlements: tuple[SettlementEvent, ...]
    cash_balances: tuple[CashBalanceSnapshot, ...]
    issues: tuple[DataQualityIssue, ...]
    resolved_columns: dict[str, int] = field(default_factory=dict)

    @property
    def unique_isins(self) -> frozenset[str]:
        return frozenset(position.isin for position in self.positions if position.isin)

    @property
    def purchase_amount_kzt(self) -> Decimal:
        return sum((position.purchase_amount_kzt or ZERO for position in self.positions), ZERO)

    @property
    def derived_carrying_value_kzt(self) -> Decimal:
        return sum((position.derived_carrying_value_kzt or ZERO for position in self.positions), ZERO)

    @property
    def cash_kzt(self) -> Decimal:
        return sum((balance.kzt_amount for balance in self.cash_balances), ZERO)

    @property
    def derived_operational_total_kzt(self) -> Decimal:
        return self.derived_carrying_value_kzt + self.cash_kzt

    @property
    def total_fees_kzt(self) -> Decimal:
        return sum(
            (
                (position.organizer_fee_kzt or ZERO)
                + (position.broker_fee_kzt or ZERO)
                for position in self.positions
            ),
            ZERO,
        )

    @property
    def total_reserves_kzt(self) -> Decimal:
        return sum((position.reserve_kzt or ZERO for position in self.positions), ZERO)
