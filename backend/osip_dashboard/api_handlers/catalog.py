"""Portfolio/metric/snapshot catalog HTTP handlers."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import HTTPException, Query

from osip_dashboard.identity import require_domain, require_portfolio, require_role
from osip_dashboard.persistence.models import (
    ImportBatch,
    ImportStatus,
    MetricDefinition,
    Portfolio,
    PortfolioSnapshotRecord,
)
from sqlalchemy import select

from .shared import ActorDep, SessionDep, _iso, _snapshot_summary, router


@router.get("/portfolios")
def list_portfolios(session: SessionDep, actor: ActorDep) -> dict[str, Any]:
    require_role(actor, "reader")
    require_domain(actor, "back_office")
    portfolios = list(session.scalars(select(Portfolio).order_by(Portfolio.code)))
    if "*" not in actor.portfolios:
        portfolios = [item for item in portfolios if item.code in actor.portfolios]
    items: list[dict[str, Any]] = []
    latest_dates: list[date] = []
    for portfolio in portfolios:
        latest = session.scalar(
            select(ImportBatch)
            .where(
                ImportBatch.portfolio_code == portfolio.code,
                ImportBatch.status == ImportStatus.PUBLISHED,
            )
            .order_by(ImportBatch.report_date.desc(), ImportBatch.version.desc())
            .limit(1)
        )
        if latest and latest.report_date:
            latest_dates.append(latest.report_date)
        items.append(
            {
                "code": portfolio.code,
                "name": portfolio.name,
                "reporting_currency": portfolio.reporting_currency,
                "latest_published_report_date": _iso(latest.report_date) if latest else None,
                "latest_published_snapshot_id": str(latest.snapshot.id)
                if latest and latest.snapshot
                else None,
            }
        )
    return {
        "items": items,
        "combined_report_dates": sorted({_iso(value) for value in latest_dates}),
        "report_date_mismatch": len(set(latest_dates)) > 1,
    }


@router.get("/metrics")
def list_metric_definitions(session: SessionDep, actor: ActorDep) -> dict[str, Any]:
    require_role(actor, "reader")
    require_domain(actor, "back_office")
    definitions = list(
        session.scalars(select(MetricDefinition).order_by(MetricDefinition.code))
    )
    return {
        "items": [
            {
                "code": definition.code,
                "label": definition.label,
                "basis": definition.basis,
                "unit": definition.unit,
                "formula": definition.formula,
                "version": definition.version,
                "enabled": definition.enabled,
                "unavailable_reason": definition.unavailable_reason,
            }
            for definition in definitions
        ]
    }


@router.get("/portfolios/{code}/snapshots")
def list_snapshots(
    code: str,
    session: SessionDep,
    actor: ActorDep,
    include_unpublished: bool = Query(False),
    include_superseded: bool = Query(False),
) -> dict[str, Any]:
    require_role(actor, "reader")
    require_domain(actor, "back_office")
    require_portfolio(actor, code)
    portfolio = session.get(Portfolio, code.upper())
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Портфель не найден")
    statement = (
        select(PortfolioSnapshotRecord)
        .join(ImportBatch, PortfolioSnapshotRecord.import_id == ImportBatch.id)
        .where(PortfolioSnapshotRecord.portfolio_code == portfolio.code)
        .order_by(
            PortfolioSnapshotRecord.report_date.desc(),
            PortfolioSnapshotRecord.version.desc(),
        )
    )
    if include_unpublished:
        pass
    elif include_superseded:
        statement = statement.where(
            ImportBatch.status.in_((ImportStatus.PUBLISHED, ImportStatus.SUPERSEDED))
        )
    else:
        statement = statement.where(ImportBatch.status == ImportStatus.PUBLISHED)
    snapshots = list(session.scalars(statement))
    return {"items": [_snapshot_summary(item) for item in snapshots]}
