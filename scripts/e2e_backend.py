"""Run a browser-test backend, optionally retaining local demo data."""

from pathlib import Path
import os
import tempfile

from alembic import command
from alembic.config import Config
import uvicorn
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect

from osip_dashboard.config import Settings
from osip_dashboard.main import create_app
from osip_dashboard.persistence import Base
from osip_dashboard.persistence.database import create_database_engine, create_session_factory
from osip_dashboard.services.imports import import_workbook
from osip_dashboard.services.workflow import Actor, approve_import, publish_import
from osip_dashboard.services.demo_multi_source import seed_multi_source_demo
from osip_dashboard.storage import LocalBlobStore


ROOT = Path(__file__).resolve().parents[1]
state_directory = os.getenv("OSIP_E2E_STATE_DIR")
if state_directory:
    # scripts/demo_service.py (via start-dashboard.command) points this at
    # .data/local-dashboard/runtime - the real, persistent local database.
    # It intentionally survives a process restart so an uploaded version is
    # never erased. Treat this path as live user data, not disposable output.
    runtime_path = Path(state_directory)
    runtime_path.mkdir(parents=True, exist_ok=True)
else:
    # CI and Playwright get their own disposable temporary directory instead.
    RUNTIME = tempfile.TemporaryDirectory(prefix="osip-e2e-")
    runtime_path = Path(RUNTIME.name)

database_path = runtime_path / "dashboard.sqlite3"
seed_fixtures = not database_path.exists()
database_url = f"sqlite:///{database_path}"
settings = Settings(
    environment="test",
    database_url=database_url,
    blob_root=runtime_path / "blobs",
    identity_provider="development",
    source_first_mode=True,
    cors_origins=["http://127.0.0.1:4173"],
)
engine = create_database_engine(database_url)
if state_directory:
    # Older local demos were created directly from SQLAlchemy metadata. Stamp
    # their known baseline once, then run normal Alembic migrations so local
    # history stays intact when the schema evolves.
    migration_config = Config(str(ROOT / "alembic.ini"))
    migration_config.set_main_option("sqlalchemy.url", database_url)
    migration_config.set_main_option("script_location", str(ROOT / "migrations"))
    if "alembic_version" not in inspect(engine).get_table_names():
        if inspect(engine).get_table_names():
            command.stamp(migration_config, "0001_versioned_imports")
    command.upgrade(migration_config, "head")
else:
    Base.metadata.create_all(engine)
blob_store = LocalBlobStore(settings.blob_root)
session_factory = create_session_factory(engine)

if seed_fixtures:
    with session_factory() as session:
        fixtures = (
            ("SOBSTV", ROOT / "Portfolio operations" / "ОСИП Портфель о состоянии текущего портфеля и  предстоящих расчетах по сделкам  СОБСТВ 15.07.2026.xls"),
            ("TABYS", ROOT / "Portfolio operations" / "ОСИП Портфель о состоянии текущего портфеля и  предстоящих расчетах по сделкам TABYS 15.07.2026.xls"),
        )
        for portfolio_code, path in fixtures:
            outcome = import_workbook(
                session,
                blob_store,
                filename=path.name,
                content=path.read_bytes(),
                portfolio_code=portfolio_code,
                uploader_id="e2e-uploader",
                max_upload_bytes=settings.max_upload_bytes,
            )
            batch = outcome.import_batch
            required_codes = sorted(
                {
                    issue.code
                    for issue in batch.snapshot.issues
                    if issue.severity in {"blocker", "high"}
                }
            )
            approve_import(
                session,
                batch.id,
                actor=Actor("e2e-reviewer", frozenset({"reviewer"})),
                comment="E2E independent review",
                acknowledged_codes=required_codes,
            )
            publish_import(
                session,
                batch.id,
                actor=Actor("e2e-publisher", frozenset({"publisher"})),
            )
        session.commit()

# Existing persistent local demos receive sanitized examples after migrating;
# the seeder is idempotent and never reads the ignored real source directory.
with session_factory() as session:
    seed_multi_source_demo(session, blob_store)
    session.commit()

app = create_app(settings=settings, engine=engine, blob_store=blob_store)

# The built frontend lets this disposable environment be opened directly when
# Node/Vite is not available. API and health routes were registered before
# this catch-all, so they continue to reach FastAPI first. The catch-all
# itself mirrors the production nginx `try_files $uri $uri/ /index.html`
# rule: an unmatched path is a client-side route, not a missing file, so it
# must still serve index.html rather than 404 on a page refresh or deep link.
frontend_dist = ROOT / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount(
        "/assets", StaticFiles(directory=frontend_dist / "assets"), name="dashboard-assets"
    )

    @app.middleware("http")
    async def add_cache_headers(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/assets/"):
            # Vite content-hashes these filenames - any content change gets a
            # new URL, so caching forever is always safe.
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            # index.html (served both directly and via the SPA fallback
            # below) references the current hashed bundle by name, so it
            # must always be revalidated. Neither route set any
            # Cache-Control before this - with only Last-Modified/ETag and
            # no explicit directive, browsers (Safari in particular) may
            # apply heuristic freshness and skip even a conditional request
            # on reload, which is exactly what let a stale bundle keep
            # loading here after a plain refresh.
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        # Mirrors LocalBlobStore.path_for's traversal guard: don't rely on
        # the ASGI layer's own dot-segment normalization alone to keep this
        # confined to frontend_dist.
        dist_root = frontend_dist.resolve()
        candidate = (dist_root / full_path).resolve()
        if full_path and dist_root in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(frontend_dist / "index.html")

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.getenv("OSIP_E2E_PORT", "8765")),
        log_level="warning",
    )
