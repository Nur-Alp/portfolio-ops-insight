"""One-step local dashboard launcher for non-technical users.

Finds a suitable Python, creates/reuses .venv, installs the backend package
(unpinned, so pip resolves wheels for whatever platform this is), starts the
persistent local demo service, waits for it to answer, and opens the browser.
Only the standard library is used here since nothing else is installed yet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / ".venv"
INSTALL_MARKER = VENV_DIR / ".osip-install-fingerprint"
STATE_FILE = ROOT / ".data" / "local-dashboard" / "server.json"
DEFAULT_PORT = 8765
MIN_PYTHON = (3, 11)
CANDIDATE_PYTHONS = (
    "python3.13",
    "python3.12",
    "python3.11",
    "python3",
    "python",
)


def _log(message: str) -> None:
    print(f"[launch] {message}", flush=True)


def _venv_python() -> Path:
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _probe_version(command: str) -> tuple[int, int] | None:
    try:
        result = subprocess.run(
            [command, "-c", "import sys; print(sys.version_info[0], sys.version_info[1])"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        major, minor = (int(part) for part in result.stdout.split())
    except ValueError:
        return None
    return (major, minor)


def find_base_python() -> str:
    best: tuple[tuple[int, int], str] | None = None
    for command in CANDIDATE_PYTHONS:
        version = _probe_version(command)
        if version is None or version < MIN_PYTHON:
            continue
        if best is None or version > best[0]:
            best = (version, command)
    if best is None:
        _log(
            "No compatible Python was found. Install Python 3.11 or newer from "
            "https://www.python.org/downloads/ and run this launcher again."
        )
        raise SystemExit(1)
    return best[1]


def _port_available(port: int) -> bool:
    """Return whether the local dashboard can bind a loopback port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def diagnose_environment() -> tuple[str, list[str]]:
    """Report startup prerequisites before making any local changes.

    The launcher intentionally needs no third-party package to run this
    check.  Missing Python is actionable and stops startup; a missing venv or
    pip is reported separately because the normal startup path can repair
    those pieces with the standard library's ``venv``/``ensurepip`` modules.
    """
    _log("Checking local dashboard dependencies...")
    base_python = find_base_python()
    version = _probe_version(base_python)
    _log(f"  OK Python {version[0]}.{version[1]} ({base_python})")

    checks: list[str] = []
    for module, label in (("venv", "Python virtual-environment support"), ("ensurepip", "pip bootstrap support")):
        result = subprocess.run(
            [base_python, "-c", f"import {module}"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            _log(f"  OK {label}")
        else:
            checks.append(f"{label} is unavailable in {base_python}")
            _log(f"  MISSING {label}")

    if (ROOT / "frontend" / "dist" / "index.html").is_file():
        _log("  OK packaged frontend")
    else:
        checks.append("frontend/dist/index.html is missing; obtain a complete repository checkout")
        _log("  MISSING packaged frontend")

    try:
        data_dir = ROOT / ".data" / "local-dashboard"
        data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".diagnose-", dir=data_dir, delete=True):
            pass
        _log("  OK writable dashboard data directory")
    except OSError as exc:
        checks.append(f"dashboard data directory is not writable: {exc}")
        _log("  MISSING write permission for dashboard data")

    available_port = next((port for port in range(DEFAULT_PORT, DEFAULT_PORT + 5) if _port_available(port)), None)
    running_port = _actual_running_port()
    if available_port is None and running_port is not None:
        _log(f"  OK dashboard already owns port {running_port}")
    elif available_port is None:
        checks.append(f"ports {DEFAULT_PORT}-{DEFAULT_PORT + 4} are all in use")
        _log(f"  MISSING free local port ({DEFAULT_PORT}-{DEFAULT_PORT + 4})")
    else:
        _log(f"  OK local port {available_port}")
    return base_python, checks


def ensure_venv() -> Path:
    venv_python = _venv_python()
    if venv_python.exists():
        return venv_python
    base_python = find_base_python()
    _log(f"Creating a local Python environment ({base_python}) at {VENV_DIR}...")
    subprocess.run([base_python, "-m", "venv", str(VENV_DIR)], check=True)
    return venv_python


def _dependency_fingerprint() -> str:
    """Hash the project dependency declaration used by the editable install."""
    return hashlib.sha256((ROOT / "pyproject.toml").read_bytes()).hexdigest()


def ensure_installed(venv_python: Path) -> None:
    probe = subprocess.run(
        [str(venv_python), "-c", "import osip_dashboard"],
        capture_output=True,
        text=True,
    )
    pip_probe = subprocess.run(
        [str(venv_python), "-m", "pip", "--version"],
        capture_output=True,
        text=True,
    )
    if pip_probe.returncode != 0:
        _log("pip is missing from the local environment; bootstrapping it automatically...")
        subprocess.run([str(venv_python), "-m", "ensurepip", "--upgrade"], check=True, cwd=ROOT)

    dependency_fingerprint = _dependency_fingerprint()
    marker_matches = False
    try:
        marker_matches = INSTALL_MARKER.read_text(encoding="utf-8").strip() == dependency_fingerprint
    except OSError:
        pass
    pip_check = subprocess.run(
        [str(venv_python), "-m", "pip", "check"],
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0 and pip_check.returncode == 0 and marker_matches:
        return

    if probe.returncode != 0:
        _log("The dashboard package is not installed; installing it now...")
    elif pip_check.returncode != 0:
        _log("Some Python dependencies are missing or inconsistent; repairing the environment...")
    else:
        _log("The dependency declaration has changed; refreshing the local environment...")
    _log("Installing the dashboard backend (first run only, needs internet)...")
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
        check=True,
        cwd=ROOT,
    )
    INSTALL_MARKER.write_text(dependency_fingerprint, encoding="utf-8")
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--quiet", "-e", "."],
        check=True,
        cwd=ROOT,
    )


