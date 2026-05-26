from __future__ import annotations

import importlib.util
import asyncio
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from agentsociety2.backend.services.custom.scanner import CustomModuleScanner


REPO_ROOT = Path(__file__).resolve().parents[4]
AGENT_FILE = REPO_ROOT / "custom" / "agents" / "jiuwenclaw_agent.py"


def load_agent_class():
    spec = importlib.util.spec_from_file_location("test_jiuwenclaw_agent", AGENT_FILE)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.JiuwenClawAgent


class FakeWebSocket:
    def __init__(self, response_content: str | None = None, error: str | None = None):
        self.response_content = response_content
        self.error = error
        self.sent: list[dict] = []
        self.closed = False
        self._ack_sent = False

    async def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))

    async def recv(self) -> str:
        if not self._ack_sent:
            self._ack_sent = True
            return json.dumps({"type": "event", "event": "connection.ack"})
        assert self.sent, "response requested before send"
        request_id = self.sent[-1]["request_id"]
        if self.error is not None:
            return json.dumps(
                {
                    "protocol_version": "1.0",
                    "request_id": request_id,
                    "is_final": True,
                    "status": "failed",
                    "response_kind": "e2a.error",
                    "body": {"message": self.error},
                }
            )
        return json.dumps(
            {
                "protocol_version": "1.0",
                "request_id": request_id,
                "is_final": True,
                "status": "succeeded",
                "response_kind": "e2a.stream",
                "body": {
                    "delta": {
                        "event_type": "chat.final",
                        "content": self.response_content,
                    }
                },
            }
        )

    async def close(self) -> None:
        self.closed = True


class FakeEnv:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    async def ask(
        self,
        ctx: dict,
        message: str,
        readonly: bool,
        template_mode: bool = False,
    ):
        self.calls.append((message, readonly))
        if readonly:
            return ctx, "observation text"
        return ctx, "environment action result"


class FakeSocialEnv(FakeEnv):
    def __init__(self, run_dir: Path) -> None:
        super().__init__()
        self.run_dir = run_dir
        self.moves: list[tuple[int, str]] = []
        self.interactions: list[tuple[int, str, dict]] = []
        self.states: list[tuple[int, str, str, str]] = []
        self.direct_messages: list[tuple[int, int, str]] = []
        self.group_messages: list[tuple[int, int, str]] = []
        self.nearby_agents: list[dict] = [
            {"agent_id": 2, "name": "Nearby Bob", "location_id": "home"}
        ]

    async def observe_agent(self, agent_id: int):
        return {
            "agent_id": agent_id,
            "name": "Jiuwen",
            "location_id": "home",
            "location": "家",
            "latest_event": "",
            "recent_messages": [],
            "nearby_agents": list(self.nearby_agents),
            "known_locations": [
                {
                    "id": "home",
                    "name": "家",
                    "aliases": ["home"],
                    "anchor_tile": {"x": 1, "y": 1},
                    "interaction_ids": ["sleep_at_home"],
                    "scene_type": "home",
                },
                {
                    "id": "school",
                    "name": "学校",
                    "aliases": ["school"],
                    "anchor_tile": {"x": 2, "y": 1},
                    "interaction_ids": ["attend_class"],
                    "scene_type": "school",
                },
            ],
            "known_interactions": [
                {
                    "id": "sleep_at_home",
                    "name": "睡觉",
                    "allowed_location_ids": ["home"],
                },
                {
                    "id": "attend_class",
                    "name": "上课",
                    "allowed_location_ids": ["school"],
                },
            ],
        }

    async def move_agent(self, agent_id: int, location: str):
        self.moves.append((agent_id, location))
        return {"ok": True, "agent_id": agent_id, "location_id": location}

    async def interact(self, agent_id: int, interaction_id: str, params: dict | None = None):
        self.interactions.append((agent_id, interaction_id, params or {}))
        return {"ok": True, "agent_id": agent_id, "interaction_id": interaction_id}

    async def send_group_message(self, sender_id: int, group_id: int, content: str):
        self.group_messages.append((sender_id, group_id, content))
        return {"ok": True, "sender_id": sender_id, "group_id": group_id, "content": content}

    async def send_message(self, sender_id: int, receiver_id: int, content: str):
        self.direct_messages.append((sender_id, receiver_id, content))
        return {"ok": True, "sender_id": sender_id, "receiver_id": receiver_id, "content": content}

    async def set_agent_action(
        self,
        agent_id: int,
        action: str,
        status: str = "active",
        emotion: str = "calm",
    ):
        self.states.append((agent_id, action, status, emotion))
        return {
            "ok": True,
            "agent_id": agent_id,
            "action": action,
            "status": status,
            "emotion": emotion,
        }


