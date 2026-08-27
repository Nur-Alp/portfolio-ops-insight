"""Capture or compare deterministic OSIP recovery-drill state."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

from osip_dashboard.config import get_settings
from osip_dashboard.operations.reconciliation import (
    collect_recovery_state,
    compare_recovery_states,
)
from osip_dashboard.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from osip_dashboard.storage import LocalBlobStore


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture pre-backup state or compare an isolated restore."
    )
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        state = collect_recovery_state(session, LocalBlobStore(settings.blob_root))
    engine.dispose()

    differences: list[str] = []
    mode = "baseline"
    if args.baseline:
        mode = "restore-comparison"
        expected_document = json.loads(args.baseline.read_text(encoding="utf-8"))
        expected_state = expected_document.get("state", expected_document)
        differences = compare_recovery_states(expected_state, state)
    else:
        differences.extend(state["integrity_errors"])

    evidence = {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "result": "pass" if not differences else "fail",
        "differences": differences,
        "state": state,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"{evidence['result']}: wrote {args.output}")
    if differences:
        for difference in differences:
            print(f"- {difference}")
        sys.exit(1)


if __name__ == "__main__":
    main()
