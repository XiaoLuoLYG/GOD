from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from runpy import run_path
import subprocess
from zipfile import ZipFile

import pytest

from agentsociety2.backend.routers import experiment_configs, god_setup, replay
from agentsociety2.backend.services import experiment_packs, package_archives, public_replay_export
from agentsociety2.society.experiment_runner import portable_experiment_runner
from agentsociety2.society.launch_config import prepare_launch


def _write_experiment(root: Path) -> Path:
    exp = root / "quick_experiments" / "hypothesis_demo" / "experiment_1"
    (exp / "init").mkdir(parents=True)
    (exp / "init" / "init_config.json").write_text(
        json.dumps(
            {
                "env_modules": [
                    {
                        "module_type": "PixelTownSocialEnv",
                        "kwargs": {
                            "map_id": "demo_map",
                            "map_manifest_path": "/Users/example/GOD/agentsociety/custom/maps/demo_map/map.yaml",
                        },
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
                            "session_id": "demo-local-run-agent-1",
                            "trusted_dirs": ["/Users/example/GOD/agentsociety"],
                        },
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


@pytest.mark.parametrize(("manifest", "expected"), [
    ("/Users/author/map.yaml", None),
    (r"C:\Users\author\map.yaml", None),
    (r"\\server\share\map.yaml", None),
    (r"~\maps\map.yaml", None),
    ("custom/maps/demo/map.yaml", "custom/maps/demo/map.yaml"),
    (r"custom\maps\demo\map.yaml", "custom/maps/demo/map.yaml"),
])
def test_pack_manifest_references_are_portable(manifest: str, expected: str | None) -> None:
    config = {"env_modules": [{"module_type": "PixelTownSocialEnv", "kwargs": {"map_manifest_path": manifest}}]}
    cleaned = experiment_packs.sanitize_experiment_pack_config(config)
    kwargs = cleaned["env_modules"][0]["kwargs"]
    assert kwargs == ({} if expected is None else {"map_manifest_path": expected})


def test_export_experiment_pack_excludes_run_state(tmp_path: Path) -> None:
    root = tmp_path / "agentsociety"
    exp = _write_experiment(root)
    (exp / "run" / "artifacts").mkdir(parents=True)
    (exp / "run" / "sqlite.db").write_bytes(b"db")
    (exp / "run" / "artifacts" / "ask.md").write_text("runtime answer", encoding="utf-8")
    (exp / "run" / "logs").mkdir()
    (exp / "run" / "logs" / "agent.log").write_text("debug", encoding="utf-8")
    (exp / "run" / "agents" / "1" / ".runtime").mkdir(parents=True)
    (exp / "run" / "agents" / "1" / ".runtime" / "agent_state_snapshot.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (exp / "run_2").mkdir()
    (exp / "run_2" / "sqlite.db").write_bytes(b"db")
    (exp / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    zip_path = tmp_path / "demo-experiment.zip"

    experiment_packs.export_experiment_pack(exp, zip_path)

    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        exported_config = json.loads(archive.read("init/init_config.json").decode("utf-8"))
        exported_text = json.dumps(exported_config)
    assert "init/init_config.json" in names
    assert "init/steps.yaml" in names
    assert "run.sh" in names
    assert "session_id" not in exported_text
    assert "trusted_dirs" not in exported_text
    assert "/Users/" not in exported_text
    assert exported_config["env_modules"][0]["kwargs"]["map_id"] == "demo_map"
    assert "map_manifest_path" not in exported_config["env_modules"][0]["kwargs"]
    assert not any(name.startswith("run/") or name.startswith("run_") for name in names)
    assert not any(name.endswith(("sqlite.db", ".sqlite", ".sqlite3", ".log")) for name in names)
    assert not any(".runtime/" in name for name in names)
    assert "thread_messages.jsonl" not in names
    assert "agent_state_snapshot.json" not in names


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


def test_launched_map_is_used_by_studio_replay_and_pack_export(tmp_path, monkeypatch):
    root = tmp_path / "agentsociety"
    experiment = _write_experiment(root)
    config = experiment / "init/init_config.json"
    source = config.read_bytes()
    workspace = root / "quick_experiments"
    monkeypatch.setenv("LIVE_WORKSPACE_PATH", str(workspace))
    monkeypatch.setenv("GOD_MAP_ID", "event_map")
    _write_map_dependency(root, "event_map")
    prepare_launch(config, root, 19876)

    selected = {"workspace_path": str(workspace), "hypothesis_id": "demo", "experiment_id": "1", "map_id": "demo_map"}
    assert god_setup._current_map_id(selected) == "event_map"
    editor = asyncio.run(experiment_configs.get_init_config("demo", "1", str(workspace)))
    assert editor.map_id == "event_map" and editor.config == json.loads(source)
    assert replay._resolve_experiment_map_package(str(workspace), "demo", "1").map_id == "event_map"

    archive_path = tmp_path / "played-experiment.zip"
    experiment_packs.export_experiment_pack(experiment, archive_path, agentsociety_root=root)
    with ZipFile(archive_path) as archive:
        assert "dependencies/maps/event_map/map.yaml" in archive.namelist()
        assert not any(path.startswith("run/") for path in archive.namelist())
        packed = json.loads(archive.read("init/init_config.json"))
        assert packed["env_modules"][0]["kwargs"]["map_manifest_path"] == "custom/maps/event_map/map.yaml"
        assert "trusted_dirs" not in packed["agents"][0]["kwargs"]
    assert config.read_bytes() == source


def test_imported_experiment_pack_can_be_exported_again(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    first_zip = tmp_path / "first.zip"
    second_zip = tmp_path / "second.zip"
    experiment_packs.export_experiment_pack(_write_experiment(source_root), first_zip, agentsociety_root=source_root)
    installed = experiment_packs.import_experiment_pack_zip(
        first_zip,
        workspace_root=target_root / "quick_experiments",
        agentsociety_root=target_root,
    )

    experiment_packs.export_experiment_pack(installed.package_path, second_zip, agentsociety_root=target_root)

    with ZipFile(second_zip) as archive:
        assert "dependencies/agent_packs/demo-experiment_1-agents/agent_pack.yaml" in archive.namelist()


def test_import_old_public_experiment_pack_warns_and_ignores_run_artifacts(tmp_path: Path) -> None:
    source = _write_experiment(tmp_path / "source")
    (source / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (source / "run" / "artifacts").mkdir(parents=True)
    (source / "run" / "artifacts" / "ask.md").write_text("hello", encoding="utf-8")
    (source / "run" / "sqlite.db").write_bytes(b"db")
    (source / "run" / "agents" / "1" / ".runtime").mkdir(parents=True)
    (source / "run" / "agents" / "1" / ".runtime" / "agent_state_snapshot.json").write_text(
        "{}",
        encoding="utf-8",
    )
    zip_path = tmp_path / "old-public.zip"
    with ZipFile(zip_path, "w") as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source))

    imported = experiment_packs.import_experiment_pack_zip(zip_path, workspace_root=tmp_path / "target")

    assert imported.validation.ok is True
    assert any("ignored run content" in warning for warning in imported.validation.warnings)
    target = tmp_path / "target" / "hypothesis_demo" / "experiment_1"
    assert target.joinpath("init", "init_config.json").exists()
    installed_text = target.joinpath("init", "init_config.json").read_text(encoding="utf-8")
    assert "session_id" not in installed_text
    assert "trusted_dirs" not in installed_text
    assert "/Users/" not in installed_text
    assert target.joinpath("run.sh").exists()
    assert not target.joinpath("run").exists()
    assert not target.joinpath("run_2").exists()


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


def test_pack_runner_migration_preserves_custom_scripts_and_curated_environment(tmp_path: Path) -> None:
    legacy = (Path(__file__).parent / "fixtures/legacy_god_town_runner.txt").read_bytes().replace(b"\r\n", b"\n")
    backend = Path(__file__).resolve().parents[3]
    expected = (backend / "quick_experiments/hypothesis_god_town/experiment_1/run.sh").read_bytes().replace(b"\r\n", b"\n")
    stage_zip_asset = run_path(str(backend.parent / "scripts/publish_site_release_assets.py"))["stage_zip_asset"]
    curated = legacy[:legacy.index(b"if [[ -f .env")] + legacy[legacy.index(b"PYTHON_PATH="):]
    curated = curated.replace(b"god_town", b"gaokao-blackout")
    curated_portable = expected[:expected.index(b"if [[ -f .env")] + expected[expected.index(b"PYTHON_PATH="):]
    custom = legacy.replace(b"--log-level INFO", b"--log-level DEBUG").replace(b"\n", b"\r\n") + b"# \xff\r\n"
    source = _write_experiment(tmp_path / "source")
    script = source / "run.sh"
    large_custom = custom * 10
    for original, result in (
        (legacy, expected), (curated, curated_portable), (custom, custom), (large_custom, large_custom),
    ):
        assert portable_experiment_runner(result) == result
        script.write_bytes(original)
        for exporter in (experiment_packs.export_experiment_pack, public_replay_export._zip_experiment_pack):
            archive_path = tmp_path / "exported.zip"
            exporter(source, archive_path)
            with ZipFile(archive_path) as archive:
                assert archive.read("run.sh") == result
            assert script.read_bytes() == original
        archive_path = package_archives.zip_directory(source, tmp_path / "original-experiment-pack.zip")
        before_staging = archive_path.read_bytes()
        staged = stage_zip_asset(source_zip=archive_path, asset_root=tmp_path, target_dir=tmp_path / "staged")
        with ZipFile(staged) as archive:
            assert archive.read("run.sh") == result
            assert archive_path.read_bytes() == before_staging
        installed = experiment_packs.import_experiment_pack_zip(archive_path, workspace_root=tmp_path / "copies", overwrite=True)
        assert (installed.package_path / "run.sh").read_bytes() == result


@pytest.mark.skipif(os.name == "nt", reason="The standalone quick experiment is a Bash script")
def test_imported_runner_uses_its_own_experiment_and_replay(tmp_path: Path) -> None:
    source = _write_experiment(tmp_path / "source")
    (source / "run.sh").write_bytes((Path(__file__).parent / "fixtures/legacy_god_town_runner.txt").read_bytes())
    archive_path = package_archives.zip_directory(source, tmp_path / "legacy.zip")
    copies = []
    for experiment_id in ("1", "2"):
        installed = experiment_packs.import_experiment_pack_zip(
            archive_path, workspace_root=tmp_path / "external workspace", requested_hypothesis_id="renamed",
            requested_experiment_id=experiment_id,
        ).package_path
        copies.append(installed)
        run = installed / "run"
        run.mkdir()
        for filename in ("sqlite.db", ".god-launch.json", ".god-session-prefix"):
            (run / filename).write_text(experiment_id, encoding="utf-8")

    backend = tmp_path / "GOD backend"
    backend.mkdir()
    (backend / ".env").write_text("AGENTSOCIETY_LLM_API_KEY=test-key\n", encoding="utf-8")
    python = backend / "selected interpreter"
    python.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$PWD" "$@"\n', encoding="utf-8")
    python.chmod(0o755)
    first, second = copies
    result = subprocess.run(
        ["bash", str(second / "run.sh")], cwd=tmp_path, check=True, capture_output=True, text=True,
        env={"PATH": os.environ["PATH"], "BACKEND_ROOT": str(backend), "PYTHON_PATH": str(python)},
    )
    assert result.stdout.splitlines() == [
        str(backend), "-m", "agentsociety2.society.cli", "--config", str(second / "init/init_config.json"),
        "--steps", str(second / "init/steps.yaml"), "--run-dir", str(second / "run"),
        "--experiment-id", "renamed_2", "--log-level", "INFO", "--log-file", str(second / "run/output.log"),
    ]
    assert (first / "run/sqlite.db").read_bytes() == b"1"
    assert not (second / "run/sqlite.db").exists()
    for index, copy in enumerate(copies, 1):
        for marker in (".god-launch.json", ".god-session-prefix"):
            assert (copy / "run" / marker).read_text(encoding="utf-8") == str(index)
