"""Database primitives for persisted OSIP snapshots."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from osip_dashboard.persistence.models import (  # noqa: E402,F401
    AuditEvent,
    CashBalanceRecord,
    ClientIdentityResolution,
    DataQualityAcknowledgement,
    DataQualityIssueRecord,
    ImportBatch,
    InstrumentRecord,
    MetricDefinition,
    Portfolio,
    PositionLotRecord,
    PortfolioSnapshotRecord,
    ReportRun,
    SettlementEventRecord,
    SettlementSourceLink,
    SourceRow,
)
