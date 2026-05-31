from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace

from agentsociety2.backend.routers.live_experiments import (
    AskTarget,
    LiveExperimentSession,
)


class FakeAgent:
    def __init__(self) -> None:
        self.id = 1
        self.name = "Alice"
        self.ask_calls: list[tuple[str, bool]] = []
        self.external_question_calls: list[tuple[str, datetime, str]] = []

    async def ask(self, question: str, readonly: bool = True) -> str:
        self.ask_calls.append((question, readonly))
        return "environment-routed answer"

    async def answer_external_question(
        self,
        prompt: str,
        *,
        t: datetime,
        response_type: str = "text",
        choices: list[str] | None = None,
    ) -> str:
        self.external_question_calls.append((prompt, t, response_type))
        return "direct agent answer"


class FakeInterventionAgent:
    def __init__(self, agent_id: int, name: str) -> None:
        self.id = agent_id
        self.name = name
        self.queued: list[str] = []

    def queue_intervention(self, instruction: str) -> str:
        self.queued.append(instruction)
        return "queued"


class FakeMoveEnv:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    async def move_agent(self, agent_id: int, location: str):
        self.calls.append((agent_id, location))
        return {
            "ok": True,
            "agent_id": agent_id,
            "location_id": "park",
            "location": "Johnson Park 公园",
            "path_length": 4,
        }


class FakeReplayWriter:
    def __init__(self) -> None:
        self.rows: list[dict] = []


async def fake_write_operator_command(writer, **kwargs):
    writer.rows.append(kwargs)


def test_targeted_live_ask_uses_external_question_api(tmp_path):
    asyncio.run(_targeted_live_ask_uses_external_question_api(tmp_path))


async def _targeted_live_ask_uses_external_question_api(tmp_path):
    agent = FakeAgent()
    current_time = datetime(2026, 5, 8, 9, 30)
    society = SimpleNamespace(
        _agents=[agent],
        current_time=current_time,
        step_count=3,
        ask=None,
    )
    session = LiveExperimentSession(
        workspace_path=tmp_path,
        hypothesis_id="1",
        experiment_id="1",
    )

    result = await session._ask_with_target(
        society,
        "你今天做了什么",
        AskTarget(type="agent", agent_id=1),
    )

    assert "direct agent answer" in result
    assert agent.ask_calls == []
    assert agent.external_question_calls == [
        ("你今天做了什么", current_time, "text")
    ]


def test_live_intervene_directly_moves_agents_for_gather_instruction(tmp_path):
    asyncio.run(_live_intervene_directly_moves_agents_for_gather_instruction(tmp_path))


async def _live_intervene_directly_moves_agents_for_gather_instruction(tmp_path):
    agents = [
        FakeInterventionAgent(1, "Alice"),
        FakeInterventionAgent(2, "Bob"),
    ]
    env = FakeMoveEnv()
    society = SimpleNamespace(
        _agents=agents,
        _env_router=SimpleNamespace(env_modules=[env]),
        current_time=datetime(2026, 5, 8, 19, 20),
        step_count=52,
    )
    session = LiveExperimentSession(
        workspace_path=tmp_path,
        hypothesis_id="1",
        experiment_id="1",
    )

    result = await session._intervene_with_target(
        society,
        "所有人到公园集合准备社区碰头",
        AskTarget(type="all_agents"),
    )

    assert env.calls == [(1, "公园"), (2, "公园")]
    assert agents[0].queued == []
    assert agents[1].queued == []
    assert "直接调用环境寻路" in result
    assert "path_length=4" in result


def test_live_interaction_records_operator_command(monkeypatch, tmp_path):
    asyncio.run(_live_interaction_records_operator_command(monkeypatch, tmp_path))


async def _live_interaction_records_operator_command(monkeypatch, tmp_path):
    from agentsociety2.backend.routers import live_experiments

    fake_writer = FakeReplayWriter()
    monkeypatch.setattr(
        live_experiments,
        "write_operator_command",
        fake_write_operator_command,
    )
    session = LiveExperimentSession(
        workspace_path=tmp_path,
        hypothesis_id="demo",
        experiment_id="1",
    )
    session.replay_writer = fake_writer
    session.status = "waiting"
    session.default_tick = 1
    session.society = SimpleNamespace(
        step_count=7,
        current_time=datetime(2026, 5, 31, 9, 30),
    )

    async def run_answer(society):
        return "A public event happened."

    response = await session._run_interaction(
        command_type="ask",
        busy_status="asking",
        prompt="What happened?",
        runner=run_answer,
        metadata={"target": {"type": "society"}},
    )

    assert response.type == "ask"
    assert fake_writer.rows[0]["command_type"] == "ask"
    assert fake_writer.rows[0]["step"] == 7
    assert fake_writer.rows[0]["prompt"] == "What happened?"
    assert fake_writer.rows[0]["target"] == {"type": "society"}
    assert fake_writer.rows[0]["status"] == "completed"
