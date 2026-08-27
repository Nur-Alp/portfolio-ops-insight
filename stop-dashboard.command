#!/usr/bin/env bash
# Double-click this file in Finder to stop the OSIP dashboard.
set -euo pipefail
cd "$(dirname "$0")"

close_launcher_window() {
  if command -v osascript >/dev/null 2>&1; then
    (
      sleep 0.2
      osascript <<'APPLESCRIPT' >/dev/null 2>&1
tell application "Terminal"
  repeat with terminalWindow in windows
    if (name of terminalWindow contains "stop-dashboard.command") then
      close terminalWindow
      exit repeat
    end if
  end repeat
end tell
APPLESCRIPT
    ) &
  fi
}

PYTHON=""
for candidate in python3.12 python3.11 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  echo "Python was not found on this Mac."
  read -n 1 -s -r -p "Press any key to close this window..."
  exit 1
fi

if "$PYTHON" scripts/launch.py stop; then
  close_launcher_window
  exit 0
else
  status=$?
  echo "Something went wrong. See the messages above for details."
  read -n 1 -s -r -p "Press any key to close this window..."
  exit "$status"
fi
