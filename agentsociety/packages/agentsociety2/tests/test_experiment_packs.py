from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from agentsociety2.backend.services import experiment_packs


def _write_experiment(root: Path) -> Path:
    exp = root / "quick_experiments" / "hypothesis_demo" / "experiment_1"
    (exp / "init").mkdir(parents=True)
    (exp / "init" / "init_config.json").write_text(
        json.dumps(
            {
                "env_modules": [{"module_type": "PixelTownSocialEnv", "kwargs": {"map_id": "demo_map"}}],
                "agents": [
                    {
                        "agent_id": 1,
                        "agent_type": "JiuwenClawAgent",
                        "kwargs": {"id": 1, "name": "Alice", "profile": {"name": "Alice"}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (exp / "init" / "steps.yaml").write_text(
        "start_t: '2026-05-11T08:20:00+08:00'\nsteps:\n- type: run\n  num_steps: 1\n  tick: 600\n",
        encoding="utf-8",
    )
    (exp / "init" / "experiment_context.json").write_text(
        json.dumps({"title": "Demo", "map_id": "demo_map"}),
        encoding="utf-8",
    )
    (exp / "README.md").write_text("# Demo\n", encoding="utf-8")
    return exp


def _write_map_dependency(root: Path, map_id: str = "demo_map") -> Path:
    package = root / "custom" / "maps" / map_id
    (package / "visuals").mkdir(parents=True)
    (package / "visuals" / "map.json").write_text(
        json.dumps(
            {
                "type": "map",
                "orientation": "orthogonal",
                "width": 1,
                "height": 1,
                "tilewidth": 32,
                "tileheight": 32,
                "tilesets": [],
                "layers": [{"name": "Collisions", "type": "tilelayer", "width": 1, "height": 1, "data": [0]}],
            }
        ),
        encoding="utf-8",
    )
    (package / "map.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                f"map_id: {map_id}",
                "display_name: Demo Map",
                "tiled_map_path: visuals/map.json",
                "tile_size: 32",
                "locations:",
                "- id: plaza",
                "  name: Plaza",
                "  anchor_tile: {x: 0, y: 0}",
                "interactions: []",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return package


def test_validate_experiment_pack_discovers_map_dependency(tmp_path: Path) -> None:
    exp = _write_experiment(tmp_path / "agentsociety")

    preview = experiment_packs.preview_experiment_pack(exp)

    assert preview.ok is True
    assert preview.hypothesis_id == "demo"
    assert preview.experiment_id == "1"
    assert preview.map_id == "demo_map"


def test_export_experiment_pack_excludes_run_state(tmp_path: Path) -> None:
    root = tmp_path / "agentsociety"
    exp = _write_experiment(root)
    (exp / "run").mkdir()
    (exp / "run" / "sqlite.db").write_bytes(b"db")
    zip_path = tmp_path / "demo-experiment.zip"

    experiment_packs.export_experiment_pack(exp, zip_path)

    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "init/init_config.json" in names
    assert "init/steps.yaml" in names
    assert "run/sqlite.db" not in names


def test_export_experiment_pack_can_embed_map_and_agent_dependencies(tmp_path: Path) -> None:
    root = tmp_path / "agentsociety"
    exp = _write_experiment(root)
    map_dir = root / "custom" / "maps" / "demo_map"
    (map_dir / "visuals").mkdir(parents=True)
    (map_dir / "visuals" / "map.json").write_text(
        json.dumps(
            {
                "type": "map",
                "orientation": "orthogonal",
                "width": 1,
                "height": 1,
                "tilewidth": 32,
                "tileheight": 32,
                "tilesets": [],
                "layers": [{"name": "Collisions", "type": "tilelayer", "width": 1, "height": 1, "data": [0]}],
            }
        ),
        encoding="utf-8",
    )
    (map_dir / "map.yaml").write_text(
        "schema_version: 1\nmap_id: demo_map\ndisplay_name: Demo Map\ntiled_map_path: visuals/map.json\ntile_size: 32\nlocations:\n- id: plaza\n  name: Plaza\n  anchor_tile: {x: 0, y: 0}\ninteractions: []\n",
        encoding="utf-8",
    )
    zip_path = tmp_path / "demo-with-deps.zip"

    experiment_packs.export_experiment_pack(exp, zip_path, agentsociety_root=root)

    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "dependencies/maps/demo_map/map.yaml" in names
    assert any(name.startswith("dependencies/agent_packs/") and name.endswith("/agent_pack.yaml") for name in names)


def test_import_old_public_experiment_pack_warns_and_ignores_run_artifacts(tmp_path: Path) -> None:
    source = _write_experiment(tmp_path / "source")
    (source / "run" / "artifacts").mkdir(parents=True)
    (source / "run" / "artifacts" / "ask.md").write_text("hello", encoding="utf-8")
    zip_path = tmp_path / "old-public.zip"
    experiment_packs.export_experiment_pack(source, zip_path, include_legacy_run_artifacts=True)

    imported = experiment_packs.import_experiment_pack_zip(zip_path, workspace_root=tmp_path / "target")

    assert imported.validation.ok is True
    assert any("ignored run content" in warning for warning in imported.validation.warnings)
    assert (tmp_path / "target" / "hypothesis_demo" / "experiment_1" / "init" / "init_config.json").exists()
    assert not (tmp_path / "target" / "hypothesis_demo" / "experiment_1" / "run").exists()


def test_import_experiment_pack_conflict_does_not_install_dependencies(tmp_path: Path) -> None:
    source_root = tmp_path / "source_agentsociety"
    exp = _write_experiment(source_root)
    _write_map_dependency(source_root)
    zip_path = tmp_path / "demo-with-deps.zip"
    experiment_packs.export_experiment_pack(exp, zip_path, agentsociety_root=source_root)
    workspace_root = tmp_path / "workspace"
    existing = workspace_root / "hypothesis_demo" / "experiment_1"
    (existing / "init").mkdir(parents=True)

    with pytest.raises(FileExistsError, match="already exists"):
        experiment_packs.import_experiment_pack_zip(
            zip_path,
            workspace_root=workspace_root,
            agentsociety_root=tmp_path / "target_agentsociety",
            overwrite=False,
        )

    assert not (tmp_path / "target_agentsociety" / "custom" / "maps" / "demo_map").exists()
