#!/usr/bin/env bash
# Double-click this file in Finder to open the OSIP dashboard.
# First run needs internet access and takes a minute; later runs are fast.
set -euo pipefail
cd "$(dirname "$0")"

close_launcher_window() {
  # Terminal can be configured to keep completed command windows open. Close
  # only this launcher window after the detached dashboard is ready.
  if command -v osascript >/dev/null 2>&1; then
    (
      sleep 0.2
      osascript <<'APPLESCRIPT' >/dev/null 2>&1
tell application "Terminal"
  repeat with terminalWindow in windows
    if (name of terminalWindow contains "start-dashboard.command") then
      close terminalWindow
      exit repeat
    end if
  end repeat
end tell
APPLESCRIPT
    ) &
  fi
}

# Best-effort self-update: only if this is a real git checkout (not a plain
# folder someone copied), and never fatal - no git, no network, a diverged
# local history, or anything else that would make a fast-forward pull fail
# just means "launch whatever is already here" instead of blocking startup.
if command -v git >/dev/null 2>&1 && [ -d .git ]; then
  echo "Checking for dashboard updates..."
  if git pull --ff-only >/dev/null 2>&1; then
    echo "Up to date."
  else
    echo "Could not check for updates (offline, or local files changed) - continuing with what's already installed."
  fi
fi

find_python() {
  PYTHON=""
  for candidate in python3.12 python3.11 python3 python \
    /opt/homebrew/bin/python3 /usr/local/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PYTHON="$candidate"
      return 0
    fi
  done
  return 1
}

find_python || true

# Nothing else here needs installing: SQLite (the local database) ships
# inside Python's own standard library, and the prebuilt frontend/dist/
# bundle (tracked in this repo) means Node/npm are never required just to
# run the dashboard - see .gitignore's comment on frontend/dist/. Python
# itself is the one real prerequisite.
if [ -z "$PYTHON" ]; then
  echo "Python was not found on this Mac - installing it now (one-time, official builds only)."
  if command -v brew >/dev/null 2>&1; then
    # Homebrew's own python formula: same upstream CPython, BSD-licensed
    # packaging, no admin password needed (installs under Homebrew's own
    # prefix). Preferred when available since it completes in this same
    # run - no second double-click needed.
    echo "Using Homebrew to install Python (this can take a few minutes)..."
    brew install python@3.12 || echo "Homebrew install failed - falling back to the official python.org installer."
    find_python || true
  fi
  if [ -z "$PYTHON" ]; then
    # Fallback: the official CPython build directly from python.org, under
    # the PSF License (the same license as Python itself) - not a
    # third-party or unlicensed build. macOS .pkg installers need either
    # Installer.app (interactive) or `sudo installer` (this app's own
    # first-run only, using the standard macOS installer tool, not a
    # bespoke privilege-escalation trick).
    PY_PKG_VERSION="3.12.8"
    PY_PKG_URL="https://www.python.org/ftp/python/${PY_PKG_VERSION}/python-${PY_PKG_VERSION}-macos11.pkg"
    TMP_PKG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/osip-python-install.XXXXXX")"
    trap 'rm -rf "$TMP_PKG_DIR"' EXIT
    echo "Downloading the official Python ${PY_PKG_VERSION} installer from python.org..."
    if command -v curl >/dev/null 2>&1 && curl --fail --location --silent --show-error "$PY_PKG_URL" -o "$TMP_PKG_DIR/python.pkg"; then
      echo "Installing Python system-wide - macOS will ask for your account password (this is Apple's own Installer, not a script prompt)."
      if sudo installer -pkg "$TMP_PKG_DIR/python.pkg" -target / ; then
        find_python || true
      fi
    fi
  fi
fi

if [ -z "$PYTHON" ]; then
  echo "Python could not be installed automatically."
  echo "Install it yourself from https://www.python.org/downloads/ and double-click this file again."
  read -n 1 -s -r -p "Press any key to close this window..."
  exit 1
fi

if "$PYTHON" scripts/launch.py start; then
  # A successful launch hands the dashboard to its detached service. Exiting
  # here lets macOS close the temporary Terminal window automatically. The
  # AppleScript fallback also handles Terminal's "Process completed" setting.
  close_launcher_window
  exit 0
else
  status=$?
  echo
  echo "Something went wrong. See the messages above for details."
  read -n 1 -s -r -p "Press any key to close this window..."
  exit "$status"
fi
