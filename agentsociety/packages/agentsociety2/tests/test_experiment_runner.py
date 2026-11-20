import json
from unittest.mock import AsyncMock

import anyio
import pytest

from agentsociety2.society.cli import AgentSociety, CodeGenRouter, ExperimentRunner


def test_incomplete_run_records_failure_after_later_steps(tmp_path, monkeypatch):
    config = tmp_path / "init_config.json"
    config.write_text(json.dumps({
        "env_modules": [{"module_type": "TestEnv", "kwargs": {}}],
        "agents": [{"agent_type": "TestAgent", "agent_id": 1, "kwargs": {"id": 1}}],
    }), encoding="utf-8")
    steps = tmp_path / "steps.yaml"
    steps.write_text(json.dumps({
        "start_t": "2026-01-01T08:00:00", "steps": [{"type": "run", "num_steps": 1}] * 2,
    }), encoding="utf-8")
    runner = ExperimentRunner(tmp_path / "run")
    monkeypatch.setenv("AGENTSOCIETY_LLM_API_KEY", "local-test")
    monkeypatch.setattr(runner, "_create_env_modules", lambda *args: [])
    monkeypatch.setattr(runner, "_create_agents", lambda *args, **kwargs: [])
    monkeypatch.setattr(CodeGenRouter, "init", AsyncMock())
    run = AsyncMock(side_effect=[OSError("No space left on device"), None])
    monkeypatch.setattr(AgentSociety, "run", run)

    with pytest.raises(RuntimeError, match="No space left on device"):
        anyio.run(runner.run, config, steps)

    assert run.await_count == 2
    status = json.loads(runner.pid_file.read_text(encoding="utf-8"))
    assert status["status"] == "failed" and "step 0 (run)" in status["error"]


def test_failed_status_write_preserves_previous_progress(tmp_path, monkeypatch):
    runner = ExperimentRunner(tmp_path / "run")
    runner._update_pid_file("running", step_count=6)
    previous = runner.pid_file.read_bytes()

    def disk_full(data, handle, **kwargs):
        handle.write('{"pid":')
        raise OSError("No space left on device")

    monkeypatch.setattr(json, "dump", disk_full)
    with pytest.raises(OSError, match="No space left"):
        runner._update_pid_file("completed")

    assert runner.pid_file.read_bytes() == previous
    assert set(runner.run_dir.iterdir()) == {runner.artifacts_dir, runner.pid_file}
