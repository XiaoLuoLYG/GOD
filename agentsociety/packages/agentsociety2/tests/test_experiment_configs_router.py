import json

import anyio
import pytest
from fastapi import HTTPException

from agentsociety2.backend.routers.experiment_configs import (
    ApplyAgentsRequest,
    _preview_agents,
    apply_agents,
    get_init_config,
)


def _base_config() -> dict:
    return {
        "env_modules": [
            {
                "module_type": "SimpleSocialSpace",
                "kwargs": {"agent_id_name_pairs": [[1, "Alice"]]},
            }
        ],
        "agents": [
            {
                "agent_id": 1,
                "agent_type": "PersonAgent",
                "kwargs": {
                    "id": 1,
                    "name": "Alice",
                    "profile": {"name": "Alice"},
                },
            }
        ],
        "codegen_router": {"final_summary_enabled": True},
    }


def test_csv_import_preview_success():
    content = "\n".join(
        [
            "agent_id,agent_type,name,profile.age,profile_json,kwargs.max_tool_rounds",
            '2,PersonAgent,Bob,30,"{""age"": 31, ""occupation"": ""teacher""}",12',
        ]
    )

    preview = _preview_agents(content, "csv")

    assert preview.valid_count == 1
    agent = preview.rows[0].agent
    assert agent is not None
    assert agent["agent_id"] == 2
    assert agent["kwargs"]["id"] == 2
    assert agent["kwargs"]["profile"]["age"] == 31
    assert agent["kwargs"]["profile"]["occupation"] == "teacher"
    assert agent["kwargs"]["max_tool_rounds"] == 12


def test_import_preview_marks_duplicate_ids():
    content = "\n".join(
        [
            "agent_id,agent_type,name",
            "2,PersonAgent,Bob",
            "2,PersonAgent,Carol",
        ]
    )

    preview = _preview_agents(content, "csv")

    assert preview.valid_count == 1
    assert preview.invalid_count == 1
    assert "duplicate agent_id" in preview.rows[1].errors[0]


def test_json_import_preview_requires_kwargs_id_for_full_agent_config():
    content = json.dumps(
        [
            {
                "agent_id": 2,
                "agent_type": "PersonAgent",
                "kwargs": {"name": "Bob", "profile": {"name": "Bob"}},
            }
        ]
    )

    preview = _preview_agents(content, "json")

    assert preview.valid_count == 0
    assert preview.invalid_count == 1
    assert "kwargs.id is required" in preview.rows[0].errors


def test_apply_agents_writes_valid_config_and_syncs_env(tmp_path):
    exp_dir = tmp_path / "hypothesis_1" / "experiment_1" / "init"
    exp_dir.mkdir(parents=True)
    (exp_dir / "init_config.json").write_text(
        json.dumps(_base_config()), encoding="utf-8"
    )

    response = anyio.run(
        apply_agents,
        "1",
        "1",
        ApplyAgentsRequest(
            agents=[
                {
                    "agent_id": 2,
                    "agent_type": "PersonAgent",
                    "kwargs": {
                        "id": 2,
                        "name": "Bob",
                        "profile": {"name": "Bob"},
                    },
                }
            ]
        ),
        str(tmp_path),
    )

    saved = json.loads((exp_dir / "init_config.json").read_text(encoding="utf-8"))
    assert response.agent_count == 2
    assert saved["env_modules"][0]["kwargs"]["agent_id_name_pairs"] == [
        [1, "Alice"],
        [2, "Bob"],
    ]


def test_apply_agents_rejects_existing_duplicate_id(tmp_path):
    exp_dir = tmp_path / "hypothesis_1" / "experiment_1" / "init"
    exp_dir.mkdir(parents=True)
    (exp_dir / "init_config.json").write_text(
        json.dumps(_base_config()), encoding="utf-8"
    )

    with pytest.raises(HTTPException):
        anyio.run(
            apply_agents,
            "1",
            "1",
            ApplyAgentsRequest(
                agents=[
                    {
                        "agent_id": 1,
                        "agent_type": "PersonAgent",
                        "kwargs": {
                            "id": 1,
                            "name": "Duplicate Alice",
                            "profile": {"name": "Duplicate Alice"},
                        },
                    }
                ]
            ),
            str(tmp_path),
        )


def test_get_init_config_returns_experiment_context_and_map_locations(monkeypatch, tmp_path):
    exp_dir = tmp_path / "hypothesis_1" / "experiment_1" / "init"
    exp_dir.mkdir(parents=True)
    config = _base_config()
    config["env_modules"][0]["kwargs"]["map_id"] = "test_map"
    (exp_dir / "init_config.json").write_text(json.dumps(config), encoding="utf-8")
    (exp_dir / "experiment_context.json").write_text(
        json.dumps({"title": "Test World", "background": "A test scenario.", "map_id": "test_map"}),
        encoding="utf-8",
    )

    class Package:
        locations = [{"id": "lab", "name": "Lab"}]

    monkeypatch.setattr(
        "agentsociety2.backend.routers.experiment_configs.load_map_package",
        lambda map_id: Package(),
    )

    response = anyio.run(get_init_config, "1", "1", str(tmp_path))

    assert response.experiment_context == {
        "title": "Test World",
        "background": "A test scenario.",
        "map_id": "test_map",
    }
    assert response.map_id == "test_map"
    assert response.map_locations == [{"id": "lab", "name": "Lab"}]
