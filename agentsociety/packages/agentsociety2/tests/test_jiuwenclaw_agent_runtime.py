import asyncio
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import anyio
import pytest
from websockets.asyncio import client as websocket_client
from websockets.asyncio.server import serve


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


def _skill_choice_kwargs():
    return {
        "tick": 60,
        "t": datetime(2026, 5, 26, tzinfo=timezone.utc),
        "observation": {},
        "catalog": [{"name": "routine.daily", "description": "day"}],
        "mounted_skill_ids": ["routine.daily", "safety.respond"],
        "pending_interventions": [],
        "broadcast_result": "",
    }


def _ack() -> str:
    return json.dumps({"type": "event", "event": "connection.ack"})


def _final_frame(request_id: str, content: str) -> str:
    return json.dumps(
        {
            "request_id": request_id,
            "is_final": True,
            "body": {"result": {"content": content}},
        }
    )


def _keepalive_frame(request_id: str) -> str:
    return json.dumps(
        {
            "request_id": request_id,
            "is_final": False,
            "payload": {"event_type": "keepalive"},
        }
    )


def test_silent_open_socket_fails_at_request_timeout_and_reconnects():
    """Session cancel leaves the socket ESTABLISHED and sends no final frame.

    recv() does not raise. The request deadline must still end the attempt,
    release the shared semaphore, and let the next request open a new socket.
    """

    JiuwenClawAgent = _load_jiuwenclaw_agent_class()
    JiuwenClawAgent._request_semaphore = None
    JiuwenClawAgent._request_semaphore_loop = None

    async def run_case():
        seen = {"n": 0}

        async def handler(ws):
            await ws.send(_ack())
            raw = await ws.recv()
            data = json.loads(raw)
            seen["n"] += 1
            if seen["n"] == 1:
                try:
                    while True:
                        await ws.recv()
                except Exception:
                    return
            await ws.send(_final_frame(data["request_id"], '{"selected_skill_id":"routine.daily"}'))

        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            agent = JiuwenClawAgent(
                id=6,
                name="Agent 6",
                profile={"name": "Agent 6"},
                jiuwenclaw_ws_url=f"ws://127.0.0.1:{port}",
                request_timeout=0.4,
            )
            loop = asyncio.get_running_loop()
            started = loop.time()
            decision = await agent._select_next_skill(**_skill_choice_kwargs())
            elapsed = loop.time() - started
            assert elapsed < 1.2
            assert elapsed >= 0.4
            assert decision["fallback"] is True
            assert decision["selected_skill_id"] == "routine.daily"
            assert agent._ws is None
            assert agent._last_response.startswith("九问技能选择失败")
            assert seen["n"] == 1
            _semaphore, limit = agent._request_semaphore_for_current_loop()
            assert limit == 24

            started = loop.time()
            text = await agent._send_jiuwenclaw_request("again")
            assert loop.time() - started < 2
            assert "routine.daily" in text
            assert agent._ws is not None
            assert seen["n"] == 2

    anyio.run(run_case)


def test_nonfinal_chunks_do_not_extend_the_request_deadline():
    JiuwenClawAgent = _load_jiuwenclaw_agent_class()

    async def run_case():
        seen = {"n": 0}

        async def handler(ws):
            await ws.send(_ack())
            raw = await ws.recv()
            data = json.loads(raw)
            seen["n"] += 1
            if seen["n"] == 1:
                try:
                    while True:
                        await ws.send(_keepalive_frame(data["request_id"]))
                        await asyncio.sleep(0.05)
                except Exception:
                    return
            await ws.send(_final_frame(data["request_id"], "done"))

        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            agent = JiuwenClawAgent(
                id=7,
                name="Agent 7",
                profile={"name": "Agent 7"},
                jiuwenclaw_ws_url=f"ws://127.0.0.1:{port}",
                request_timeout=0.45,
            )
            loop = asyncio.get_running_loop()
            started = loop.time()
            with pytest.raises(TimeoutError):
                await agent._send_jiuwenclaw_request("keepalive only")
            elapsed = loop.time() - started
            assert elapsed < 0.9
            assert seen["n"] == 1

            text = await agent._send_jiuwenclaw_request("again")
            assert text == "done"
            assert seen["n"] == 2

    anyio.run(run_case)


def test_connect_is_inside_the_request_deadline():
    JiuwenClawAgent = _load_jiuwenclaw_agent_class()

    async def run_case():
        agent = JiuwenClawAgent(
            id=1,
            name="Agent 1",
            profile={"name": "Agent 1"},
            request_timeout=0.3,
        )

        async def hang_connect(_uri: str):
            await asyncio.Future()

        agent._open_websocket = hang_connect
        loop = asyncio.get_running_loop()
        started = loop.time()
        with pytest.raises(TimeoutError):
            await agent._send_jiuwenclaw_request("connect hangs")
        assert loop.time() - started < 1.0
        assert agent._ws is None

    anyio.run(run_case)


def test_peer_going_away_reconnects_on_next_ask():
    JiuwenClawAgent = _load_jiuwenclaw_agent_class()

    async def run_case():
        seen = {"n": 0}

        async def handler(ws):
            await ws.send(_ack())
            raw = await ws.recv()
            data = json.loads(raw)
            seen["n"] += 1
            if seen["n"] == 1:
                await ws.send(_final_frame(data["request_id"], "first-answer"))
                await ws.close(code=1001, reason="going away")
                return
            await ws.send(_final_frame(data["request_id"], "second-answer"))

        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            agent = JiuwenClawAgent(
                id=1,
                name="Jiuwen Alice",
                profile={"name": "Jiuwen Alice"},
                jiuwenclaw_ws_url=f"ws://127.0.0.1:{port}",
                request_timeout=2,
            )
            first = await agent._send_jiuwenclaw_request("hello")
            assert first == "first-answer"
            assert agent._ws is not None
            for _ in range(50):
                state = getattr(agent._ws, "state", None)
                if getattr(state, "name", "") == "CLOSED":
                    break
                await asyncio.sleep(0.02)
            assert getattr(getattr(agent._ws, "state", None), "name", "") == "CLOSED"

            loop = asyncio.get_running_loop()
            started = loop.time()
            answer = await agent.ask("现在在做什么？")
            assert loop.time() - started < 2
            assert "1001" not in answer
            assert answer == "second-answer"
            assert seen["n"] == 2

    anyio.run(run_case)