def _actual_running_port() -> int | None:
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return int(payload["port"])
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def start_demo(venv_python: Path) -> int:
    for port in range(DEFAULT_PORT, DEFAULT_PORT + 5):
        result = subprocess.run(
            [str(venv_python), str(ROOT / "scripts" / "demo_service.py"), "start", "--port", str(port)]
        )
        if result.returncode == 0:
            # demo_service.py reports success both when it just started on the
            # requested port and when it found an already-running instance on
            # a different one (from a prior launch) - the state file is the
            # only source of truth for which port is actually serving.
            return _actual_running_port() or port
        _log(f"Port {port} did not work, trying another...")
    _log("Could not start the demo on any port. See .data/local-dashboard/server.log for details.")
    raise SystemExit(1)


def wait_until_ready(port: int, timeout_seconds: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    url = f"http://127.0.0.1:{port}/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    return False


def dashboard_url(port: int) -> str:
    """Return a stable per-build URL so a rebuilt dashboard bypasses browser cache."""
    index_file = ROOT / "frontend" / "dist" / "index.html"
    try:
        build_token = hashlib.sha256(index_file.read_bytes()).hexdigest()[:12]
    except OSError:
        build_token = "current"
    return f"http://127.0.0.1:{port}/?build={build_token}"


def open_dashboard(url: str) -> bool:
    """Open the dashboard using the platform-native browser handoff."""
    if platform.system() == "Darwin":
        try:
            # Python's webbrowser module can return success without bringing
            # an existing browser session to the foreground on macOS.  The
            # native `open` command reliably delegates to the user's default
            # browser and makes the launch visible from Finder/Terminal.
            return subprocess.run(["open", url], check=False).returncode == 0
        except OSError:
            return False
    if platform.system() == "Windows":
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return True
        except OSError:
            return False
    try:
        return bool(webbrowser.open_new_tab(url))
    except webbrowser.Error:
        return False


def cmd_start() -> int:
    _base_python, checks = diagnose_environment()
    if checks:
        _log("Startup cannot continue until these prerequisites are fixed:")
        for check in checks:
            _log(f"  - {check}")
        return 1
    venv_python = ensure_venv()
    ensure_installed(venv_python)
    port = start_demo(venv_python)
    _log("Waiting for the dashboard to become ready...")
    if not wait_until_ready(port):
        _log(f"The dashboard did not respond in time. Check .data/local-dashboard/server.log.")
        return 1
    url = dashboard_url(port)
    _log(f"Opening {url} in your browser...")
    if not open_dashboard(url):
        _log(f"Could not open the browser automatically. Copy this URL into your browser: {url}")
        return 1
    _log("Done. The dashboard keeps running in the background.")
    return 0


def cmd_stop() -> int:
    venv_python = _venv_python()
    python = str(venv_python) if venv_python.exists() else sys.executable
    return subprocess.run([python, str(ROOT / "scripts" / "demo_service.py"), "stop"]).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "stop", "diagnose"), nargs="?", default="start")
    arguments = parser.parse_args()
    if arguments.command == "stop":
        return cmd_stop()
    if arguments.command == "diagnose":
        _base_python, checks = diagnose_environment()
        if checks:
            _log("Diagnostics found issues:")
            for check in checks:
                _log(f"  - {check}")
            return 1
        _log("All startup prerequisites are present.")
        return 0
    return cmd_start()


if __name__ == "__main__":
    raise SystemExit(main())
