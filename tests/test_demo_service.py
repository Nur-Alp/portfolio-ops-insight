import importlib.util
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
