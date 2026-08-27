"""Create a verified OSIP database/blob backup archive."""

from __future__ import annotations

import argparse
from pathlib import Path

from osip_dashboard.config import get_settings
from osip_dashboard.operations.backup import create_backup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    settings = get_settings()
    manifest = create_backup(
        database_url=settings.database_url,
        blob_root=settings.blob_root,
        destination=args.destination,
    )
    print(f"Created {args.destination} at {manifest['created_at']}")


if __name__ == "__main__":
    main()
