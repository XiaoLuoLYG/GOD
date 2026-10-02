import json

import anyio
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from agentsociety2.backend.routers import experiment_configs
from agentsociety2.backend.routers.experiment_configs import (
    ApplyAgentsRequest,
    _preview_agents,
    apply_agents,
    get_init_config,
    put_init_config,
)


@pytest.fixture(autouse=True)
def configured_workspace(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVE_WORKSPACE_PATH", str(tmp_path))


@pytest.mark.parametrize("method,suffix,payload", [
    ("GET", "init", None),
    ("PUT", "init", {}),
    ("POST", "agents/import-preview", {"content": "[]", "format": "json"}),
    ("POST", "agents/apply", {"agents": []}),
])
def test_config_routes_reject_outside_workspace(tmp_path, method, suffix, payload):
    app = FastAPI()
    app.include_router(experiment_configs.router)
    response = TestClient(app).request(
        method, f"/api/v1/experiment-configs/1/1/{suffix}",
        params={"workspace_path": str(tmp_path.parent)}, json=payload,
    )
    assert response.status_code == 403


@pytest.mark.parametrize("component", ["workspace", "experiment", "init", "config"])
def test_config_path_rejects_symlink_escape(monkeypatch, tmp_path, component):
    root = tmp_path / "allowed"
    root.mkdir()
    monkeypatch.setenv("LIVE_WORKSPACE_PATH", str(root))
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "init_config.json"
    sentinel.write_text("unchanged", encoding="utf-8")
    experiment = root / "hypothesis_1" / "experiment_1"
    if component == "workspace":
        workspace = root / "linked"
        workspace.symlink_to(outside, target_is_directory=True)
    else:
        workspace = root
        link = {"experiment": experiment, "init": experiment / "init", "config": experiment / "init/init_config.json"}[component]
        link.parent.mkdir(parents=True)
        link.symlink_to(sentinel if component == "config" else outside)

    with pytest.raises(HTTPException) as exc:
        anyio.run(put_init_config, "1", "1", _base_config(), str(workspace))
    assert exc.value.status_code == 403
    assert sentinel.read_text(encoding="utf-8") == "unchanged"


def test_config_path_rejects_traversal_and_allows_nested_workspace(tmp_path):
    with pytest.raises(HTTPException) as exc:
        experiment_configs._init_config_path(str(tmp_path), "1", "1/../../../../escape")
    assert exc.value.status_code == 403
    nested = tmp_path / "nested"
    assert experiment_configs._init_config_path(str(nested), "1", "1") == nested / "hypothesis_1/experiment_1/init/init_config.json"


@pytest.mark.parametrize("linked_layout", [False, True])
def test_config_get_rejects_context_symlink_escape(monkeypatch, tmp_path, linked_layout):
    root = tmp_path / "allowed"
    monkeypatch.setenv("LIVE_WORKSPACE_PATH", str(root))
    init_dir = root / "hypothesis_1/experiment_1/init"
    init_dir.mkdir(parents=True)
    if linked_layout:
        init_dir.rmdir()
        init_dir.parent.rmdir()
        init_dir.parent.symlink_to(root, target_is_directory=True)
        init_dir = root / "init"
        init_dir.mkdir()
        (root / "config.json").write_text(json.dumps(_base_config()), encoding="utf-8")
        (init_dir / "init_config.json").symlink_to(root / "config.json")
    else:
        (init_dir / "init_config.json").write_text(json.dumps(_base_config()), encoding="utf-8")
    outside = tmp_path / "outside.json"
    outside.write_text('{"private": "outside-data"}', encoding="utf-8")
    ((root if linked_layout else init_dir) / "experiment_context.json").symlink_to(outside)
    app = FastAPI()
    app.include_router(experiment_configs.router)
    response = TestClient(app).get(
        "/api/v1/experiment-configs/1/1/init", params={"workspace_path": str(root)},
    )
    assert response.status_code == 403
    assert "outside-data" not in response.text


def test_config_keeps_cwd_relative_workspace_paths(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIVE_WORKSPACE_PATH", "quick_experiments")
    response = anyio.run(put_init_config, "1", "1", _base_config(), "quick_experiments")
    expected = tmp_path / "quick_experiments/hypothesis_1/experiment_1/init/init_config.json"
    assert response.path == str(expected)
    assert expected.exists()


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


def test_json_import_preview_normalizes_jiuwen_runtime_kwargs():
    content = json.dumps(
        [
            {
                "agent_id": 2,
                "agent_type": "JiuwenClawAgent",
                "kwargs": {
                    "id": 2,
                    "name": "Jiuwen Bob",
                    "enable_skill_runtime": False,
                    "skill_ids": [],
                    "skill_runtime_skill_names": ["legacy.daily"],
                    "profile": {
                        "name": "Jiuwen Bob",
                        "skills": ["class.learn"],
                    },
                },
            }
        ]
    )

    preview = _preview_agents(content, "json")

    assert preview.valid_count == 1
    kwargs = preview.rows[0].agent["kwargs"]
    assert kwargs["enable_skill_runtime"] is True
    assert kwargs["common_skill_ids"] == [
        "routine.daily",
        "social.reply",
        "memory.record",
        "map.navigate",
        "safety.respond",
    ]
    assert kwargs["skill_ids"] == ["class.learn"]
    assert "skill_runtime_skill_names" not in kwargs
    assert "skills" not in kwargs["profile"]


def test_json_import_preview_preserves_custom_personal_skill_ids():
    content = json.dumps(
        [
            {
                "agent_id": 2,
                "agent_type": "JiuwenClawAgent",
                "kwargs": {
                    "id": 2,
                    "name": "Jiuwen Bob",
                    "enable_skill_runtime": False,
                    "skill_ids": [
                        "custom.skill",
                        "class.learn",
                        "custom.skill",
                        "",
                    ],
                    "profile": {"name": "Jiuwen Bob"},
                },
            }
        ]
    )

    preview = _preview_agents(content, "json")

    assert preview.valid_count == 1
    kwargs = preview.rows[0].agent["kwargs"]
    assert kwargs["enable_skill_runtime"] is True
    assert kwargs["skill_ids"] == ["custom.skill", "class.learn"]


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


def test_put_init_config_normalizes_jiuwen_agents(tmp_path):
    exp_dir = tmp_path / "hypothesis_1" / "experiment_1" / "init"
    exp_dir.mkdir(parents=True)
    config = _base_config()
    config["agents"] = [
        {
            "agent_id": 1,
            "agent_type": "JiuwenClawAgent",
            "kwargs": {
                "id": 1,
                "name": "Jiuwen Alice",
                "enable_skill_runtime": False,
                "common_skill_ids": [],
                "skill_ids": [],
                "profile": {"name": "Jiuwen Alice"},
            },
        }
    ]

    response = anyio.run(put_init_config, "1", "1", config, str(tmp_path))

    kwargs = response.config["agents"][0]["kwargs"]
    assert kwargs["enable_skill_runtime"] is True
    assert len(kwargs["common_skill_ids"]) == 5
    assert len(kwargs["skill_ids"]) == 5


def test_apply_agents_normalizes_jiuwen_agents(tmp_path):
    exp_dir = tmp_path / "hypothesis_1" / "experiment_1" / "init"
    exp_dir.mkdir(parents=True)
    (exp_dir / "init_config.json").write_text(json.dumps(_base_config()), encoding="utf-8")

    anyio.run(
        apply_agents,
        "1",
        "1",
        ApplyAgentsRequest(
            agents=[
                {
                    "agent_id": 2,
                    "agent_type": "JiuwenClawAgent",
                    "kwargs": {
                        "id": 2,
                        "name": "Jiuwen Bob",
                        "enable_skill_runtime": False,
                        "profile": {"name": "Jiuwen Bob"},
                    },
                }
            ]
        ),
        str(tmp_path),
    )

    saved = json.loads((exp_dir / "init_config.json").read_text(encoding="utf-8"))
    kwargs = saved["agents"][1]["kwargs"]
    assert kwargs["enable_skill_runtime"] is True
    assert len(kwargs["common_skill_ids"]) == 5
    assert len(kwargs["skill_ids"]) == 5


def test_apply_agents_replace_removes_orphan_initial_locations(tmp_path):
    exp_dir = tmp_path / "hypothesis_1" / "experiment_1" / "init"
    exp_dir.mkdir(parents=True)
    config = _base_config()
    config["env_modules"][0]["kwargs"]["initial_locations"] = {
        "1": "school",
        "2": "park",
    }
    (exp_dir / "init_config.json").write_text(json.dumps(config), encoding="utf-8")

    anyio.run(
        apply_agents,
        "1",
        "1",
        ApplyAgentsRequest(
            mode="replace",
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
            ],
        ),
        str(tmp_path),
    )

    saved = json.loads((exp_dir / "init_config.json").read_text(encoding="utf-8"))
    assert saved["env_modules"][0]["kwargs"]["agent_id_name_pairs"] == [[2, "Bob"]]
    assert saved["env_modules"][0]["kwargs"]["initial_locations"] == {"2": "park"}


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


def test_put_init_config_rejects_duplicate_agent_id(tmp_path):
    exp_dir = tmp_path / "hypothesis_1" / "experiment_1" / "init"
    exp_dir.mkdir(parents=True)
    config = _base_config()
    config["agents"].append(
        {
            "agent_id": 1,
            "agent_type": "PersonAgent",
            "kwargs": {
                "id": 1,
                "name": "Duplicate Alice",
                "profile": {"name": "Duplicate Alice"},
            },
        }
    )
    (exp_dir / "init_config.json").write_text(json.dumps(_base_config()), encoding="utf-8")

    with pytest.raises(HTTPException):
        anyio.run(put_init_config, "1", "1", config, str(tmp_path))

    saved = json.loads((exp_dir / "init_config.json").read_text(encoding="utf-8"))
    assert len(saved["agents"]) == 1
    assert saved["agents"][0]["kwargs"]["profile"]["name"] == "Alice"


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
