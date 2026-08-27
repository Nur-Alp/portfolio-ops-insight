"""Fail if a real source file is invisible to git (usually a .gitignore collision).

Twice in this repo's history a generic pattern (dist/, lib/) matched a real
frontend source directory at a different depth and silently excluded it from
every commit, undetected until a clean-checkout build failed. This script
diffs the source files on disk against `git ls-files` for the directories
that matter and fails loudly if anything on disk isn't tracked.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("frontend/src", "backend", "docs", "migrations", "scripts")
SOURCE_SUFFIXES = (".ts", ".tsx", ".py", ".css", ".json", ".md")


def tracked_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", *SOURCE_DIRS],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return set(result.stdout.splitlines())


def files_on_disk() -> set[str]:
    found = set()
    for directory in SOURCE_DIRS:
        base = ROOT / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in SOURCE_SUFFIXES:
                found.add(str(path.relative_to(ROOT)))
    return found


def main() -> int:
    missing = sorted(files_on_disk() - tracked_files())
    if not missing:
        print("OK: every source file on disk is git-tracked.")
        return 0
    print("Untracked source files found (likely a .gitignore collision):", file=sys.stderr)
    for path in missing:
        result = subprocess.run(
            ["git", "check-ignore", "-v", "--no-index", path],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        reason = result.stdout.strip() or "not matched by any ignore rule (just never git add-ed?)"
        print(f"  {path}\n    -> {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