def make_agent(
    response_content: str | None = None,
    error: str | None = None,
    profile: dict | None = None,
    enable_skill_runtime: bool = True,
    common_skill_ids: list[str] | None = None,
    skill_ids: list[str] | None = None,
):
    cls = load_agent_class()
    fake_ws = FakeWebSocket(response_content=response_content, error=error)

    class TestableJiuwenClawAgent(cls):
        async def _open_websocket(self, uri: str):
            self.opened_uri = uri
            return fake_ws

    agent = TestableJiuwenClawAgent(
        id=1,
        profile=profile or {"name": "Jiuwen", "role": "tester"},
        jiuwenclaw_ws_url="ws://example.test:18092",
        trusted_dirs=[str(REPO_ROOT)],
        request_timeout=1,
        enable_skill_runtime=enable_skill_runtime,
        common_skill_ids=common_skill_ids,
        skill_ids=skill_ids,
    )
    return agent, fake_ws


def test_scanner_accepts_jiuwenclaw_agent():
    result = CustomModuleScanner(str(REPO_ROOT)).scan_all()
    agents = result["agents"]
    assert any(agent["class_name"] == "JiuwenClawAgent" for agent in agents)

    diagnostics = result["agent_diagnostics"]
    diag = next(
        item for item in diagnostics if item.get("class_name") == "JiuwenClawAgent"
    )
    assert diag["accepted"] is True
    assert diag["issues"] == []


def test_skill_registry_parses_executable_skill_metadata():
    from agentsociety2.agent.skills import SkillRegistry

    registry = SkillRegistry()
    registry.scan_custom(REPO_ROOT)
    info = registry.get_skill_info("routine.daily", load_content=False)

    assert info is not None
    assert info.script == "scripts/run_skill.py"
    assert info.shared is True
    assert "move" in info.effects
    assert "remember" in info.effects
    assert info.args_schema["type"] == "object"
    metadata = registry.list_selection_metadata(names=["routine.daily"])
    assert metadata[0]["effects"] == info.effects
    assert metadata[0]["shared"] is True


def test_personal_skills_execute_independent_logic(tmp_path: Path):
    asyncio.run(_personal_skills_execute_independent_logic(tmp_path))


async def _personal_skills_execute_independent_logic(tmp_path: Path):
    from agentsociety2.agent.skills import SkillRegistry

    registry = SkillRegistry()
    registry.scan_custom(REPO_ROOT)
    observation = {
        "agent_id": 1,
        "name": "Jiuwen",
        "location_id": "home",
        "known_locations": [
            {"id": "home", "interaction_ids": ["relax_at_home"]},
            {"id": "school", "interaction_ids": ["attend_class", "study_after_class"]},
            {"id": "supply_store", "interaction_ids": ["repair_tools", "inspect_supplies"]},
        ],
        "known_interactions": [
            {"id": "relax_at_home", "allowed_location_ids": ["home"]},
            {"id": "attend_class", "allowed_location_ids": ["school"]},
            {"id": "study_after_class", "allowed_location_ids": ["school"]},
            {"id": "repair_tools", "allowed_location_ids": ["supply_store"]},
            {"id": "inspect_supplies", "allowed_location_ids": ["supply_store"]},
        ],
        "recent_messages": [],
    }

    async def execute(skill_id: str) -> dict:
        work_dir = tmp_path / skill_id.replace(".", "_")
        args = {
            "agent_id": 1,
            "profile": {"name": "Jiuwen", "role": "student"},
            "time": "2026-01-01T09:00:00+08:00",
            "observation": observation,
            "agent_work_dir": str(work_dir),
            "selected_skill_id": skill_id,
            "skill_args": {},
        }
        raw = await registry.execute(skill_id, args, work_dir)
        assert raw["ok"], raw
        for line in reversed(str(raw["stdout"]).splitlines()):
            if line.strip():
                return json.loads(line)
        raise AssertionError("skill did not emit JSON")

    repair = await execute("tools.repair")
    learn = await execute("class.learn")

    assert repair["summary"] != learn["summary"]
    assert repair["world_effect"] != learn["world_effect"]
    assert repair["world_effect"]["location_id"] == "supply_store"
    assert learn["world_effect"]["location_id"] == "school"
    assert "tools.repair" in repair["memory_effects"][0]["content"]
    assert "class.learn" in learn["memory_effects"][0]["content"]


