import asyncio
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import anyio


def _load_jiuwenclaw_agent_class():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "custom" / "agents" / "jiuwenclaw_agent.py"
    spec = importlib.util.spec_from_file_location("god_custom_jiuwenclaw_agent", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.JiuwenClawAgent


class _Env:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.env_modules = []


class _NoRunDirEnv:
    env_modules: list = []


class _DummyWebSocket:
    async def send(self, _payload: str) -> None:
        return None


async def _prepare_agent_for_timed_request(agent, receive_response):
    async def ensure_connected():
        agent._ws = _DummyWebSocket()

    agent._ensure_connected = ensure_connected
    agent._receive_matching_response = receive_response


def test_jiuwenclaw_agent_forces_skill_runtime_when_legacy_false(tmp_path):
    JiuwenClawAgent = _load_jiuwenclaw_agent_class()
    agent = JiuwenClawAgent(
        id=1,
        name="Runtime Tester",
        profile={"name": "Runtime Tester"},
        enable_skill_runtime=False,
        skill_ids=["class.learn"],
    )

    async def run_case():
        await agent.init(_Env(tmp_path))
        dumped = await agent.dump()
        assert dumped["enable_skill_runtime"] is True

        config_path = tmp_path / "agents" / "agent_0001" / "agent_config.json"
        assert '"enable_skill_runtime": true' in config_path.read_text(encoding="utf-8")

        async def observe_environment():
            return {"location_id": "school", "known_locations": [], "known_interactions": []}

        async def run_skill_runtime(**_kwargs):
            return {"ok": True, "public_summary": "skill runtime step", "environment_effects": []}

        async def fail_direct_request(_prompt):
            raise AssertionError("step must not call the legacy direct JiuwenClaw path")

        agent._observe_environment = observe_environment
        agent._run_skill_runtime = run_skill_runtime
        agent._send_jiuwenclaw_request = fail_direct_request

        result = await agent.step(60, datetime(2026, 5, 26, tzinfo=timezone.utc))
        assert result == "skill runtime step"

    anyio.run(run_case)


def test_jiuwenclaw_agent_init_without_run_dir_does_not_create_workspace(tmp_path, monkeypatch):
    JiuwenClawAgent = _load_jiuwenclaw_agent_class()
    agent = JiuwenClawAgent(
        id=1,
        name="Runtime Tester",
        profile={"name": "Runtime Tester"},
        enable_skill_runtime=False,
    )

    async def run_case():
        monkeypatch.chdir(tmp_path)
        await agent.init(_NoRunDirEnv())

        assert agent._agent_work_dir is None
        assert not (tmp_path / "agents").exists()

        async def fail_direct_request(_prompt):
            raise AssertionError("step must not call the legacy direct JiuwenClaw path")

        agent._send_jiuwenclaw_request = fail_direct_request
        result = await agent.step(60, datetime(2026, 5, 26, tzinfo=timezone.utc))
        assert result == "技能步骤已完成。"
        assert not (tmp_path / "agents").exists()

    anyio.run(run_case)


def test_jiuwenclaw_agent_accepts_mounted_skill_ids_from_config():
    JiuwenClawAgent = _load_jiuwenclaw_agent_class()
    agent = JiuwenClawAgent(
        id=2,
        name="Mounted Skills Tester",
        profile={"name": "Mounted Skills Tester"},
        common_skill_ids=["routine.daily", "social.reply"],
        mounted_skill_ids=[
            "routine.daily",
            "social.reply",
            "class.learn",
            "info.research",
        ],
    )

    dumped = anyio.run(agent.dump)
    assert dumped["enable_skill_runtime"] is True
    assert dumped["common_skill_ids"] == ["routine.daily", "social.reply"]
    assert dumped["skill_ids"] == ["class.learn", "info.research"]
    assert dumped["mounted_skill_ids"] == [
        "routine.daily",
        "social.reply",
        "class.learn",
        "info.research",
    ]


def test_jiuwenclaw_request_concurrency_allows_overlapping_agents(monkeypatch):
    monkeypatch.setenv("AGENTSOCIETY_JIUWENCLAW_REQUEST_CONCURRENCY", "2")
    JiuwenClawAgent = _load_jiuwenclaw_agent_class()
    agents = [
        JiuwenClawAgent(id=1, name="Agent 1", profile={"name": "Agent 1"}),
        JiuwenClawAgent(id=2, name="Agent 2", profile={"name": "Agent 2"}),
    ]
    active_requests = 0
    max_active_requests = 0

    async def receive_response(_request_id):
        nonlocal active_requests, max_active_requests
        active_requests += 1
        max_active_requests = max(max_active_requests, active_requests)
        await anyio.sleep(0.05)
        active_requests -= 1
        return {"body": {"result": {"content": "ok"}}}

    async def run_case():
        for agent in agents:
            await _prepare_agent_for_timed_request(agent, receive_response)

        results = await asyncio.gather(
            *(agent._send_jiuwenclaw_request("prompt") for agent in agents)
        )

        assert results == ["ok", "ok"]
        assert max_active_requests == 2

    anyio.run(run_case)


def test_jiuwenclaw_request_concurrency_can_be_limited_to_one(monkeypatch):
    monkeypatch.setenv("AGENTSOCIETY_JIUWENCLAW_REQUEST_CONCURRENCY", "1")
    JiuwenClawAgent = _load_jiuwenclaw_agent_class()
    agents = [
        JiuwenClawAgent(id=1, name="Agent 1", profile={"name": "Agent 1"}),
        JiuwenClawAgent(id=2, name="Agent 2", profile={"name": "Agent 2"}),
    ]
    active_requests = 0
    max_active_requests = 0

    async def receive_response(_request_id):
        nonlocal active_requests, max_active_requests
        active_requests += 1
        max_active_requests = max(max_active_requests, active_requests)
        await anyio.sleep(0.05)
        active_requests -= 1
        return {"body": {"result": {"content": "ok"}}}

    async def run_case():
        for agent in agents:
            await _prepare_agent_for_timed_request(agent, receive_response)

        results = await asyncio.gather(
            *(agent._send_jiuwenclaw_request("prompt") for agent in agents)
        )

        assert results == ["ok", "ok"]
        assert max_active_requests == 1

    anyio.run(run_case)


def test_jiuwenclaw_request_concurrency_invalid_env_falls_back_to_default(monkeypatch):
    JiuwenClawAgent = _load_jiuwenclaw_agent_class()

    monkeypatch.setenv("AGENTSOCIETY_JIUWENCLAW_REQUEST_CONCURRENCY", "not-an-int")
    assert JiuwenClawAgent._request_concurrency_limit() == 24

    monkeypatch.setenv("AGENTSOCIETY_JIUWENCLAW_REQUEST_CONCURRENCY", "0")
    assert JiuwenClawAgent._request_concurrency_limit() == 1
