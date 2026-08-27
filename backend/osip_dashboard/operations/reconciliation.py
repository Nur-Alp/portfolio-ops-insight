"""Deterministic database/blob state evidence for recovery drills."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from osip_dashboard.persistence.models import (
    AuditEvent,
    CashBalanceRecord,
    DataQualityAcknowledgement,
    DataQualityIssueRecord,
    ImportBatch,
    Portfolio,
    PortfolioSnapshotRecord,
    PositionLotRecord,
    ReportRun,
    SettlementEventRecord,
    SettlementSourceLink,
    SourceRow,
)
from osip_dashboard.storage import BlobStore


TABLES = {
    "portfolios": Portfolio,
    "imports": ImportBatch,
    "snapshots": PortfolioSnapshotRecord,
    "source_rows": SourceRow,
    "position_lots": PositionLotRecord,
    "cash_balances": CashBalanceRecord,
    "settlements": SettlementEventRecord,
    "settlement_source_links": SettlementSourceLink,
    "dq_issues": DataQualityIssueRecord,
    "dq_acknowledgements": DataQualityAcknowledgement,
    "audit_events": AuditEvent,
    "report_runs": ReportRun,
}


def collect_recovery_state(session: Session, blob_store: BlobStore) -> dict[str, Any]:
    """Collect content hashes and business counts without exposing workbook data."""
    errors: list[str] = []
    source_files = [
        _artifact_state(
            blob_store,
            storage_key=batch.storage_key,
            expected_hash=batch.source_sha256,
            label=f"import:{batch.id}",
            errors=errors,
        )
        | {
            "import_id": str(batch.id),
            "portfolio": batch.portfolio_code,
            "report_date": batch.report_date.isoformat() if batch.report_date else None,
            "version": batch.version,
            "status": batch.status.value,
        }
        for batch in session.scalars(select(ImportBatch).order_by(ImportBatch.id))
    ]
    report_files = [
        _artifact_state(
            blob_store,
            storage_key=report.storage_key,
            expected_hash=report.artifact_sha256,
            label=f"report:{report.id}",
            errors=errors,
        )
        | {
            "report_id": str(report.id),
            "snapshot_id": str(report.snapshot_id),
            "format": report.format,
        }
        for report in session.scalars(select(ReportRun).order_by(ReportRun.id))
    ]
    snapshots = [
        {
            "snapshot_id": str(snapshot.id),
            "import_id": str(snapshot.import_id),
            "portfolio": snapshot.portfolio_code,
            "report_date": snapshot.report_date.isoformat(),
            "version": snapshot.version,
            "status": snapshot.import_batch.status.value,
            "position_count": snapshot.position_count,
            "unique_isin_count": snapshot.unique_isin_count,
            "raw_settlement_count": snapshot.raw_settlement_count,
            "settlement_count": snapshot.settlement_count,
            "purchase_amount_kzt": str(snapshot.purchase_amount_kzt),
            "derived_carrying_value_kzt": str(
                snapshot.derived_carrying_value_kzt
            ),
            "cash_kzt": str(snapshot.cash_kzt),
            "derived_operational_total_kzt": str(
                snapshot.derived_operational_total_kzt
            ),
        }
        for snapshot in session.scalars(
            select(PortfolioSnapshotRecord).order_by(
                PortfolioSnapshotRecord.portfolio_code,
                PortfolioSnapshotRecord.report_date,
                PortfolioSnapshotRecord.version,
            )
        )
    ]
    return {
        "format_version": 1,
        "counts": {
            name: session.scalar(select(func.count()).select_from(model)) or 0
            for name, model in TABLES.items()
        },
        "snapshots": snapshots,
        "source_files": source_files,
        "report_files": report_files,
        "integrity_errors": sorted(errors),
    }


def compare_recovery_states(
    expected: dict[str, Any], actual: dict[str, Any]
) -> list[str]:
    """Describe top-level recovery differences without dumping financial rows."""
    differences: list[str] = []
    for key in ("format_version", "counts", "snapshots", "source_files", "report_files"):
        if expected.get(key) != actual.get(key):
            differences.append(f"{key} differs from the pre-backup baseline")
    if actual.get("integrity_errors"):
        differences.extend(str(item) for item in actual["integrity_errors"])
    return differences


def _artifact_state(
    blob_store: BlobStore,
    *,
    storage_key: str,
    expected_hash: str,
    label: str,
    errors: list[str],
) -> dict[str, Any]:
    try:
        path = blob_store.path_for(storage_key)
        content = path.read_bytes()
        actual_hash = sha256(content).hexdigest()
        size_bytes = len(content)
    except (OSError, ValueError) as exc:
        errors.append(f"{label} cannot be read ({type(exc).__name__})")
        actual_hash = None
        size_bytes = None
    if actual_hash is not None and actual_hash != expected_hash:
        errors.append(f"{label} hash does not match the database")
    return {
        "storage_key": storage_key,
        "expected_sha256": expected_hash,
        "actual_sha256": actual_hash,
        "size_bytes": size_bytes,
    }
