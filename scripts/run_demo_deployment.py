"""Serve the shareable demo deployment (backend + built frontend, one
process) against the dedicated .data/demo-deployment database - never the
real .data/local-dashboard data. See docs/demo-deployment.md.

Serves frontend/dist-demo, NOT frontend/dist: scripts/e2e_backend.py (the
real local dashboard on port 8765, per .data/local-dashboard/server.json)
also serves frontend/dist as static files. Building the demo frontend
(VITE_AUTH_MODE=demo) into the same dist/ directory overwrites the real
dashboard's build with one whose login flow that dashboard's backend
(identity_provider=development) can't serve, breaking it outright - this
happened once already. Always build the demo frontend with
`npm run build -- --outDir dist-demo`.

Not part of the committed automated tooling: a throwaway runner for the
"quick tunnel from a machine that stays on" hosting path.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from osip_dashboard.config import Settings
from osip_dashboard.main import create_app
from osip_dashboard.persistence.database import create_database_engine
from osip_dashboard.storage import LocalBlobStore

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / ".data" / "demo-deployment"

settings = Settings(
    environment="development",
    database_url=f"sqlite:///{DEMO_DIR / 'dashboard.sqlite3'}",
    blob_root=DEMO_DIR / "blobs",
    reference_data_root=DEMO_DIR / "reference-data",
    identity_provider="demo",
    demo_jwt_secret=(DEMO_DIR / "jwt-secret.txt").read_text(encoding="utf-8").strip(),
    cors_origins=["http://127.0.0.1:8790", "http://localhost:8790"],
)
engine = create_database_engine(settings.database_url)
app = create_app(settings=settings, engine=engine, blob_store=LocalBlobStore(settings.blob_root))

frontend_dist = ROOT / "frontend" / "dist-demo"
app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="dashboard-assets")


@app.middleware("http")
async def add_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/assets/"):
        # Vite content-hashes these filenames - any content change gets a
        # new URL, so caching forever is always safe.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        # index.html (served both directly and via the SPA fallback below)
        # references the current hashed bundle by name, so it must always be
        # revalidated. Neither route set any Cache-Control before this - with
        # only Last-Modified/ETag and no explicit directive, browsers (Safari
        # in particular) may apply heuristic freshness and skip even a
        # conditional request on reload, which is exactly what let a stale
        # bundle keep loading here after a plain refresh.
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str) -> FileResponse:
    dist_root = frontend_dist.resolve()
    candidate = (dist_root / full_path).resolve()
    if full_path and dist_root in candidate.parents and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(frontend_dist / "index.html")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8790")), log_level="info")
