"""Import every real workbook in the gitignored sources/ folder into a demo
deployment - the "upload everything in sources/" rule. See
docs/demo-deployment.md.

Idempotent: re-running skips anything already imported/published (matching
each service function's own dedupe/guard checks), so this is safe to run
again whenever sources/ gains new or replaced files.

Never touches .data/local-dashboard (the real local dev data) - this
targets whatever OSIP_DATABASE_URL/OSIP_BLOB_ROOT/OSIP_REFERENCE_DATA_ROOT
point at.
"""

from __future__ import annotations

import os
from pathlib import Path

from osip_dashboard.config import get_settings
from osip_dashboard.ingestion.multi_source import SourceDetectionError
from osip_dashboard.persistence.database import create_database_engine, create_session_factory
from osip_dashboard.persistence.models import ImportStatus
from osip_dashboard.services.dividends import DividendValidationError, configure_dividend_data_root, replace_dividend_history
from osip_dashboard.services.imports import UploadValidationError, import_workbook
from osip_dashboard.services.multi_source import approve_dataset, create_source_upload, materialize_datasets, publish_dataset
from osip_dashboard.services.workflow import Actor, WorkflowError, approve_import, publish_import
from osip_dashboard.storage import LocalBlobStore

ROOT = Path(__file__).resolve().parents[1]
# Overridable so a deployed environment (no repo checkout, no local
# sources/ folder) can point this at wherever the real workbooks were
# uploaded instead - e.g. a persistent volume, never baked into an image.
SOURCES_DIR = Path(os.environ.get("OSIP_SOURCES_DIR", ROOT / "sources"))
UPLOADER_ID = "e2e-uploader"

# Legacy OSIP .xls snapshots: the app never infers the portfolio from
# content or filename (see docs/domain-upload-instructions.md), so this
# mapping is the one place a human decision is encoded.
OSIP_PORTFOLIO_FILES = {
    "Бэк офис_УИП_ ОСИП собственный портфель 19.07.2026.xls": "SOBSTV",
    "Бэк офис_УИП_ ОСИП ТАбыс 19.07.2026.xls": "TABYS",
}

DIVIDEND_FILE = "dividends.xlsx"

SKIP_SUFFIXES = {".docx", ".ini"}
SKIP_PREFIXES = ("~$",)


def _iter_source_files():
    for path in sorted(SOURCES_DIR.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() in SKIP_SUFFIXES or path.name.startswith(SKIP_PREFIXES):
            continue
        yield path


def _import_osip(session, blob_store, path: Path, portfolio_code: str) -> None:
    try:
        outcome = import_workbook(
            session, blob_store,
            filename=path.name, content=path.read_bytes(),
            portfolio_code=portfolio_code, uploader_id=UPLOADER_ID,
            max_upload_bytes=50 * 1024 * 1024,
        )
    except UploadValidationError as exc:
        print(f"  SKIP (validation error): {exc}")
        return
    batch = outcome.import_batch
    if batch.status != ImportStatus.VALIDATED:
        print(f"  already {batch.status.value}, skipping review/publish")
        return
    required_codes = sorted({issue.code for issue in batch.snapshot.issues if issue.severity in {"blocker", "high"}})
    try:
        approve_import(session, batch.id, actor=Actor("e2e-reviewer", frozenset({"reviewer"})), comment="Demo import review", acknowledged_codes=required_codes)
        publish_import(session, batch.id, actor=Actor("e2e-publisher", frozenset({"publisher"})))
        print(f"  published (portfolio {portfolio_code}, report date {batch.report_date})")
    except WorkflowError as exc:
        print(f"  SKIP (workflow): {exc}")


def _import_multi_source(session, blob_store, path: Path) -> None:
    try:
        upload, duplicate = create_source_upload(
            session, blob_store,
            filename=path.name, content=path.read_bytes(),
            uploader_id=UPLOADER_ID, max_upload_bytes=50 * 1024 * 1024,
        )
    except (SourceDetectionError, UploadValidationError, ValueError) as exc:
        print(f"  SKIP (detection failed): {exc}")
        return
    if upload.detected_source_type == "osip_portfolio":
        print("  SKIP: OSIP legacy file not listed in OSIP_PORTFOLIO_FILES - add it there")
        return
    proposals = upload.detection.get("datasets", [])
    if not proposals:
        print(f"  SKIP: nothing detected (type={upload.detected_source_type!r})")
        return
    assignments = [{"detected_key": item["key"], "scope_code": item.get("scope_code")} for item in proposals]
    datasets = materialize_datasets(session, blob_store, upload, assignments=assignments, uploader_id=UPLOADER_ID)
    for dataset in datasets:
        if dataset.status == ImportStatus.FAILED:
            print(f"  {dataset.dataset_type}/{dataset.scope_code}: FAILED to parse - source retained for review")
            continue
        if dataset.status != ImportStatus.VALIDATED:
            print(f"  {dataset.dataset_type}/{dataset.scope_code}: already {dataset.status.value}")
            continue
        required_codes = sorted({issue.code for issue in dataset.issues if issue.severity in {"blocker", "high"}})
        try:
            approve_dataset(session, dataset, UPLOADER_ID, "Demo import review", required_codes)
            publish_dataset(session, dataset, UPLOADER_ID)
        except ValueError as exc:
            # A real, correctly-enforced business rule (e.g. the consumed-
            # formula-audit gate finding a published field backed by a
            # blank/error formula result) - not a bug. Leave it validated
            # rather than crash the whole import; it's still visible for
            # manual review.
            print(f"  {dataset.dataset_type}/{dataset.scope_code}: SKIP publish - {exc}")
            continue
        print(f"  {dataset.dataset_type}/{dataset.scope_code}: published (business date {dataset.business_date})")


def main() -> None:
    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    blob_store = LocalBlobStore(settings.blob_root)
    configure_dividend_data_root(settings.reference_data_root)

    # Commit after every file, not once at the end: some of these real
    # workbooks take tens of seconds each to parse (thousands of formula
    # cells to audit), so a single all-or-nothing transaction meant an
    # interrupted run threw away everything already done. Each file's
    # ingestion functions are individually idempotent (dedupe by content
    # hash / active-dataset checks), so committing per file is safe to
    # re-run.
    for path in _iter_source_files():
        print(path.name)
        with session_factory() as session:
            if path.name in OSIP_PORTFOLIO_FILES:
                _import_osip(session, blob_store, path, OSIP_PORTFOLIO_FILES[path.name])
            elif path.name == DIVIDEND_FILE:
                try:
                    status = replace_dividend_history(filename=path.name, content=path.read_bytes())
                    print(f"  dividend dictionary replaced (latest ex-date {status.latest_ex_date})")
                except DividendValidationError as exc:
                    print(f"  SKIP (validation error): {exc}")
            else:
                _import_multi_source(session, blob_store, path)
            session.commit()
    print("done")


if __name__ == "__main__":
    main()