def test_validator_rejects_old_shared_wrapper(tmp_path: Path):
    spec = importlib.util.spec_from_file_location(
        "validate_agent_skills",
        REPO_ROOT / "scripts" / "validate_agent_skills.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)

    shared = tmp_path / "_shared" / "agent_skill_runtime.py"
    shared.parent.mkdir(parents=True)
    shared.write_text("def parse_args():\n    return {}\n", encoding="utf-8")
    skill_root = tmp_path / "demo.skill"
    (skill_root / "scripts").mkdir(parents=True)
    (skill_root / "skill.json").write_text(
        json.dumps(
            {
                "skill_id": "demo.skill",
                "description": "demo",
                "effects": ["set_state", "remember"],
                "target_locations": [],
                "target_interactions": [],
                "status": "active",
                "emotion": "calm",
                "memory_template": "demo",
                "failure_strategy": "set_state",
                "strategy": "configured_action",
                "shared": False,
            }
        ),
        encoding="utf-8",
    )
    (skill_root / "scripts" / "run_skill.py").write_text(
        "from agent_skill_runtime import main\n\nif __name__ == '__main__':\n    raise SystemExit(main())\n",
        encoding="utf-8",
    )
    original_shared = module.SHARED_RUNTIME
    module.SHARED_RUNTIME = shared
    try:
        errors = module.validate_source_independence(
            [
                SimpleNamespace(
                    name="demo.skill",
                    path=str(skill_root),
                    script="scripts/run_skill.py",
                    effects=["set_state", "remember"],
                    shared=False,
                )
            ]
        )
    finally:
        module.SHARED_RUNTIME = original_shared
    assert any("banned old shared runtime pattern" in error for error in errors)


def test_ask_sends_legacy_chat_request_and_returns_content():
    asyncio.run(_ask_sends_legacy_chat_request_and_returns_content())


async def _ask_sends_legacy_chat_request_and_returns_content():
    agent, fake_ws = make_agent("hello from jiuwenclaw")

    answer = await agent.ask("What should you do?", readonly=True)

    assert answer == "hello from jiuwenclaw"
    assert len(fake_ws.sent) == 1
    sent = fake_ws.sent[0]
    assert sent["channel_id"] == "agentsociety"
    assert sent["req_method"] == "chat.send"
    assert sent["is_stream"] is True
    assert sent["params"]["mode"] == "agent.plan"
    assert sent["params"]["trusted_dirs"] == [str(REPO_ROOT)]
    assert sent["metadata"]["source"] == "agentsociety"
    assert sent["metadata"]["enable_memory"] is True


def test_ask_raises_on_jiuwenclaw_error_response():
    asyncio.run(_ask_raises_on_jiuwenclaw_error_response())


async def _ask_raises_on_jiuwenclaw_error_response():
    agent, _ = make_agent(error="agent failed")

    import pytest

    with pytest.raises(RuntimeError, match="agent failed"):
        await agent.ask("fail please")


def test_step_ignores_legacy_environment_instruction_when_runtime_is_forced(tmp_path: Path, monkeypatch):
    asyncio.run(_step_ignores_legacy_environment_instruction_when_runtime_is_forced(tmp_path, monkeypatch))


async def _step_ignores_legacy_environment_instruction_when_runtime_is_forced(
    tmp_path: Path,
    monkeypatch,
):
    decision = json.dumps(
        {
            "public_summary": "The agent chose to inspect the plaza.",
            "environment_instruction": "Move to the central plaza.",
        }
    )
    agent, _ = make_agent(decision, enable_skill_runtime=False)
    env = FakeEnv()
    monkeypatch.chdir(tmp_path)
    await agent.init(env)

    result = await agent.step(tick=60, t=datetime(2026, 1, 1))

    assert result == "技能步骤已完成。"
    assert env.calls[0][1] is True
    assert len(env.calls) == 1
    assert not (tmp_path / "agents").exists()


def test_forced_runtime_ignores_legacy_action_proposal(tmp_path: Path):
    asyncio.run(_forced_runtime_ignores_legacy_action_proposal(tmp_path))


async def _forced_runtime_ignores_legacy_action_proposal(tmp_path: Path):
    decision = json.dumps(
        {
            "public_summary": "The agent asks a nearby person.",
            "environment_instruction": "Post this question to the whole campus chat.",
            "action_proposal": {
                "action_type": "direct_message",
                "receiver_id": 2,
                "content": "请问未名湖怎么走？",
            },
        }
    )
    agent, _ = make_agent(decision, enable_skill_runtime=False)
    env = FakeSocialEnv(tmp_path)
    await agent.init(env)

    result = await agent.step(tick=60, t=datetime(2026, 1, 1))

    assert "The agent asks a nearby person." not in result
    assert env.direct_messages == []
    assert env.group_messages == []
    assert env.calls == []
    snapshot = json.loads(
        (
            tmp_path
            / "agents"
            / "agent_0001"
            / ".runtime"
            / "logs"
            / "agent_state_snapshot.json"
        ).read_text()
    )
    assert snapshot["last_skill_decision"]["selected_skill_id"]


def test_step_non_json_legacy_response_is_not_used(tmp_path: Path, monkeypatch):
    asyncio.run(_step_non_json_legacy_response_is_not_used(tmp_path, monkeypatch))


async def _step_non_json_legacy_response_is_not_used(tmp_path: Path, monkeypatch):
    agent, _ = make_agent("plain natural-language response", enable_skill_runtime=False)
    env = FakeEnv()
    monkeypatch.chdir(tmp_path)
    await agent.init(env)

    result = await agent.step(tick=60, t=datetime(2026, 1, 1))

    assert result == "技能步骤已完成。"
    assert len(env.calls) == 1
    assert env.calls[0][1] is True
    assert not (tmp_path / "agents").exists()


def test_dump_load_and_close_do_not_serialize_websocket():
    asyncio.run(_dump_load_and_close_do_not_serialize_websocket())


async def _dump_load_and_close_do_not_serialize_websocket():
    agent, fake_ws = make_agent("hello")
    await agent.ask("hello")
    dump = await agent.dump()

    assert "_ws" not in dump
    assert dump["session_id"] == "agentsociety_agent_1"
    assert dump["last_response"] == "hello"

    restored, _ = make_agent("unused")
    await restored.load(dump)
    restored_dump = await restored.dump()
    assert restored_dump["last_response"] == "hello"
    await agent.close()
    assert fake_ws.closed is True


def test_step_runs_agentsociety_skill_runtime_and_applies_proposal(tmp_path: Path):
    asyncio.run(_step_runs_agentsociety_skill_runtime_and_applies_proposal(tmp_path))


async def _step_runs_agentsociety_skill_runtime_and_applies_proposal(tmp_path: Path):
    decision = json.dumps(
        {
            "selected_skill_id": "routine.daily",
            "args": {},
            "reason": "A school-day routine is appropriate.",
            "public_summary": "The agent accepts the grounded routine.",
        }
    )
    agent, _ = make_agent(
        decision,
        profile={"name": "Jiuwen", "role": "student"},
    )
    env = FakeSocialEnv(tmp_path)
    await agent.init(env)

    result = await agent.step(tick=60, t=datetime(2026, 1, 1, 9, 0, 0))

    assert "The agent accepts the grounded routine." in result
    assert env.moves == [(1, "school")]
    work_dir = tmp_path / "agents" / "agent_0001"
    assert json.loads((work_dir / "state" / "mounted_skills.json").read_text())[:5] == [
        "routine.daily",
        "social.reply",
        "memory.record",
        "map.navigate",
        "safety.respond",
    ]
    skill_result = json.loads((work_dir / "state" / "skill_results" / "routine_daily.json").read_text())
    assert skill_result["skill_id"] == "routine.daily"
    assert skill_result["world_effect"]["type"] == "move"
    assert skill_result["world_effect"]["location_id"] == "school"
    assert (work_dir / "memory" / "skill_memory.jsonl").is_file()
    session_state = json.loads(
        (work_dir / ".runtime" / "logs" / "session_state.json").read_text()
    )
    assert "routine.daily" in session_state["mounted_skill_ids"]
    assert session_state["activated_skills"] == ["routine.daily"]
    snapshot = json.loads(
        (work_dir / ".runtime" / "logs" / "agent_state_snapshot.json").read_text()
    )
    assert snapshot["last_skill_decision"]["selected_skill_id"] == "routine.daily"
    assert snapshot["last_skill_result"]["skill_id"] == "routine.daily"
    assert snapshot["last_environment_effects"][0]["effect"] == "world_effect"


def test_unmounted_skill_decision_falls_back_to_mounted_skill(tmp_path: Path):
    asyncio.run(_unmounted_skill_decision_falls_back_to_mounted_skill(tmp_path))


async def _unmounted_skill_decision_falls_back_to_mounted_skill(tmp_path: Path):
    decision = json.dumps(
        {
            "selected_skill_id": "tools.repair",
            "args": {},
            "reason": "The model tried to select an unmounted skill.",
            "public_summary": "This choice should be rejected.",
        }
    )
    agent, _ = make_agent(
        decision,
        profile={"name": "Jiuwen", "role": "student"},
        common_skill_ids=["routine.daily"],
        skill_ids=[],
    )
    env = FakeSocialEnv(tmp_path)
    await agent.init(env)

    await agent.step(tick=60, t=datetime(2026, 1, 1, 9, 0, 0))

    assert env.moves == [(1, "school")]
    work_dir = tmp_path / "agents" / "agent_0001"
    snapshot = json.loads(
        (work_dir / ".runtime" / "logs" / "agent_state_snapshot.json").read_text()
    )
    assert snapshot["last_skill_decision"]["selected_skill_id"] == "routine.daily"
    assert snapshot["last_skill_decision"]["fallback"] is True


def test_non_public_skill_group_speech_becomes_nearby_direct(tmp_path: Path):
    asyncio.run(_non_public_skill_group_speech_becomes_nearby_direct(tmp_path))


async def _non_public_skill_group_speech_becomes_nearby_direct(tmp_path: Path):
    agent, _ = make_agent("unused")
    env = FakeSocialEnv(tmp_path)
    await agent.init(env)

    result = await agent._apply_speech_effect(
        {"type": "group_message", "group_id": 1, "content": "local chat"},
        {"skill_id": "peer.communicate"},
    )

    assert result["ok"] is True
    assert env.direct_messages == [(1, 2, "local chat")]
    assert env.group_messages == []


def test_skill_group_speech_without_nearby_agent_does_not_broadcast(tmp_path: Path):
    asyncio.run(_skill_group_speech_without_nearby_agent_does_not_broadcast(tmp_path))


async def _skill_group_speech_without_nearby_agent_does_not_broadcast(tmp_path: Path):
    agent, _ = make_agent("unused")
    env = FakeSocialEnv(tmp_path)
    env.nearby_agents = []
    await agent.init(env)

    result = await agent._apply_speech_effect(
        {"type": "group_message", "group_id": 1, "content": "no one nearby"},
        {"skill_id": "peer.communicate"},
    )

    assert result["ok"] is False
    assert result["error"] == "no_nearby_agent"
    assert env.direct_messages == []
    assert env.group_messages == []


def test_public_skill_group_speech_stays_group_broadcast(tmp_path: Path):
    asyncio.run(_public_skill_group_speech_stays_group_broadcast(tmp_path))


async def _public_skill_group_speech_stays_group_broadcast(tmp_path: Path):
    agent, _ = make_agent("unused")
    env = FakeSocialEnv(tmp_path)
    await agent.init(env)

    result = await agent._apply_speech_effect(
        {"type": "group_message", "group_id": 1, "content": "safety notice"},
        {"skill_id": "safety.respond"},
    )

    assert result["ok"] is True
    assert env.direct_messages == []
    assert env.group_messages == [(1, 1, "safety notice")]


def test_memory_skill_writes_agent_workspace_memory(tmp_path: Path):
    asyncio.run(_memory_skill_writes_agent_workspace_memory(tmp_path))


async def _memory_skill_writes_agent_workspace_memory(tmp_path: Path):
    decision = json.dumps(
        {
            "selected_skill_id": "memory.record",
            "args": {"content": "Remember this validation event."},
            "reason": "The agent should preserve a useful observation.",
            "public_summary": "The agent records a memory.",
        }
    )
    agent, _ = make_agent(
        decision,
        profile={"name": "Jiuwen", "role": "tester"},
        common_skill_ids=["memory.record"],
        skill_ids=[],
    )
    env = FakeSocialEnv(tmp_path)
    await agent.init(env)

    result = await agent.step(tick=60, t=datetime(2026, 1, 1, 9, 0, 0))

    assert "The agent records a memory." in result
    memory_path = tmp_path / "agents" / "agent_0001" / "memory" / "skill_memory.jsonl"
    lines = memory_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["skill_id"] == "memory.record"
    assert "记忆记录" in entry["content"]
