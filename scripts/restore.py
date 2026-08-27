"""Restore a verified OSIP database/blob backup archive."""

from __future__ import annotations

import argparse
from pathlib import Path

from osip_dashboard.config import get_settings
from osip_dashboard.operations.backup import restore_backup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--confirm-destructive-restore", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    manifest = restore_backup(
        database_url=settings.database_url,
        blob_root=settings.blob_root,
        archive_path=args.archive,
        confirmed=args.confirm_destructive_restore,
    )
    print(f"Restored backup created at {manifest['created_at']}")


if __name__ == "__main__":
    main()
