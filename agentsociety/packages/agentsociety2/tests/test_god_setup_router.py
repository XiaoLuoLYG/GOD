import asyncio
import io
import json
from pathlib import Path

import anyio
import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from agentsociety2.backend.routers import god_setup
from agentsociety2.backend.routers.god_setup import (
    AgentStudioGenerateRequest,
    DraftBasics,
    GenerateDraftRequest,
    ModelConfigPayload,
    PublishRequest,
    StartDefaultRequest,
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
        "GOD_MAP_ID",
        "GOD_SETUP_MODE",
    ):
        monkeypatch.delenv(key, raising=False)


def _write_test_map_package(tmp_path: Path, map_id: str, *, valid: bool = True) -> Path:
    package = tmp_path / "agentsociety" / "custom" / "maps" / map_id
    (package / "visuals").mkdir(parents=True)
    (package / "characters").mkdir(parents=True)
    if valid:
        (package / "visuals" / "map.json").write_text(
            json.dumps(
                {
                    "type": "map",
                    "orientation": "orthogonal",
                    "width": 4,
                    "height": 4,
                    "tilewidth": 32,
                    "tileheight": 32,
                    "tilesets": [],
                    "layers": [
                        {"name": "Ground", "type": "tilelayer", "width": 4, "height": 4, "data": [0] * 16},
                        {"name": "Collisions", "type": "tilelayer", "width": 4, "height": 4, "data": [0] * 16},
                    ],
                }
            ),
            encoding="utf-8",
        )
    (package / "map.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                f"map_id: {map_id}",
                f"display_name: {map_id.title()}",
                "tiled_map_path: visuals/map.json",
                "tile_size: 32",
                "character_root: characters",
                "default_location_order:",
                "- lab",
                "- yard",
                "spawn_points:",
                "- id: start",
                "  location_id: lab",
                "locations:",
                "- id: lab",
                "  name: Lab",
                "  aliases: [lab]",
                "  anchor_tile: {x: 1, y: 1}",
                "  interaction_ids: [inspect]",
                "- id: yard",
                "  name: Yard",
                "  aliases: [yard]",
                "  anchor_tile: {x: 2, y: 1}",
                "  interaction_ids: [walk]",
                "interactions:",
                "- id: inspect",
                "  name: Inspect",
                "  allowed_location_ids: [lab]",
                "- id: walk",
                "  name: Walk",
                "  allowed_location_ids: [yard]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return package


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
    assert status["setup_mode"] is False


def test_setup_status_exposes_setup_mode(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    monkeypatch.setenv("GOD_SETUP_MODE", "1")

    status = anyio.run(god_setup.setup_status)

    assert status["setup_mode"] is True


def test_agent_studio_generate_keeps_location_on_current_map():
    response = anyio.run(
        god_setup.generate_agent_studio_options,
        AgentStudioGenerateRequest(
            experiment_context={
                "title": "Town Test",
                "background": "A realistic town experiment.",
            },
            map_id="test_map",
            map_locations=[
                {"id": "lab", "name": "Lab"},
                {"id": "yard", "name": "Yard"},
            ],
            language="zh",
            source={"prompt": "一个每天去月球上班的变形金刚", "mbti": "INTP"},
            locked_choices={"initial_location": "yard"},
            custom_choices={"personality_core": "外冷内热的机械生命"},
        ),
    )

    assert response.initial_location == "yard"
    assert response.selected_choices["initial_location"] == "yard"
    assert response.profile_patch["role"]
    assert response.profile_patch["agent_studio"]["custom_choices"]["personality_core"] == "外冷内热的机械生命"
    assert "world_conflict" not in response.profile_patch
    assert "virtual_locations" not in response.profile_patch


def test_agent_studio_generate_localizes_known_context_and_locations():
    response = anyio.run(
        god_setup.generate_agent_studio_options,
        AgentStudioGenerateRequest(
            experiment_context={
                "title": "上帝模式小镇 · 维尔普通工作日",
                "background": "晚春的一个工作日清晨 8:20。维尔小镇是一个 200 多人的小镇，10 位常住居民彼此熟识但不黏腻。天气晴朗微风，温度 18 摄氏度。镇上没有突发事件，是一段反映自然节奏的日常切片。",
            },
            map_id="the_ville",
            map_locations=[
                {
                    "id": "park",
                    "name": "约翰逊公园",
                    "localized": {"en": {"name": "Johnson Park"}, "zh": {"name": "约翰逊公园"}},
                },
            ],
            language="en",
        ),
    )

    location_group = next(group for group in response.groups if group.id == "initial_location")
    assert location_group.options[0].label == "Johnson Park (park)"
    assert "late-spring weekday morning" in response.profile_patch["scenario"]
    assert "晚春" not in response.profile_patch["persona"]


def test_agent_studio_character_generation_writes_map_sprite(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    package = _write_test_map_package(tmp_path, "the_ville")
    source = Image.new("RGB", (24, 24), (92, 140, 220))
    buffer = io.BytesIO()
    source.save(buffer, format="PNG")
    buffer.seek(0)

    async def call_endpoint():
        return await god_setup.generate_agent_studio_character(
            file=UploadFile(buffer, filename="reference.png"),
            map_id="the_ville",
            agent_name="Moon Transformer",
            prompt="A Transformer who commutes to the moon",
            mbti="INTP",
        )

    asset = anyio.run(call_endpoint)
    output_path = package / "characters" / asset.filename

    assert asset.sprite_name == output_path.stem
    assert asset.image_url.endswith(asset.filename)
    assert output_path.exists()
    with Image.open(output_path) as generated:
        assert generated.size == (96, 128)


def test_setup_status_scans_map_packages_and_keeps_invalid_visible(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    _write_test_map_package(tmp_path, "the_ville")
    _write_test_map_package(tmp_path, "lab_map")
    _write_test_map_package(tmp_path, "broken_map", valid=False)
    (tmp_path / ".env").write_text("GOD_MAP_ID=lab_map\n", encoding="utf-8")

    status = anyio.run(god_setup.setup_status)

    by_id = {item["map_id"]: item for item in status["maps"]}
    assert status["selected_map_id"] == "the_ville"
    assert by_id["lab_map"]["validation_status"]["ok"] is True
    assert by_id["broken_map"]["validation_status"]["ok"] is False
    assert status["map_locations"][0]["id"] == "lab"


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


def test_normalize_draft_uses_selected_map_package(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    _write_test_map_package(tmp_path, "the_ville")
    _write_test_map_package(tmp_path, "lab_map")

    raw = _raw_draft()
    draft = god_setup._normalize_draft(
        raw,
        DraftBasics(
            title="Lab Scenario",
            background="Coordinate a lab handoff.",
            agent_count=2,
            map_id="lab_map",
        ),
    )

    env = draft["init_config"]["env_modules"][0]["kwargs"]
    assert env["map_id"] == "lab_map"
    assert env["map_manifest_path"] == "custom/maps/lab_map/map.yaml"
    assert draft["experiment_context"]["map_id"] == "lab_map"
    assert set(env["initial_locations"].values()) <= {"lab", "yard"}


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


def test_generate_draft_falls_back_to_default_map_when_selected_missing(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    _write_test_map_package(tmp_path, "the_ville")
    captured = {}

    async def fake_call(**kwargs):
        captured["package"] = kwargs["package"]
        return _raw_draft()

    monkeypatch.setattr(god_setup, "_call_openai_compatible", fake_call)

    draft = anyio.run(
        god_setup.generate_draft,
        GenerateDraftRequest(
            model_config=ModelConfigPayload(GOD_LLM_API_KEY="sk-test"),
            basics=DraftBasics(agent_count=2, map_id="missing_map"),
        ),
    )

    assert captured["package"].map_id == "the_ville"
    assert draft["experiment_context"]["map_id"] == "the_ville"


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


def test_normalize_draft_uses_public_channel_default(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    monkeypatch.setattr(god_setup, "_known_location_ids", lambda: ["school", "park", "cafe"])
    raw = _raw_draft()
    raw["init_config"]["env_modules"][0]["kwargs"].pop("default_group_name")

    draft = god_setup._normalize_draft(
        raw,
        DraftBasics(
            title="Lab Scenario",
            background="Coordinate a lab handoff.",
            agent_count=2,
        ),
    )

    env = draft["init_config"]["env_modules"][0]["kwargs"]
    assert env["default_group_name"] == "Lab Scenario公开频道"


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

    agents = draft["init_config"]["agents"]
    profiles = [agent["kwargs"]["profile"] for agent in agents]
    assert agents[0]["kwargs"]["skill_ids"] != agents[1]["kwargs"]["skill_ids"]
    assert "skills" not in profiles[0]
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
    assert current["map_id"] == "the_ville"
    assert start_request["hypothesis_id"] == "role_study"
    assert "GOD_EXPERIMENT=role_study" not in (tmp_path / ".env").read_text(encoding="utf-8")


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
    assert current["map_id"] == "the_ville"
    assert start_request["hypothesis_id"] == "god_town"


def test_start_default_experiment_can_select_pku_without_writing_env_map(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text("GOD_MAP_ID=the_ville\n", encoding="utf-8")
    default_dir = tmp_path / "quick_experiments" / "hypothesis_pku_trump_visit" / "experiment_1" / "init"
    default_dir.mkdir(parents=True)
    (default_dir / "init_config.json").write_text("{}", encoding="utf-8")

    result = anyio.run(
        god_setup.start_default_experiment,
        StartDefaultRequest(experiment_key="pku_trump_visit"),
    )

    assert result["hypothesis_id"] == "pku_trump_visit"
    assert result["map_id"] == "pku"
    current = json.loads((tmp_path / ".god" / "current_experiment.json").read_text(encoding="utf-8"))
    assert current["hypothesis_id"] == "pku_trump_visit"
    assert current["map_id"] == "pku"
    assert "GOD_MAP_ID=pku" not in (tmp_path / ".env").read_text(encoding="utf-8")
