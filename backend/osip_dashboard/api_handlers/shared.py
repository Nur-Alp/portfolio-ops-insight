"""Shared infrastructure and cross-domain helpers for the legacy OSIP API.

This module holds the pieces used by more than one of the domain-specific
handler modules (``imports.py``, ``catalog.py``, ``snapshots.py``,
``reports.py``, ``auth.py``), plus the small amount of app-wide plumbing
(``XlsxResponse``, session/actor dependencies) every one of them needs.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Iterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from osip_dashboard.identity import get_actor, require_domain, require_portfolio
from osip_dashboard.persistence.models import PortfolioSnapshotRecord
from osip_dashboard.services.workflow import Actor


router = APIRouter(prefix="/api/v1")
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _osip_export_filename(kind: str, portfolio_code: str, report_date: date) -> str:
    """Build an OSIP export filename: ``{portfolio}[_prop]_{kind}_data_{YYYYMMDD}``.

    SOBSTV is the firm's own (proprietary) book, not a client fund - the
    "_prop" tag distinguishes it from TABYS and any other portfolio at a
    glance without opening the file. No version number: unlike the
    immutable audit trail (which keeps every version), a downloaded export
    is a point-in-time convenience copy - the report date is what a
    recipient actually needs to identify it by.
    """
    date_compact = report_date.strftime("%Y%m%d")
    tag = f"{portfolio_code}_prop" if portfolio_code == "SOBSTV" else portfolio_code
    return f"{tag}_{kind}_data_{date_compact}.xlsx"


class XlsxResponse(Response):
    media_type = XLSX_MEDIA_TYPE


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session)]
ActorDep = Annotated[Actor, Depends(get_actor)]


def _get_snapshot(
    session: Session, snapshot_id: UUID, actor: Actor
) -> PortfolioSnapshotRecord:
    snapshot = session.get(PortfolioSnapshotRecord, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Снимок не найден")
    require_domain(actor, "back_office")
    require_portfolio(actor, snapshot.portfolio_code)
    return snapshot


def _snapshot_summary(snapshot: PortfolioSnapshotRecord) -> dict[str, Any]:
    return {
        "id": str(snapshot.id),
        "import_id": str(snapshot.import_id),
        "source_upload_id": str(snapshot.import_batch.source_upload_id) if snapshot.import_batch.source_upload_id else None,
        "portfolio": snapshot.portfolio_code,
        "report_date": _iso(snapshot.report_date),
        "version": snapshot.version,
        "status": snapshot.import_batch.status.value,
        "value_label": snapshot.value_label,
    }


def _dividend_status_payload(status: Any) -> dict[str, Any]:
    return {
        "freshness": status.freshness,
        "source_filename": status.source_filename,
        "source_sha256": status.source_sha256,
        "source_date": status.source_date.isoformat() if status.source_date else None,
        "uploaded_at": status.uploaded_at.isoformat() if status.uploaded_at else None,
        "latest_ex_date": status.latest_ex_date.isoformat() if status.latest_ex_date else None,
        "latest_pay_date": status.latest_pay_date.isoformat() if status.latest_pay_date else None,
        "future_pay_count": status.future_pay_count,
        "row_count": status.row_count,
        "ticker_count": status.ticker_count,
        "stale_after_days": status.stale_after_days,
    }


def _excel_column_letter(column: int) -> str:
    result = ""
    value = column
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
