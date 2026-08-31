"""Manage a persistent local OSIP dashboard process.

The controller keeps both the server and its local database under the
ignored ``.data/local-dashboard`` directory. This is the real, persistent
database behind ``start-dashboard.command`` - not disposable test data.
Browser-test runs (Playwright/CI) use their own temporary directory instead.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / ".data" / "local-dashboard"
PID_PATH = STATE_DIR / "server.json"
LOG_PATH = STATE_DIR / "server.log"
BACKEND_SCRIPT = ROOT / "scripts" / "e2e_backend.py"
FRONTEND_DIST = ROOT / "frontend" / "dist"


def _read_state() -> dict[str, int] | None:
    try:
        payload = json.loads(PID_PATH.read_text(encoding="utf-8"))
        if isinstance(payload["pid"], int) and isinstance(payload["port"], int):
            return {"pid": payload["pid"], "port": payload["port"]}
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return None


def _port_responds(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2):
            return True
    except urllib.error.HTTPError:
        # Any HTTP response, even a non-2xx one, means a real server is
        # listening and answering on this port.
        return True
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def _win_process_exists(pid: int) -> bool:
    """Windows-only existence check with no side effects on the process."""
    import ctypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    ERROR_ACCESS_DENIED = 5
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    # Process exists but we can't query it (rare - e.g. a privileged system
    # process) - matches the POSIX PermissionError branch in _process_exists.
    return ctypes.windll.kernel32.GetLastError() == ERROR_ACCESS_DENIED


def _process_exists(pid: int) -> bool:
    """Cross-platform "is this PID alive" check with no side effects.

    ``os.kill(pid, 0)`` is the POSIX idiom for this (signal 0 does nothing,
    but the syscall still validates the PID). Python's ``os.kill`` on Windows
    does not support signal 0 at all - it unconditionally raises
    ``OSError: [WinError 87] The parameter is incorrect`` for *any* PID,
    valid or not, which is neither ``ProcessLookupError`` nor
    ``PermissionError`` and so crashed every call site that used to try/except
    around ``os.kill`` directly. Confirmed via a real crash on Windows: it
    only happens once ``server.json`` already exists from a prior run (a
    fresh checkout has no state to check yet), which is exactly why it never
    showed up in CI - those always start from a pristine clone.
    """
    if platform.system() == "Windows":
        return _win_process_exists(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _is_running(pid: int, port: int | None = None) -> bool:
    """Report whether the recorded demo process is actually serving traffic.

    A live PID alone isn't proof: the recorded process can still exist while
    its HTTP port has died (crash-and-respawn under the same PID space, a
    hung shutdown, etc.), which previously caused status/start to report
    "running" against a port that refused every connection. When ``port`` is
    given, also require it to answer ``/health``; ``stop()``'s shutdown poll
    intentionally omits ``port`` since it only needs to know the process has
    exited, not whether it was ever reachable.
    """
    if not _process_exists(pid):
        return False
    if port is not None and not _port_responds(port):
        return False
    return True


def _remove_stale_state() -> None:
    state = _read_state()
    if state is not None and not _is_running(state["pid"], state["port"]):
        PID_PATH.unlink(missing_ok=True)


def status() -> int:
    _remove_stale_state()
    state = _read_state()
    if state is None:
        print("Demo is stopped.")
        print(f"Log: {LOG_PATH}")
        return 1
    print(f"Demo is running at http://127.0.0.1:{state['port']} (PID {state['pid']}).")
    print(f"Log: {LOG_PATH}")
    return 0


def start(port: int) -> int:
    _remove_stale_state()
    existing = _read_state()
    if existing is not None:
        print(
            "Demo is already running at "
            f"http://127.0.0.1:{existing['port']} (PID {existing['pid']})."
        )
        return 0
    if not FRONTEND_DIST.is_dir():
        print("frontend/dist is missing. Run `cd frontend && npm run build` first.", file=sys.stderr)
        return 2

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["OSIP_E2E_PORT"] = str(port)
    environment["OSIP_E2E_STATE_DIR"] = str(STATE_DIR / "runtime")
    with LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(f"\n--- starting local demo on port {port} ---\n")
        process = subprocess.Popen(
            [sys.executable, str(BACKEND_SCRIPT)],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    # Workbook import and demo-data seeding happen during startup, before
    # the process ever attempts to bind `port` - on a fresh checkout (no
    # database yet) that alone can take well over a second. A short fixed
    # sleep followed by a bare `process.poll()` check declared success
    # while the process was still busy seeding, long before it had even
    # tried (and possibly failed) to bind the port - confirmed once: the
    # process later died on an actual bind conflict, after this function
    # had already written its PID to PID_PATH and reported success, and
    # the caller's own /health check then coincidentally hit a *different*
    # process already listening on the same port instead. Poll for the
    # real outcome instead: either the process exits (a genuine startup
    # failure, e.g. the port is held by something unrelated to this app)
    # or it actually starts answering /health - whichever happens first.
    deadline = time.monotonic() + 60.0
    started_ok = False
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        if _port_responds(port):
            started_ok = True
            break
        time.sleep(0.2)

    if not started_ok:
        if process.poll() is None:
            # Still alive but never answered in time - don't leave an
            # orphaned, port-less process running in the background.
            process.terminate()
        print(f"Demo failed to start on port {port}. See {LOG_PATH}", file=sys.stderr)
        return 1

    PID_PATH.write_text(
        json.dumps({"pid": process.pid, "port": port}) + "\n", encoding="utf-8"
    )
    print(f"Demo started at http://127.0.0.1:{port} (PID {process.pid}).")
    print(f"It will keep running after this command exits. Log: {LOG_PATH}")
    return 0


def stop() -> int:
    _remove_stale_state()
    state = _read_state()
    if state is None:
        print("Demo is already stopped.")
        return 0
    os.kill(state["pid"], signal.SIGTERM)
    for _ in range(50):
        if not _is_running(state["pid"]):
            PID_PATH.unlink(missing_ok=True)
            print("Demo stopped.")
            return 0
        time.sleep(0.1)
    print(f"Demo process {state['pid']} did not stop; inspect {LOG_PATH}.", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "status", "stop", "restart"))
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if arguments.command == "start":
        return start(arguments.port)
    if arguments.command == "status":
        return status()
    if arguments.command == "stop":
        return stop()
    stopped = stop()
    return start(arguments.port) if stopped == 0 else stopped


if __name__ == "__main__":
    raise SystemExit(main())
