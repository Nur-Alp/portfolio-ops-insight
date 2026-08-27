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

PYTHON=""
for candidate in python3.12 python3.11 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  echo "Python was not found on this Mac."
  echo "Install it from https://www.python.org/downloads/ and double-click this file again."
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
