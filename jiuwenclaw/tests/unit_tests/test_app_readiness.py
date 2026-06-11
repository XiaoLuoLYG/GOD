import importlib
import sys

import pytest


class _FakeSocket:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _FakeProcess:
    def __init__(self, returncode=None):
        self.returncode = returncode
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 143

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = 137


def _load_app_module(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    sys.modules.pop("jiuwenclaw.app", None)
    return importlib.import_module("jiuwenclaw.app")


def test_wait_for_agent_server_uses_tcp_readiness(monkeypatch, tmp_path):
    app = _load_app_module(monkeypatch, tmp_path)
    calls = []

    def fake_create_connection(address, timeout):
        calls.append((address, timeout))
        return _FakeSocket()

    monkeypatch.setattr(app.socket, "create_connection", fake_create_connection)

    app._wait_for_agent_server(_FakeProcess(), host="127.0.0.1", port=19092, timeout=1)

    assert calls == [(("127.0.0.1", 19092), 0.5)]


def test_wait_for_agent_server_fails_when_process_exits(monkeypatch, tmp_path):
    app = _load_app_module(monkeypatch, tmp_path)

    with pytest.raises(RuntimeError, match="exited before it became ready"):
        app._wait_for_agent_server(_FakeProcess(returncode=3), host="127.0.0.1", port=19092, timeout=1)


def test_agent_server_endpoint_reads_runtime_env(monkeypatch, tmp_path):
    app = _load_app_module(monkeypatch, tmp_path)
    monkeypatch.setenv("AGENT_SERVER_HOST", "0.0.0.0")
    monkeypatch.setenv("AGENT_SERVER_PORT", "19092")

    assert app._agent_server_endpoint() == ("127.0.0.1", 19092)
