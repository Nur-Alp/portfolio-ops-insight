"""Versioned import workflow and published-snapshot HTTP API.

This package used to be a single flat module. It is now split into one
submodule per route domain, mirroring ``osip_dashboard/routes/``:

- ``shared``: cross-domain infrastructure and helpers (``XlsxResponse``,
  ``SessionDep``/``ActorDep``, ``get_session``, and the private helpers used
  by more than one domain module).
- ``imports``: upload/review/publish workflow handlers (mirrors
  ``routes/imports.py``).
- ``catalog``: portfolio/metric/snapshot catalog handlers (mirrors
  ``routes/catalog.py``).
- ``snapshots``: published-snapshot overview/holdings/DQ/calendar handlers
  (mirrors ``routes/snapshots.py``).
- ``reports``: snapshot CSV report handlers (mirrors ``routes/reports.py``).
- ``auth``: demo-persona login handler (mirrors ``routes/auth.py``).

Every name below is re-exported explicitly (no ``import *``) so both
``from osip_dashboard import api_handlers as handlers`` / ``handlers.<name>``
(used throughout ``osip_dashboard/routes/``) and
``from osip_dashboard.api_handlers import <name>`` (used by several tests)
keep working exactly as before the split.
"""

from __future__ import annotations

from .shared import ActorDep, SessionDep, XlsxResponse, get_session, router

from .auth import demo_login

from .imports import (
    approve,
    create_import,
    export_import_registry,
    get_dividend_data_status,
    get_import,
    get_import_comparison,
    get_import_source,
    get_reference_dictionary_status,
    list_imports,
    publish,
    reject,
    source_row_preview,
    upload_dividend_data,
    upload_reference_dictionary,
    withdraw,
    _infer_header_row,
)

from .catalog import (
    list_metric_definitions,
    list_portfolios,
    list_snapshots,
)

from .snapshots import (
    assign_dq_issue,
    export_snapshot_cash_calendar,
    export_snapshot_holdings,
    export_snapshot_issues,
    export_snapshot_lots,
    snapshot_allocations,
    snapshot_calendar,
    snapshot_cash,
    snapshot_holdings,
    snapshot_issues,
    snapshot_overview,
    snapshot_provenance,
    snapshot_report_readiness,
    snapshot_settlements,
    _provenance_ref,
    _weighted_average_ytm,
)

from .reports import (
    create_snapshot_report,
    get_report_artifact,
    list_snapshot_reports,
)

__all__ = [
    "ActorDep",
    "SessionDep",
    "XlsxResponse",
    "get_session",
    "router",
    "demo_login",
    "approve",
    "create_import",
    "export_import_registry",
    "get_dividend_data_status",
    "get_import",
    "get_import_comparison",
    "get_import_source",
    "get_reference_dictionary_status",
    "list_imports",
    "publish",
    "reject",
    "source_row_preview",
    "upload_dividend_data",
    "upload_reference_dictionary",
    "withdraw",
    "_infer_header_row",
    "list_metric_definitions",
    "list_portfolios",
    "list_snapshots",
    "assign_dq_issue",
    "export_snapshot_cash_calendar",
    "export_snapshot_holdings",
    "export_snapshot_issues",
    "export_snapshot_lots",
    "snapshot_allocations",
    "snapshot_calendar",
    "snapshot_cash",
    "snapshot_holdings",
    "snapshot_issues",
    "snapshot_overview",
    "snapshot_provenance",
    "snapshot_report_readiness",
    "snapshot_settlements",
    "_provenance_ref",
    "_weighted_average_ytm",
    "create_snapshot_report",
    "get_report_artifact",
    "list_snapshot_reports",
]
