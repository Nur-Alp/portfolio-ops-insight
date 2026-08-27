#!/usr/bin/env bash
# Send just this one file to someone to give them the dashboard. Double-click
# it once to install; after that, use start-dashboard.command inside the
# installed folder (it self-updates on every launch - see that file).
set -euo pipefail

REPO_URL="https://github.com/Nur-Alp/portfolio-ops-insight.git"
TARGET_DIR="$HOME/PortfolioOpsInsight-Dashboard"

if ! command -v git >/dev/null 2>&1; then
  echo "Git was not found on this Mac."
  echo "Opening a Terminal and running 'git' usually offers to install Apple's Command Line Tools automatically."
  echo "Install it, then double-click this file again."
  read -n 1 -s -r -p "Press any key to close this window..."
  exit 1
fi

if [ -d "$TARGET_DIR/.git" ]; then
  echo "Dashboard already installed at $TARGET_DIR - starting it..."
else
  echo "Installing the dashboard to $TARGET_DIR ..."
  if ! git clone "$REPO_URL" "$TARGET_DIR"; then
    echo
    echo "Could not download the dashboard. This is a private repository - you need"
    echo "read access to it first:"
    echo "  $REPO_URL"
    echo "Ask to be added as a collaborator, then double-click this file again."
    read -n 1 -s -r -p "Press any key to close this window..."
    exit 1
  fi
fi

cd "$TARGET_DIR"
exec ./start-dashboard.command
