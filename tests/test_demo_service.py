import importlib.util
import json
import os
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "demo_service.py"
_spec = importlib.util.spec_from_file_location("demo_service", MODULE_PATH)
demo_service = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo_service)


def test_is_running_true_for_live_pid_when_no_port_given():
    assert demo_service._is_running(os.getpid()) is True


def test_is_running_false_for_a_dead_pid():
    assert demo_service._is_running(2**31 - 1) is False


def test_is_running_false_when_pid_alive_but_port_unresponsive(monkeypatch):
    # Reproduces the previously-reported false-positive: the recorded process
    # still exists but its HTTP port refuses connections (crash-and-respawn
    # under the same PID space, a hung shutdown, etc.).
    monkeypatch.setattr(demo_service, "_port_responds", lambda port: False)
    assert demo_service._is_running(os.getpid(), 12345) is False


def test_is_running_true_when_pid_alive_and_port_responds(monkeypatch):
    monkeypatch.setattr(demo_service, "_port_responds", lambda port: True)
    assert demo_service._is_running(os.getpid(), 12345) is True


def test_process_exists_uses_the_windows_check_on_windows(monkeypatch):
    """Regression: os.kill(pid, 0) - the POSIX "does this PID exist" idiom -
    unconditionally raises OSError [WinError 87] on Windows for any PID,
    valid or not, since Windows' os.kill doesn't support signal 0. That
    crashed every real Windows run once server.json already existed from a
    prior launch. _process_exists must route to the ctypes-based Windows
    check instead of ever calling os.kill(pid, 0) there."""
    monkeypatch.setattr(demo_service.platform, "system", lambda: "Windows")
    monkeypatch.setattr(demo_service, "_win_process_exists", lambda pid: True)

    def _os_kill_should_not_be_called(pid, sig):
        raise AssertionError("os.kill(pid, 0) must not be called on Windows")

    monkeypatch.setattr(demo_service.os, "kill", _os_kill_should_not_be_called)

    assert demo_service._process_exists(4242) is True


def test_process_exists_reflects_the_windows_check_result(monkeypatch):
    monkeypatch.setattr(demo_service.platform, "system", lambda: "Windows")
    monkeypatch.setattr(demo_service, "_win_process_exists", lambda pid: False)
    assert demo_service._process_exists(4242) is False


class _FakeProcess:
    """Stands in for subprocess.Popen: .poll() is None until told to "exit"."""

    def __init__(self):
        self.pid = 999999
        self.terminated = False
        self._poll_calls = 0
        self._exit_after_polls: int | None = None

    def poll(self):
        self._poll_calls += 1
        if self._exit_after_polls is not None and self._poll_calls >= self._exit_after_polls:
            return 1
        return None

    def terminate(self):
        self.terminated = True


def _prepare_state_dir(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    monkeypatch.setattr(demo_service, "STATE_DIR", state_dir)
    monkeypatch.setattr(demo_service, "PID_PATH", state_dir / "server.json")
    monkeypatch.setattr(demo_service, "LOG_PATH", state_dir / "server.log")
    monkeypatch.setattr(demo_service, "FRONTEND_DIST", demo_service.ROOT / "frontend" / "dist")
    monkeypatch.setattr(demo_service, "_read_state", lambda: None)
    monkeypatch.setattr(demo_service, "_remove_stale_state", lambda: None)
    monkeypatch.setattr(demo_service.time, "sleep", lambda seconds: None)
    return state_dir


def test_start_reports_failure_when_the_process_dies_before_ever_binding_the_port(monkeypatch, tmp_path):
    """Regression: a process still busy seeding on a fresh checkout (poll()
    still None, port not yet responding) used to be declared "started"
    after one fixed one-second sleep - even when it later died on a real
    port-bind conflict. start() must not report success (or write a PID)
    until the process either genuinely answers /health or has exited."""
    state_dir = _prepare_state_dir(monkeypatch, tmp_path)
    fake_process = _FakeProcess()
    fake_process._exit_after_polls = 3  # "dies" a few polls in, like a real bind failure would
    monkeypatch.setattr(demo_service.subprocess, "Popen", lambda *args, **kwargs: fake_process)
    monkeypatch.setattr(demo_service, "_port_responds", lambda port: False)

    result = demo_service.start(8765)

    assert result == 1
    assert not (state_dir / "server.json").exists()


def test_start_waits_past_the_old_one_second_window_for_a_slow_first_run_seed(monkeypatch, tmp_path):
    """A process that's still alive and simply hasn't finished seeding yet
    (poll() stays None) must be given real time to start answering /health,
    not judged only at a fixed one-second mark."""
    state_dir = _prepare_state_dir(monkeypatch, tmp_path)
    fake_process = _FakeProcess()
    responds_calls = {"count": 0}

    def _port_responds(port):
        responds_calls["count"] += 1
        return responds_calls["count"] >= 5  # "finishes seeding" a few polls in

    monkeypatch.setattr(demo_service.subprocess, "Popen", lambda *args, **kwargs: fake_process)
    monkeypatch.setattr(demo_service, "_port_responds", _port_responds)

    result = demo_service.start(8765)

    assert result == 0
    written = json.loads((state_dir / "server.json").read_text(encoding="utf-8"))
    assert written == {"pid": fake_process.pid, "port": 8765}
    assert fake_process.terminated is False
