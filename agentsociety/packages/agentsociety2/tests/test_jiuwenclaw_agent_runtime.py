import asyncio
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import anyio
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from websockets.asyncio import client as websocket_client


def _load_jiuwenclaw_agent_class():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "custom" / "agents" / "jiuwenclaw_agent.py"
    spec = importlib.util.spec_from_file_location("god_custom_jiuwenclaw_agent", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.JiuwenClawAgent


@pytest.mark.parametrize("case", ["disabled", "missing_key", "success", "unauthorized", "rate_limit", "malformed", "unknown_skill", "invalid_confidence", "llm_failure", "unmounted_baseline", "timeout"])
def test_jev_shadow_keeps_original_skill_decision(monkeypatch, tmp_path, case):
    agent_class = _load_jiuwenclaw_agent_class()
    agent = agent_class(id=1, name="Test Resident", profile={"name": "Test Resident"})
    monkeypatch.setenv("GOD_JEV_SHADOW", "0" if case == "disabled" else "1")
    monkeypatch.setenv("TYPESAFE_API_KEY", "" if case == "missing_key" else "test-jev-secret")
    monkeypatch.setenv("GOD_JEV_MODEL", "jev-test-model")
    baseline = {"selected_skill_id": "routine.daily", "args": {"kept": "original"}, "reason": "original", "public_summary": "原有决定"}
    if case == "unmounted_baseline":
        baseline["selected_skill_id"] = "unmounted.skill"
    requests = []
    jev_started = asyncio.Event()

    async def endpoint(request):
        requests.append(await request.json())
        jev_started.set()
        assert request.headers["Authorization"] == "Bearer test-jev-secret"
        if case in ("unauthorized", "rate_limit"):
            return web.Response(status=401 if case == "unauthorized" else 429, text="test-jev-secret")
        if case == "malformed":
            return web.json_response({})
        if case == "timeout":
            await asyncio.sleep(6)
        return web.json_response({
            "model": "jev-test-pinned",
            "answers": {"skill": {
                "type": "choice",
                "choice": "unmounted.skill" if case == "unknown_skill" else "social.reply",
                "confidence": True if case == "invalid_confidence" else 0.9,
                "probabilities": {"routine.daily": 0.1, "social.reply": 0.9},
            }},
            "usage": {"input_tokens": 100, "output_tokens": 0},
        })

    async def original_request(_prompt):
        if case == "success":
            await asyncio.wait_for(jev_started.wait(), timeout=2)
        if case == "llm_failure":
            raise RuntimeError("original runtime unavailable")
        return json.dumps(baseline)

    async def run_case():
        app = web.Application()
        app.router.add_post("/v1/systemone", endpoint)
        async with TestServer(app) as server:
            # Redirect only the transport; exercise production request/response handling.
            monkeypatch.setitem(agent_class._select_next_skill.__globals__, "JEV_API_URL", str(server.make_url("/v1/systemone")))
            agent._send_jiuwenclaw_request = original_request
            if case == "unmounted_baseline":
                await agent.init(_Env(tmp_path))
                async def observe():
                    return {"location_id": "school"}
                agent._observe_environment = observe
                await agent.step(60, datetime(2026, 10, 2, tzinfo=timezone.utc))
                snapshot = json.loads((tmp_path / "agents/agent_0001/.runtime/logs/agent_state_snapshot.json").read_text())
                result = snapshot["last_skill_decision"]
            else:
                result = await agent._select_next_skill(
                    tick=60, t=datetime(2026, 10, 2, tzinfo=timezone.utc),
                    observation={"location_id": "school"},
                    catalog=[{"name": "routine.daily", "description": "Follow daily routine"}, {"name": "social.reply", "description": "Reply to a message"}],
                    mounted_skill_ids=["routine.daily", "social.reply"],
                    pending_interventions=[], broadcast_result="",
                )
        assert result["selected_skill_id"] == "routine.daily"
        if case in ("llm_failure", "unmounted_baseline"):
            assert result["fallback"] is True
        else:
            assert {key: result[key] for key in baseline} == baseline
        if case == "disabled":
            assert not requests
            assert "jev_shadow" not in result
        elif case == "missing_key":
            assert not requests
            assert result["jev_shadow"]["status"] == "skipped"
        else:
            assert len(requests) == 1
            assert requests[0]["model"] == "jev-test-model"
            assert requests[0]["questions"]["skill"]["type"] == "choice"
            if case != "unmounted_baseline":
                assert set(requests[0]["questions"]["skill"]["criteria"]) == {"routine.daily", "social.reply"}
            comparison = result["jev_shadow"]
            assert "test-jev-secret" not in json.dumps(comparison)
            if case in ("success", "llm_failure", "unmounted_baseline"):
                assert comparison["status"] == "completed"
                assert comparison["choice"] == "social.reply"
                assert comparison["matches_selected_skill"] is False
                assert comparison["model"] == "jev-test-pinned"
                assert comparison["latency_ms"] >= 0
                assert comparison["usage"]["input_tokens"] == 100
            else:
                assert comparison["status"] == "error"

    anyio.run(run_case)


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


def test_jiuwenclaw_runtime_path_stays_inside_agent_workspace(tmp_path):
    JiuwenClawAgent = _load_jiuwenclaw_agent_class()
    agent = JiuwenClawAgent(id=1, name="Runtime Tester", profile={"name": "Runtime Tester"})
    agent._agent_work_dir = tmp_path / "agents" / "agent_0001"

    target = agent._runtime_path("memory/state.json")

    assert target == agent._agent_work_dir.resolve() / "memory" / "state.json"
    assert target.parent.exists()


def test_jiuwenclaw_runtime_path_rejects_workspace_escape(tmp_path):
    JiuwenClawAgent = _load_jiuwenclaw_agent_class()
    agent = JiuwenClawAgent(id=1, name="Runtime Tester", profile={"name": "Runtime Tester"})
    agent._agent_work_dir = tmp_path / "agents" / "agent_0001"

    try:
        agent._runtime_path("../../outside.json")
    except ValueError as exc:
        assert "Path escapes agent workspace" in str(exc)
    else:
        raise AssertionError("workspace escape must be rejected")


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


def test_jiuwenclaw_websocket_uses_agent_server_keepalive(monkeypatch):
    JiuwenClawAgent = _load_jiuwenclaw_agent_class()
    agent = JiuwenClawAgent(id=1, name="Runtime Tester", profile={"name": "Runtime Tester"})
    captured = {}
    expected_socket = object()

    async def connect(uri, **kwargs):
        captured["uri"] = uri
        captured["kwargs"] = kwargs
        return expected_socket

    monkeypatch.setattr(websocket_client, "connect", connect)
    result = anyio.run(agent._open_websocket, "ws://127.0.0.1:18092")

    assert result is expected_socket
    assert captured == {
        "uri": "ws://127.0.0.1:18092",
        "kwargs": {
            "origin": "http://127.0.0.1:18092",
            "ping_interval": 30,
            "ping_timeout": 300,
        },
    }
