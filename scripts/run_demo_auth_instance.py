"""Run a second dashboard instance, gated by username/password, on the real
local database.

Unlike scripts/e2e_backend.py (used by start-dashboard.command), this does
NOT reseed synthetic fixtures or run migrations - it points straight at the
same .data/local-dashboard/runtime database and blob store the primary
instance already uses, already at the current migration head. It exists so a
real login (POST /api/v1/auth/demo-login) can gate access to that same real
data, instead of the spoofable X-Actor-* dev headers the primary instance
still trusts on its own port.

Usage:
    OSIP_DEMO_JWT_SECRET=... .venv/bin/python scripts/run_demo_auth_instance.py --port 8766
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from osip_dashboard.config import Settings
from osip_dashboard.main import create_app
from osip_dashboard.persistence.database import create_database_engine
from osip_dashboard.storage import LocalBlobStore

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".data" / "local-dashboard" / "runtime"
# A separate build from the primary frontend/dist: this one is compiled with
# VITE_AUTH_MODE=demo baked in (see the frontend build's env handling in
# auth/session.ts), which is what makes AuthGate render the username/password
# form instead of trusting dev headers. Build via:
#   cd frontend && VITE_AUTH_MODE=demo npm run build -- --outDir dist-demo-auth --emptyOutDir
FRONTEND_DIST = ROOT / "frontend" / "dist-demo-auth"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    secret = os.environ.get("OSIP_DEMO_JWT_SECRET")
    if not secret or len(secret) < 32:
        raise SystemExit("Set OSIP_DEMO_JWT_SECRET to a random string of at least 32 characters")

    database_url = f"sqlite:///{RUNTIME / 'dashboard.sqlite3'}"
    settings = Settings(
        environment="test",
        database_url=database_url,
        blob_root=RUNTIME / "blobs",
        identity_provider="demo",
        demo_jwt_secret=secret,
        source_first_mode=True,
        cors_origins=[f"http://127.0.0.1:{args.port}"],
    )
    engine = create_database_engine(database_url)
    blob_store = LocalBlobStore(settings.blob_root)

    app = create_app(settings=settings, engine=engine, blob_store=blob_store)

    if FRONTEND_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="dashboard-assets")

        @app.middleware("http")
        async def add_cache_headers(request, call_next):
            response = await call_next(request)
            if request.url.path.startswith("/assets/"):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                # index.html references the current hashed bundle by name, so
                # a stale cached copy would keep loading an old build
                # indefinitely (this bit us once already - see scripts/e2e_backend.py's
                # identical comment).
                response.headers["Cache-Control"] = "no-cache"
            return response

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            dist_root = FRONTEND_DIST.resolve()
            candidate = (dist_root / full_path).resolve()
            if full_path and dist_root in candidate.parents and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
