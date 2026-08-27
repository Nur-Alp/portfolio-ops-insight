"""Reproducible operational snapshot artifacts."""

from __future__ import annotations

from decimal import Decimal
import hashlib
import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from osip_dashboard.persistence.models import AuditEvent, ImportStatus, PortfolioSnapshotRecord, ReportRun
from osip_dashboard.services.excel_safety import SafeCsvWriter
from osip_dashboard.storage import BlobStore


DISCLOSURES = [
    "Operational/derived workbook snapshot; not official reporting.",
    "Derived carrying value formula: AA × AU × AT + AR.",
    "Official NAV, market value, performance and settlement reconciliation are unavailable.",
]


def generate_csv_report(
    session: Session,
    blob_store: BlobStore,
    snapshot: PortfolioSnapshotRecord,
    actor_id: str,
    *,
    allow_unacknowledged_dq: bool = False,
) -> ReportRun:
    if snapshot.import_batch.status != ImportStatus.PUBLISHED:
        raise ValueError("Операционный артефакт можно сформировать только по опубликованному снимку")
    if not allow_unacknowledged_dq and any(
        issue.severity in {"blocker", "high"} and issue.acknowledgement is None
        for issue in snapshot.issues
    ):
        raise ValueError("Перед экспортом необходимо подтвердить блокирующие и высокие замечания DQ")
    content = _csv_content(snapshot)
    artifact_sha256 = hashlib.sha256(content).hexdigest()
    existing = session.scalar(select(ReportRun).where(ReportRun.artifact_sha256 == artifact_sha256))
    if existing is not None:
        return existing
    report = ReportRun(
        snapshot=snapshot,
        requested_by=actor_id,
        format="csv",
        artifact_sha256=artifact_sha256,
        storage_key=blob_store.put(artifact_sha256, content, suffix=".csv"),
        disclosures=DISCLOSURES,
    )
    session.add(report)
    session.add(AuditEvent(import_batch=snapshot.import_batch, actor_id=actor_id, action="report.generated", detail={"format": "csv", "artifact_sha256": artifact_sha256}))
    session.flush()
    return report


