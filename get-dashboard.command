#!/usr/bin/env bash
# Share this file with a non-technical macOS user. Double-clicking it downloads
# the dashboard into ~/Downloads and starts the existing one-click launcher.
set -euo pipefail

REPO_URL="https://github.com/Nur-Alp/portfolio-ops-insight.git"
ARCHIVE_URL="https://github.com/Nur-Alp/portfolio-ops-insight/archive/refs/heads/main.zip"
TARGET="${HOME}/Downloads/portfolio-operations-dashboard"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/portfolio-dashboard.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

fail() {
  echo
  echo "Dashboard setup failed: $1"
  read -n 1 -s -r -p "Press any key to close this window..."
  exit 1
}

mkdir -p "${HOME}/Downloads" || fail "Could not create the Downloads folder."

if [[ -d "$TARGET/.git" ]]; then
  echo "An existing dashboard was found in: $TARGET"
  if ! git -C "$TARGET" pull --ff-only; then
    fail "The existing checkout could not be updated automatically. Ask the owner to check it or remove that folder and try again."
  fi
elif [[ -e "$TARGET" ]]; then
  # A ZIP fallback has no .git directory. Reuse it safely on later launches;
  # only Git checkouts are updated automatically.
  [[ -x "$TARGET/start-dashboard.command" ]] || fail "$TARGET already exists but is not a usable dashboard checkout. Rename or remove that folder, then try again."
  echo "An archive-based dashboard was found in: $TARGET"
elif command -v git >/dev/null 2>&1; then
  echo "Downloading the dashboard into Downloads..."
  git clone --depth 1 "$REPO_URL" "$TARGET" || fail "Git could not download the repository."
else
  command -v curl >/dev/null 2>&1 || fail "Git and curl are both unavailable. Install Git or connect this Mac to the internet and try again."
  echo "Git was not found; downloading a repository archive instead..."
  curl --fail --location --silent --show-error "$ARCHIVE_URL" -o "$TMP_DIR/dashboard.zip" || fail "The repository archive could not be downloaded."
  command -v ditto >/dev/null 2>&1 || fail "The macOS archive utility is unavailable."
  ditto -x -k "$TMP_DIR/dashboard.zip" "$TMP_DIR/unpacked" || fail "The repository archive could not be opened."
  EXTRACTED="$(find "$TMP_DIR/unpacked" -mindepth 1 -maxdepth 1 -type d -print -quit)"
  [[ -n "$EXTRACTED" ]] || fail "The downloaded archive had an unexpected structure."
  mv "$EXTRACTED" "$TARGET" || fail "The repository could not be placed in Downloads."
fi

[[ -x "$TARGET/start-dashboard.command" ]] || fail "The downloaded repository is missing its launcher."
echo "Starting the dashboard..."
exec "$TARGET/start-dashboard.command"
