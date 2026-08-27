"""Snapshot the local dashboard's real database before doing anything risky.

Safe to run while the dashboard is running: uses sqlite3's online backup API
(a consistent point-in-time copy, not a raw file copy) so it never captures a
half-written page. Keeps the most recent N backups and prunes older ones.

Usage:
    .venv/bin/python scripts/backup_local_dashboard.py
    .venv/bin/python scripts/backup_local_dashboard.py --keep 20
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / ".data" / "local-dashboard" / "runtime"
DATABASE_PATH = RUNTIME_DIR / "dashboard.sqlite3"
BLOBS_DIR = RUNTIME_DIR / "blobs"
BACKUPS_DIR = ROOT / ".data" / "local-dashboard" / "backups"


def backup(keep: int) -> Path | None:
    if not DATABASE_PATH.exists():
        print(f"No database at {DATABASE_PATH}; nothing to back up.")
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = BACKUPS_DIR / stamp
    destination.mkdir(parents=True, exist_ok=True)

    source_conn = sqlite3.connect(f"file:{DATABASE_PATH}?mode=ro", uri=True)
    dest_conn = sqlite3.connect(destination / "dashboard.sqlite3")
    with dest_conn:
        source_conn.backup(dest_conn)
    source_conn.close()
    dest_conn.close()

    if BLOBS_DIR.exists():
        shutil.copytree(BLOBS_DIR, destination / "blobs")

    print(f"Backed up to {destination}")
    _prune(keep)
    return destination


def _prune(keep: int) -> None:
    if not BACKUPS_DIR.exists():
        return
    snapshots = sorted((p for p in BACKUPS_DIR.iterdir() if p.is_dir()), key=lambda p: p.name)
    for stale in snapshots[:-keep] if keep > 0 else []:
        shutil.rmtree(stale)
        print(f"Pruned old backup {stale.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", type=int, default=10, help="How many recent backups to retain (default: 10)")
    arguments = parser.parse_args()
    backup(arguments.keep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