def _csv_content(snapshot: PortfolioSnapshotRecord) -> bytes:
    output = io.StringIO(newline="")
    writer = SafeCsvWriter(output)
    writer.writerow(["OSIP Portfolio Operational Snapshot"])
    batch = snapshot.import_batch
    for label, value in (
        ("Portfolio", snapshot.portfolio_code),
        ("Report date", snapshot.report_date.isoformat()),
        ("Snapshot version", snapshot.version),
        ("Import ID", str(snapshot.import_id)),
        ("Source filename", batch.original_filename),
        ("Source SHA-256", batch.source_sha256),
        ("Parser version", batch.parser_version),
        ("Uploader", batch.uploader_id),
        ("Reviewer", batch.reviewer_id or ""),
        ("Publisher", batch.publisher_id or ""),
        ("Approved at", batch.approved_at.isoformat() if batch.approved_at else ""),
        ("Published at", batch.published_at.isoformat() if batch.published_at else ""),
    ):
        writer.writerow([label, value])
    for disclosure in DISCLOSURES:
        writer.writerow(["Disclosure", disclosure])

    purchase_amount_kzt = sum(
        (lot.purchase_amount_kzt or Decimal("0") for lot in snapshot.position_lots),
        Decimal("0"),
    )
    derived_carrying_value_kzt = sum(
        (lot.derived_carrying_value_kzt or Decimal("0") for lot in snapshot.position_lots),
        Decimal("0"),
    )
    cash_kzt = sum(
        (balance.kzt_amount for balance in snapshot.cash_balances), Decimal("0")
    )
    total_fees_kzt = sum(
        (
            (lot.organizer_fee_kzt or Decimal("0"))
            + (lot.broker_fee_kzt or Decimal("0"))
            for lot in snapshot.position_lots
        ),
        Decimal("0"),
    )
    total_reserves_kzt = sum(
        (lot.reserve_kzt or Decimal("0") for lot in snapshot.position_lots),
        Decimal("0"),
    )
    writer.writerow([])
    writer.writerow(["Summary metrics"])
    writer.writerow(["Metric", "Value", "Basis"])
    for code, value, basis in (
        ("position_count", snapshot.position_count, "source"),
        ("unique_isin_count", snapshot.unique_isin_count, "source"),
        ("purchase_amount_kzt", purchase_amount_kzt, "source"),
        ("derived_carrying_value_kzt", derived_carrying_value_kzt, "derived"),
        ("cash_kzt", cash_kzt, "source"),
        ("derived_operational_total_kzt", derived_carrying_value_kzt + cash_kzt, "derived"),
        ("total_fees_kzt", total_fees_kzt, "source"),
        ("total_reserves_kzt", total_reserves_kzt, "source"),
        ("official_nav_kzt", "", "unavailable"),
        ("official_performance", "", "unavailable"),
    ):
        writer.writerow([code, value, basis])

    writer.writerow([])
    writer.writerow(["Position lots"])
    writer.writerow(["ISIN", "Security code", "Issuer", "Asset class", "Currency", "Quantity", "Purchase date", "Purchase amount KZT", "Derived carrying value KZT", "Workbook", "Sheet", "Row"])
    for lot in sorted(snapshot.position_lots, key=lambda item: (item.isin, item.source_row.row_number)):
        writer.writerow([lot.isin, lot.security_code, lot.issuer, lot.instrument.normalized_asset_class, lot.instrument_currency, lot.quantity, lot.purchase_date.isoformat() if lot.purchase_date else "", lot.purchase_amount_kzt if lot.purchase_amount_kzt is not None else "", lot.derived_carrying_value_kzt if lot.derived_carrying_value_kzt is not None else "", lot.source_row.workbook_name, lot.source_row.sheet_name, lot.source_row.row_number])

    writer.writerow([])
    writer.writerow(["Cash balances"])
    writer.writerow(["Raw label", "Currency", "Custodian", "Native amount", "KZT equivalent", "Active", "Workbook", "Sheet", "Row"])
    for balance in sorted(snapshot.cash_balances, key=lambda item: item.source_row.row_number):
        writer.writerow([
            balance.raw_label,
            balance.currency,
            balance.custodian or "",
            balance.native_amount,
            balance.kzt_amount,
            "yes" if balance.native_amount != 0 or balance.kzt_amount != 0 else "no",
            balance.source_row.workbook_name,
            balance.source_row.sheet_name,
            balance.source_row.row_number,
        ])

    writer.writerow([])
    writer.writerow(["Deduplicated settlements"])
    writer.writerow(["ISIN", "Security code", "Issuer", "Currency", "Quantity", "Settlement date", "Amount native", "Amount KZT", "Source rows"])
    for settlement in sorted(
        snapshot.settlements,
        key=lambda item: (item.settlement_date or snapshot.report_date, item.isin, item.id.hex),
    ):
        writer.writerow([
            settlement.isin,
            settlement.security_code,
            settlement.issuer,
            settlement.currency,
            settlement.quantity,
            settlement.settlement_date.isoformat() if settlement.settlement_date else "",
            settlement.amount_native if settlement.amount_native is not None else "",
            settlement.amount_kzt if settlement.amount_kzt is not None else "",
            "; ".join(
                f"{link.source_row.sheet_name}!{link.source_row.row_number}"
                for link in settlement.source_links
            ),
        ])

    writer.writerow([])
    writer.writerow(["Operational calendar"])
    writer.writerow([
        "Date", "Event", "ISIN", "Security code", "Status",
        "Amount native", "Amount KZT", "Currency", "Amount basis", "Source row",
    ])
    events: list[tuple[str, str, str, str, str, str, str, str, str, str]] = []
    for settlement in snapshot.settlements:
        if settlement.settlement_date:
            events.append((
                settlement.settlement_date.isoformat(),
                "settlement",
                settlement.isin,
                settlement.security_code,
                "overdue" if settlement.settlement_date < snapshot.report_date else "upcoming",
                str(settlement.amount_native) if settlement.amount_native is not None else "",
                str(settlement.amount_kzt) if settlement.amount_kzt is not None else "",
                settlement.currency,
                "source_settlement_amount" if settlement.amount_kzt is not None else "unavailable",
                "; ".join(
                    f"{link.source_row.sheet_name}!{link.source_row.row_number}"
                    for link in settlement.source_links
                ),
            ))
    for lot in snapshot.position_lots:
        for event_type, event_date in (
            (
                "repo_open" if lot.instrument.normalized_asset_class == "Repo" else "instrument_open",
                lot.purchase_date or lot.open_date,
            ),
            ("repo_close" if lot.instrument.normalized_asset_class == "Repo" else "maturity", lot.close_date),
            ("previous_coupon", lot.previous_coupon_date),
            ("next_coupon", lot.next_coupon_date),
        ):
            if event_date:
                is_purchase = event_type in {"repo_open", "instrument_open"}
                events.append((
                    event_date.isoformat(),
                    event_type,
                    lot.isin,
                    lot.security_code,
                    "historical" if event_date < snapshot.report_date else "upcoming",
                    str(lot.purchase_amount_native) if is_purchase and lot.purchase_amount_native is not None else "",
                    str(lot.purchase_amount_kzt) if is_purchase and lot.purchase_amount_kzt is not None else "",
                    lot.instrument_currency,
                    "source_purchase_amount" if is_purchase and lot.purchase_amount_kzt is not None else "unavailable",
                    f"{lot.source_row.sheet_name}!{lot.source_row.row_number}",
                ))
    writer.writerows(sorted(events))

    writer.writerow([])
    writer.writerow(["Data quality findings"])
    writer.writerow(["Code", "Severity", "Message", "Affected fields", "Acknowledged by", "Acknowledgement", "Source rows"])
    for issue in sorted(snapshot.issues, key=lambda item: (item.severity, item.code, str(item.id))):
        acknowledgement = issue.acknowledgement
        writer.writerow([
            issue.code,
            issue.severity,
            issue.message,
            "; ".join(issue.affected_fields),
            acknowledgement.actor_id if acknowledgement else "",
            acknowledgement.comment if acknowledgement else "",
            "; ".join(
                f"{ref.get('sheet_name', '')}!{ref.get('row_number', '')}"
                for ref in issue.source_refs
            ),
        ])
    return ("\ufeff" + output.getvalue()).encode("utf-8")
