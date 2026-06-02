from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from zipfile import ZipFile

from agentsociety2.backend.services import package_imports
from agentsociety2.backend.services.public_replay_export import (
    export_curated_experiment_packs,
    export_public_replay,
    load_operator_commands,
)


def test_load_operator_commands_backfills_markdown_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "ask_live_step_3_20260531_093000.md").write_text(
        "---\n"
        "question: Where are you?\n"
        "target:\n"
        "  type: agent\n"
        "  agent_id: 1\n"
        "---\n\n"
        "### Alice\nAt the park.\n",
        encoding="utf-8",
    )

    commands = load_operator_commands(run_dir)

    assert commands == [
        {
            "command_id": "ask_live_step_3_20260531_093000",
            "type": "ask",
            "step": 3,
            "simulation_time": "2026-05-31T09:30:00",
            "prompt": "Where are you?",
            "target": {"type": "agent", "agent_id": 1},
            "result": "### Alice\nAt the park.",
            "artifact_name": "ask_live_step_3_20260531_093000.md",
            "status": "completed",
        }
    ]


def test_export_public_replay_writes_static_bundle(tmp_path: Path) -> None:
    workspace = tmp_path / "quick_experiments"
    experiment_root = workspace / "hypothesis_demo_world" / "experiment_1"
    run_dir = experiment_root / "run"
    init_dir = experiment_root / "init"
    run_dir.mkdir(parents=True)
    init_dir.mkdir(parents=True)
    map_manifest = _write_map_package(tmp_path / "custom" / "maps" / "demo")
    init_dir.joinpath("init_config.json").write_text(
        json.dumps(
                {
                    "env_modules": [
                        {
                            "module_type": "PixelTownSocialEnv",
                            "kwargs": {"map_manifest_path": str(map_manifest)},
                        }
                    ],
                    "agents": [
                        {
                            "agent_id": 1,
                            "agent_type": "JiuwenClawAgent",
                            "kwargs": {
                                "id": 1,
                                "name": "Alice",
                                "profile": {"name": "Alice"},
                                "session_id": "demo-run-agent-1",
                                "trusted_dirs": ["/Users/example/GOD/agentsociety"],
                            },
                        }
                    ],
                }
            ),
        encoding="utf-8",
    )
    init_dir.joinpath("steps.yaml").write_text(
        "start_t: '2026-05-11T08:20:00+08:00'\nsteps:\n- type: run\n  num_steps: 2\n  tick: 600\n",
        encoding="utf-8",
    )
    experiment_root.joinpath("README.md").write_text("# Demo World\n", encoding="utf-8")
    experiment_root.joinpath("run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    _write_replay_db(run_dir / "sqlite.db")
    run_dir.joinpath("artifacts").mkdir()
    run_dir.joinpath("artifacts", "intervene_live_step_1_20260531_100000.md").write_text(
        "---\n"
        "instruction: Move Alice to the plaza.\n"
        "target:\n"
        "  type: agent\n"
        "  agent_id: 1\n"
        "---\n\n"
        "Alice is moving.\n",
        encoding="utf-8",
    )
    run_dir.joinpath("thread_messages.jsonl").write_text("{}", encoding="utf-8")
    run_dir.joinpath("logs").mkdir()
    run_dir.joinpath("logs", "runtime.log").write_text("debug", encoding="utf-8")
    run_dir.joinpath("agents", "1", ".runtime").mkdir(parents=True)
    run_dir.joinpath("agents", "1", ".runtime", "agent_state_snapshot.json").write_text(
        "{}",
        encoding="utf-8",
    )

    manifest = export_public_replay(
        workspace_path=workspace,
        hypothesis_id="demo_world",
        experiment_id="1",
        slug="demo-world",
        output_root=tmp_path / "site-data",
        title="Demo World",
        summary="A minimal exported replay.",
    )

    replay_root = tmp_path / "site-data" / "replays" / "demo-world"
    assert manifest["slug"] == "demo-world"
    assert manifest["agent_count"] == 1
    assert manifest["total_steps"] == 2
    assert replay_root.joinpath("manifest.json").exists()
    assert json.loads(replay_root.joinpath("timeline.json").read_text())[0]["step"] == 0
    assert json.loads(replay_root.joinpath("commands.json").read_text())[0]["type"] == "intervene"
    step = json.loads(replay_root.joinpath("steps", "000001.json").read_text())
    assert step["agents"][0]["name"] == "Alice"
    assert step["agents"][0]["tile_x"] == 2
    assert step["env"]["latest_event"] == "Alice moved."
    map_info = json.loads(replay_root.joinpath("map", "map.json").read_text())
    assert map_info["tiled_map_url"] == "tiled-map.json"
    assert replay_root.joinpath("map", "assets", "tileset-0.png").exists()
    assert replay_root.joinpath("downloads", "demo-world-replay-data.zip").exists()
    map_pack_root = tmp_path / "site-data" / "map-packs" / "demo"
    assert map_pack_root.joinpath("map_pack.json").exists()
    assert map_pack_root.joinpath("tiled-map.json").exists()
    assert map_pack_root.joinpath("assets", "tileset-0.png").exists()
    agent_pack_root = tmp_path / "site-data" / "agent-packs" / "demo-world-agents"
    assert agent_pack_root.joinpath("agent_pack.json").exists()
    assert agent_pack_root.joinpath("agents", "1", "profile.json").exists()
    assert agent_pack_root.joinpath("characters", "Alice.png").exists()
    experiment_pack_root = tmp_path / "site-data" / "experiments" / "demo-world-experiment"
    assert experiment_pack_root.joinpath("experiment.json").exists()
    experiment_manifest = json.loads(experiment_pack_root.joinpath("experiment.json").read_text())
    assert experiment_manifest["kind"] == "experiment"
    assert "Playable setup seed" in experiment_manifest["summary"]
    assert experiment_manifest["example_replay"]["slug"] == "demo-world"
    assert experiment_manifest["downloads"][0]["label"] == "Playable Experiment Pack"
    assert "local runtime state" in experiment_manifest["downloads"][0]["description"]
    assert manifest["downloads"][0]["label"] == "Replay archive"
    assert manifest["downloads"][0]["type"] == "replay"
    assert manifest["downloads"][0]["hidden"] is True
    assert manifest["downloads"][3]["label"] == "Playable Experiment Pack"
    with ZipFile(replay_root.joinpath("downloads", "demo-world-agent-pack.zip")) as archive:
        names = set(archive.namelist())
    assert "agent_pack.yaml" in names
    assert "agents/1/profile.json" in names
    assert "characters/Alice.png" in names
    with ZipFile(agent_pack_root.joinpath("downloads", "demo-world-agents-agent-pack.zip")) as archive:
        names = set(archive.namelist())
    assert "agent_pack.yaml" in names
    assert "characters/Alice.png" in names
    assert "downloads/demo-world-agents-agent-pack.zip" not in names
    for zip_path in (
        experiment_pack_root.joinpath("downloads", "demo-world-experiment-experiment-pack.zip"),
        replay_root.joinpath("downloads", "demo-world-experiment-pack.zip"),
    ):
        with ZipFile(zip_path) as archive:
            names = set(archive.namelist())
            exported_config = json.loads(archive.read("init/init_config.json").decode("utf-8"))
            exported_text = json.dumps(exported_config)
        assert "init/init_config.json" in names
        assert "init/steps.yaml" in names
        assert "README.md" in names
        assert "run.sh" in names
        assert "session_id" not in exported_text
        assert "trusted_dirs" not in exported_text
        assert str(tmp_path) not in exported_text
        assert "/Users/" not in exported_text
        assert exported_config["env_modules"][0]["kwargs"]["map_id"] == "demo"
        assert "map_manifest_path" not in exported_config["env_modules"][0]["kwargs"]
        assert not any(name.startswith("run/") or name.startswith("run_") for name in names)
        assert not any(".runtime/" in name for name in names)
        assert not any(name.endswith(("sqlite.db", ".sqlite", ".sqlite3", ".log")) for name in names)
        assert "thread_messages.jsonl" not in names
        assert "agent_state_snapshot.json" not in names
        import_workspace = tmp_path / "imports" / zip_path.stem / "quick_experiments"
        import_workspace.mkdir(parents=True)
        preview = package_imports.create_preview(
            zip_path,
            agentsociety_root=tmp_path,
            workspace_root=import_workspace,
            original_filename=zip_path.name,
        )
        assert preview.package_type == "experiment"
        assert preview.validation["ok"] is True
        result = package_imports.install_preview(
            preview_token=preview.token,
            conflict_strategy="save_as",
            agentsociety_root=tmp_path,
            workspace_root=import_workspace,
            requested_id=preview.resource_id,
        )
        installed = Path(str(result["install_path"]))
        assert installed.joinpath("init", "init_config.json").exists()
        assert installed.joinpath("init", "steps.yaml").exists()
        assert not installed.joinpath("run").exists()
    with ZipFile(replay_root.joinpath("downloads", "demo-world-replay-data.zip")) as archive:
        names = set(archive.namelist())
    assert "timeline.json" in names
    assert "steps/000001.json" in names
    assert "commands.json" in names
    assert manifest["urls"]["map_pack"] == "../../map-packs/demo/map_pack.json"
    assert manifest["urls"]["agent_pack"] == "../../agent-packs/demo-world-agents/agent_pack.json"
    assert manifest["urls"]["experiment_pack"] == "../../experiments/demo-world-experiment/experiment.json"


def test_export_curated_experiment_pack_without_replay(tmp_path: Path) -> None:
    workspace = tmp_path / "quick_experiments"
    experiment_root = workspace / "hypothesis_moon_role_study" / "experiment_1"
    init_dir = experiment_root / "init"
    init_dir.mkdir(parents=True)
    init_dir.joinpath("init_config.json").write_text(
        json.dumps(
            {
                "env_modules": [
                    {
                        "module_type": "PixelTownSocialEnv",
                        "kwargs": {
                            "map_id": "moon_base",
                            "map_manifest_path": "/Users/example/GOD/agentsociety/custom/maps/moon_base/map.yaml",
                        },
                    }
                ],
                "agents": [
                    {
                        "agent_id": 1,
                        "agent_type": "JiuwenClawAgent",
                        "kwargs": {
                            "id": 1,
                            "name": "Lin",
                            "profile": {"name": "Lin"},
                            "session_id": "local-run-agent-1",
                            "trusted_dirs": ["/Users/example/GOD"],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    init_dir.joinpath("steps.yaml").write_text(
        "start_t: '2026-05-11T08:20:00+08:00'\nsteps:\n- type: run\n  num_steps: 2\n  tick: 900\n",
        encoding="utf-8",
    )
    init_dir.joinpath("experiment_context.json").write_text(
        json.dumps({"title": "Moon Role Study", "map_id": "moon_base"}),
        encoding="utf-8",
    )
    experiment_root.joinpath("README.md").write_text("# Moon Role Study\n", encoding="utf-8")
    output_root = tmp_path / "site-data"

    manifests = export_curated_experiment_packs(
        workspace_path=workspace,
        output_root=output_root,
        registry_entries=[
            {
                "key": "moon_role_study",
                "label": "Moon Role Study",
                "description": "A no-replay curated ExperimentPack.",
                "hypothesis_id": "moon_role_study",
                "experiment_id": "1",
                "map_id": "moon_base",
                "public_slug": "moon-role-study",
                "image": "assets/screenshots/map-the-ville.png",
                "tags": ["role study"],
                "enabled": True,
            }
        ],
    )

    assert [item["pack_id"] for item in manifests] == ["moon-role-study"]
    manifest = json.loads(output_root.joinpath("experiments", "moon-role-study", "experiment.json").read_text())
    assert manifest["display_name"] == "Moon Role Study"
    assert manifest["summary"] == "A no-replay curated ExperimentPack."
    assert manifest["agent_count"] == 1
    assert manifest["total_steps"] == 2
    assert "agent_pack" not in manifest
    assert "agent_pack" not in manifest["urls"]
    assert "example_replay" not in manifest
    assert "replay" not in manifest["urls"]
    zip_path = output_root / "experiments" / "moon-role-study" / "downloads" / "moon-role-study-experiment-pack.zip"
    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        exported_config = json.loads(archive.read("init/init_config.json").decode("utf-8"))
        exported_text = json.dumps(exported_config)
    assert "init/init_config.json" in names
    assert "init/steps.yaml" in names
    assert "session_id" not in exported_text
    assert "trusted_dirs" not in exported_text
    assert "/Users/" not in exported_text
    preview = package_imports.create_preview(
        zip_path,
        agentsociety_root=tmp_path,
        workspace_root=tmp_path / "imports",
        original_filename=zip_path.name,
    )
    assert preview.package_type == "experiment"
    assert preview.validation["ok"] is True


def _write_map_package(package_root: Path) -> Path:
    package_root.mkdir(parents=True)
    visuals = package_root / "visuals"
    visuals.mkdir()
    characters = package_root / "characters"
    characters.mkdir()
    characters.joinpath("Alice.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00`\x00\x00\x00\x80"
        b"\x08\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    visuals.joinpath("tiles.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x20\x00\x00\x00 "
        b"\x08\x06\x00\x00\x00szz\xf4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    visuals.joinpath("map.json").write_text(
        json.dumps(
            {
                "type": "map",
                "width": 4,
                "height": 3,
                "tilewidth": 32,
                "tileheight": 32,
                "tilesets": [
                    {
                        "firstgid": 1,
                        "name": "demo",
                        "image": "tiles.png",
                        "imagewidth": 32,
                        "imageheight": 32,
                        "tilewidth": 32,
                        "tileheight": 32,
                        "columns": 1,
                        "tilecount": 1,
                    }
                ],
                "layers": [
                    {
                        "name": "Ground",
                        "type": "tilelayer",
                        "visible": True,
                        "data": [1] * 12,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = package_root / "map.yaml"
    manifest.write_text(
        "schema_version: 1\n"
        "map_id: demo\n"
        "display_name: Demo Map\n"
        "tiled_map_path: visuals/map.json\n"
        "tile_size: 32\n"
        "character_root: characters\n"
        "locations:\n"
        "  - id: plaza\n"
        "    name: Plaza\n"
        "    anchor_tile: {x: 2, y: 1}\n"
        "interactions: []\n",
        encoding="utf-8",
    )
    return manifest


def _write_replay_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE replay_dataset_catalog (
              dataset_id TEXT PRIMARY KEY,
              table_name TEXT NOT NULL,
              module_name TEXT NOT NULL,
              kind TEXT NOT NULL,
              title TEXT,
              description TEXT,
              entity_key TEXT,
              step_key TEXT,
              time_key TEXT,
              default_order_json JSON NOT NULL,
              capabilities_json JSON NOT NULL,
              version INTEGER NOT NULL,
              created_at TIMESTAMP NOT NULL
            );
            CREATE TABLE replay_column_catalog (
              dataset_id TEXT NOT NULL,
              column_name TEXT NOT NULL,
              sqlite_type TEXT NOT NULL,
              logical_type TEXT,
              analysis_role TEXT,
              title TEXT,
              description TEXT,
              unit TEXT,
              enum_json JSON,
              example_json JSON,
              nullable INTEGER NOT NULL,
              tags_json JSON NOT NULL
            );
            CREATE TABLE core_agent_profile (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              profile JSON NOT NULL,
              created_at TIMESTAMP NOT NULL
            );
            CREATE TABLE pixel_town_social_agent_state (
              agent_id INTEGER NOT NULL,
              step INTEGER NOT NULL,
              t TIMESTAMP NOT NULL,
              name TEXT,
              location TEXT,
              action TEXT,
              status TEXT,
              emotion TEXT,
              message_count INTEGER,
              last_message TEXT,
              recent_messages JSON,
              map_id TEXT,
              tile_x INTEGER,
              tile_y INTEGER,
              location_id TEXT,
              movement_status TEXT,
              PRIMARY KEY (agent_id, step)
            );
            CREATE TABLE pixel_town_social_env_state (
              step INTEGER PRIMARY KEY,
              t TIMESTAMP NOT NULL,
              total_messages_sent INTEGER,
              latest_event TEXT,
              latest_communications TEXT
            );
            """
        )
        _insert_dataset(
            conn,
            "core.agent_profile",
            "core_agent_profile",
            "entity_static",
            "id",
            None,
            None,
            ["id"],
            ["agent_profile", "entity_static"],
            ["id", "name", "profile", "created_at"],
            {"profile": "JSON"},
        )
        _insert_dataset(
            conn,
            "pixel_town_social.agent_state",
            "pixel_town_social_agent_state",
            "entity_snapshot",
            "agent_id",
            "step",
            "t",
            ["step", "agent_id"],
            ["agent_snapshot", "timeseries", "tile_point", "trajectory"],
            [
                "agent_id",
                "step",
                "t",
                "name",
                "location",
                "action",
                "status",
                "emotion",
                "message_count",
                "last_message",
                "recent_messages",
                "map_id",
                "tile_x",
                "tile_y",
                "location_id",
                "movement_status",
            ],
            {"recent_messages": "JSON"},
        )
        _insert_dataset(
            conn,
            "pixel_town_social.env_state",
            "pixel_town_social_env_state",
            "env_snapshot",
            None,
            "step",
            "t",
            ["step"],
            ["env_snapshot", "timeseries"],
            [
                "step",
                "t",
                "total_messages_sent",
                "latest_event",
                "latest_communications",
            ],
            {},
        )
        conn.execute(
            "INSERT INTO core_agent_profile VALUES (?, ?, ?, ?)",
            (
                1,
                "Alice",
                json.dumps(
                    {
                        "role": "tester",
                        "appearance": {
                            "character_sprite": "Alice",
                            "character_sprite_filename": "Alice.png",
                        },
                    }
                ),
                "2026-05-31T09:00:00",
            ),
        )
        conn.execute(
            "INSERT INTO pixel_town_social_agent_state VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                0,
                "2026-05-31T09:00:00",
                "Alice",
                "Plaza",
                "Standing",
                "idle",
                "calm",
                0,
                "",
                "[]",
                "demo",
                1,
                1,
                "plaza",
                "idle",
            ),
        )
        conn.execute(
            "INSERT INTO pixel_town_social_agent_state VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                1,
                "2026-05-31T09:30:00",
                "Alice",
                "Plaza",
                "Moving",
                "active",
                "focused",
                1,
                "On my way.",
                json.dumps([{"content": "On my way."}]),
                "demo",
                2,
                1,
                "plaza",
                "moving",
            ),
        )
        conn.execute(
            "INSERT INTO pixel_town_social_env_state VALUES (?, ?, ?, ?, ?)",
            (0, "2026-05-31T09:00:00", 0, "Start.", "[]"),
        )
        conn.execute(
            "INSERT INTO pixel_town_social_env_state VALUES (?, ?, ?, ?, ?)",
            (1, "2026-05-31T09:30:00", 1, "Alice moved.", '[{"content":"On my way."}]'),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_dataset(
    conn: sqlite3.Connection,
    dataset_id: str,
    table_name: str,
    kind: str,
    entity_key: str | None,
    step_key: str | None,
    time_key: str | None,
    default_order: list[str],
    capabilities: list[str],
    columns: list[str],
    sqlite_types: dict[str, str],
) -> None:
    conn.execute(
        "INSERT INTO replay_dataset_catalog VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            dataset_id,
            table_name,
            "Test",
            kind,
            "",
            "",
            entity_key,
            step_key,
            time_key,
            json.dumps(default_order),
            json.dumps(capabilities),
            1,
            "2026-05-31T09:00:00",
        ),
    )
    for column in columns:
        conn.execute(
            "INSERT INTO replay_column_catalog VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                dataset_id,
                column,
                sqlite_types.get(column, "TEXT"),
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                1,
                "[]",
            ),
        )
