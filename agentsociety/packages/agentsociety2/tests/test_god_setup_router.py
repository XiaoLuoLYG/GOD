import asyncio
import json
from pathlib import Path

import anyio
import pytest
from fastapi import HTTPException

from agentsociety2.backend.routers import god_setup
from agentsociety2.backend.routers.god_setup import (
    DraftBasics,
    GenerateDraftRequest,
    ModelConfigPayload,
    PublishRequest,
)


def _configure_tmp_god(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GOD_ROOT", str(tmp_path))
    monkeypatch.setenv("GOD_ENV_FILE", str(tmp_path / ".env"))
    monkeypatch.setenv("LIVE_WORKSPACE_PATH", str(tmp_path / "quick_experiments"))
    for key in (
        "GOD_LLM_API_KEY",
        "GOD_LLM_API_BASE",
        "GOD_LLM_MODEL",
        "GOD_EXPERIMENT",
        "GOD_EXPERIMENT_RUN",
    ):
        monkeypatch.delenv(key, raising=False)


def _raw_draft() -> dict:
    return {
        "experiment_context": {
            "title": "Stanford Prison Adaptation",
            "background": "A bounded simulation about assigned authority roles.",
            "simulation_goal": "Observe role pressure without abuse.",
        },
        "init_config": {
            "env_modules": [
                {
                    "module_type": "PixelTownSocialEnv",
                    "kwargs": {
                        "initial_locations": {"1": "school", "2": "not_a_place"},
                        "default_group_name": "Role Study Chat",
                    },
                }
            ],
            "agents": [
                {
                    "agent_id": 1,
                    "agent_type": "JiuwenClawAgent",
                    "kwargs": {
                        "id": 1,
                        "name": "Warden",
                        "profile": {
                            "name": "Warden",
                            "role": "coordinator",
                            "persona": "Calm and procedural",
                        },
                    },
                },
                {
                    "agent_id": 2,
                    "agent_type": "JiuwenClawAgent",
                    "kwargs": {
                        "id": 2,
                        "name": "Participant",
                        "profile": {
                            "name": "Participant",
                            "role": "participant",
                        },
                    },
                },
            ],
        },
        "steps": {
            "start_t": "2026-05-11T08:20:00+08:00",
            "steps": [{"type": "run", "num_steps": 2, "tick": 600}],
        },
        "warnings": [],
    }


def test_setup_status_redacts_api_key_and_requires_first_setup(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text(
        "GOD_LLM_API_KEY=sk-test-secret\nGOD_LLM_MODEL=gpt-test\n",
        encoding="utf-8",
    )

    status = anyio.run(god_setup.setup_status)

    assert status["model_config"]["GOD_LLM_API_KEY"] == {
        "configured": True,
        "value": "••••cret",
    }
    assert status["model_config"]["GOD_LLM_MODEL"]["value"] == "gpt-test"
    assert status["needs_setup"] is True


def test_merged_env_prefers_saved_env_file_over_stale_process_env(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    monkeypatch.setenv("GOD_LLM_API_BASE", "https://api.openai.com/v1")
    (tmp_path / ".env").write_text(
        "GOD_LLM_API_KEY=sk-test-secret\n"
        "GOD_LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1\n"
        "GOD_LLM_MODEL=qwen-plus\n",
        encoding="utf-8",
    )

    env = god_setup._merged_env()

    assert env["GOD_LLM_API_BASE"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert env["GOD_LLM_MODEL"] == "qwen-plus"


def test_generate_draft_normalizes_model_output(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    monkeypatch.setattr(god_setup, "_known_location_ids", lambda: ["school", "park", "cafe"])

    async def fake_call(**_kwargs):
        return _raw_draft()

    monkeypatch.setattr(god_setup, "_call_openai_compatible", fake_call)

    draft = anyio.run(
        god_setup.generate_draft,
        GenerateDraftRequest(
            model_config=ModelConfigPayload(GOD_LLM_API_KEY="sk-test"),
            basics=DraftBasics(
                title="Stanford Prison Adaptation",
                background="A bounded simulation about assigned authority roles.",
                agent_count=2,
            ),
        ),
    )

    assert len(draft["init_config"]["agents"]) == 2
    first_profile = draft["init_config"]["agents"][0]["kwargs"]["profile"]
    assert first_profile["scenario_role"] == "coordinator"
    assert draft["init_config"]["agents"][0]["kwargs"]["experiment_context"]["title"] == "Stanford Prison Adaptation"
    assert draft["init_config"]["env_modules"][0]["kwargs"]["initial_locations"]["2"] in {"school", "park", "cafe"}
    assert draft["warnings"]
    latest = json.loads((tmp_path / ".god" / "run" / "latest-draft.json").read_text(encoding="utf-8"))
    assert latest["basics"]["background"] == "A bounded simulation about assigned authority roles."
    assert latest["draft"]["experiment_context"]["title"] == "Stanford Prison Adaptation"


def test_generate_draft_uses_saved_api_base_when_request_omits_it(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    monkeypatch.setenv("GOD_LLM_API_BASE", "https://api.openai.com/v1")
    (tmp_path / ".env").write_text(
        "GOD_LLM_API_KEY=sk-env-key\n"
        "GOD_LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1\n"
        "GOD_LLM_MODEL=qwen-plus\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(god_setup, "_known_location_ids", lambda: ["school", "park", "cafe"])
    captured = {}

    async def fake_call(**kwargs):
        captured.update(kwargs)
        return _raw_draft()

    monkeypatch.setattr(god_setup, "_call_openai_compatible", fake_call)

    anyio.run(
        god_setup.generate_draft,
        GenerateDraftRequest(
            model_config=ModelConfigPayload(),
            basics=DraftBasics(agent_count=2),
        ),
    )

    assert captured["api_base"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert captured["model"] == "qwen-plus"


def test_normalize_draft_replaces_generic_agent_names(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    monkeypatch.setattr(god_setup, "_known_location_ids", lambda: ["school", "park", "cafe"])
    raw = _raw_draft()
    raw["init_config"]["agents"][0]["kwargs"]["name"] = "Jiuwen Agent 1"
    raw["init_config"]["agents"][0]["kwargs"]["profile"]["name"] = "Jiuwen Agent 1"

    draft = god_setup._normalize_draft(
        raw,
        DraftBasics(
            title="角色压力观察",
            background="安全版监狱角色压力实验，观察权力、规则和沟通。",
            agent_count=2,
        ),
    )

    first = draft["init_config"]["agents"][0]
    assert first["kwargs"]["name"] != "Jiuwen Agent 1"
    assert first["kwargs"]["profile"]["name"] == first["kwargs"]["name"]
    assert first["kwargs"]["profile"]["role"] != "participant"


def test_normalize_draft_backfills_scenario_specific_agents(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    monkeypatch.setattr(god_setup, "_known_location_ids", lambda: ["home", "school", "cafe", "market", "park"])

    draft = god_setup._normalize_draft(
        {"init_config": {"agents": []}},
        DraftBasics(
            title="早高峰协作实验",
            background="小镇早高峰，居民需要在咖啡馆和市场之间协调采购清单和交接时间。",
            agent_count=2,
        ),
    )

    profiles = [agent["kwargs"]["profile"] for agent in draft["init_config"]["agents"]]
    assert profiles[0]["skills"] != profiles[1]["skills"]
    assert "库存盘点" in profiles[1]["skills"]
    assert "采购" in profiles[1]["persona"]


def test_generate_draft_accepts_empty_basics_with_defaults(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    monkeypatch.setattr(god_setup, "_known_location_ids", lambda: ["school", "park", "cafe"])

    captured = {}

    async def fake_call(**kwargs):
        captured["basics"] = kwargs["basics"]
        return {}

    monkeypatch.setattr(god_setup, "_call_openai_compatible", fake_call)

    draft = anyio.run(
        god_setup.generate_draft,
        GenerateDraftRequest(
            model_config=ModelConfigPayload(GOD_LLM_API_KEY="sk-test"),
            basics={},
        ),
    )

    assert captured["basics"].background
    assert captured["basics"].agent_count == 10
    assert draft["experiment_context"]["background"] == captured["basics"].background
    assert len(draft["init_config"]["agents"]) == 10


def test_generate_draft_reports_timeout_as_gateway_timeout(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)

    async def fake_call(**_kwargs):
        raise asyncio.TimeoutError

    monkeypatch.setattr(god_setup, "_call_openai_compatible", fake_call)

    with pytest.raises(HTTPException) as exc_info:
        anyio.run(
            god_setup.generate_draft,
            GenerateDraftRequest(
                model_config=ModelConfigPayload(GOD_LLM_API_KEY="sk-test"),
                basics=DraftBasics(background="custom background"),
            ),
        )

    assert exc_info.value.status_code == 504
    assert "timed out" in str(exc_info.value.detail)


def test_publish_writes_new_experiment_context_and_start_request(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    monkeypatch.setattr(god_setup, "_known_location_ids", lambda: ["school", "park", "cafe"])

    result = anyio.run(
        god_setup.publish_experiment,
        PublishRequest(
            draft=_raw_draft(),
            model_config=ModelConfigPayload(GOD_LLM_API_KEY="sk-test"),
            requested_hypothesis_id="role_study",
            start_immediately=True,
        ),
    )

    exp_dir = Path(result["experiment_path"])
    context = json.loads((exp_dir / "init" / "experiment_context.json").read_text(encoding="utf-8"))
    init_config = json.loads((exp_dir / "init" / "init_config.json").read_text(encoding="utf-8"))
    current = json.loads((tmp_path / ".god" / "current_experiment.json").read_text(encoding="utf-8"))
    start_request = json.loads((tmp_path / ".god" / "run" / "start-request.json").read_text(encoding="utf-8"))

    assert context["title"] == "Stanford Prison Adaptation"
    assert init_config["agents"][0]["kwargs"]["experiment_context"]["title"] == context["title"]
    assert current["hypothesis_id"] == "role_study"
    assert start_request["hypothesis_id"] == "role_study"
    assert "GOD_EXPERIMENT=role_study" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_start_default_experiment_writes_current_and_start_request(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    default_dir = tmp_path / "quick_experiments" / "hypothesis_god_town" / "experiment_1" / "init"
    default_dir.mkdir(parents=True)
    (default_dir / "init_config.json").write_text("{}", encoding="utf-8")

    result = anyio.run(god_setup.start_default_experiment)

    assert result["hypothesis_id"] == "god_town"
    assert result["experiment_id"] == "1"
    current = json.loads((tmp_path / ".god" / "current_experiment.json").read_text(encoding="utf-8"))
    start_request = json.loads((tmp_path / ".god" / "run" / "start-request.json").read_text(encoding="utf-8"))
    assert current["hypothesis_id"] == "god_town"
    assert start_request["hypothesis_id"] == "god_town"
