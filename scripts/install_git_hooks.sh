#!/usr/bin/env bash
# One-time setup: point git at the repo's checked-in hooks (.githooks/) so
# `git push` runs the same checks CI runs before anything leaves your
# machine. Safe to re-run; only touches this repo's local git config.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
echo "Installed: git push now runs .githooks/pre-push first (bypass once with git push --no-verify)."
