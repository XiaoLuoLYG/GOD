from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from agentsociety2.backend.routers import package_imports
from agentsociety2.backend.services import package_imports as package_import_service


def _client(monkeypatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("GOD_ROOT", str(tmp_path))
    monkeypatch.setenv("LIVE_WORKSPACE_PATH", str(tmp_path / "agentsociety" / "quick_experiments"))
    app = FastAPI()
    app.include_router(package_imports.router)
    return TestClient(app)


def _write_map_pack_zip(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    map_dir = source / "map"
    (map_dir / "visuals").mkdir(parents=True)
    (map_dir / "visuals" / "map.json").write_text(
        '{"type":"map","orientation":"orthogonal","width":1,"height":1,"tilewidth":32,"tileheight":32,"tilesets":[],"layers":[{"name":"Collisions","type":"tilelayer","width":1,"height":1,"data":[0]}]}',
        encoding="utf-8",
    )
    (map_dir / "map.yaml").write_text(
        "schema_version: 1\nmap_id: demo_map\ndisplay_name: Demo Map\ntiled_map_path: visuals/map.json\ntile_size: 32\nlocations:\n- id: plaza\n  name: Plaza\n  anchor_tile: {x: 0, y: 0}\ninteractions: []\n",
        encoding="utf-8",
    )
    zip_path = tmp_path / "map.zip"
    with ZipFile(zip_path, "w") as archive:
        for path in map_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(map_dir))
    return zip_path


def test_import_preview_rejects_unknown_zip(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    zip_path = tmp_path / "unknown.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("notes.txt", "hello")

    with zip_path.open("rb") as file:
        response = client.post(
            "/api/v1/god/packages/import-preview",
            files={"file": ("unknown.zip", file, "application/zip")},
        )

    assert response.status_code == 400
    assert "Could not identify package type" in response.text


def test_import_preview_rejects_replay_data_archive(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    zip_path = tmp_path / "god-town-replay-data.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("timeline.json", "[]")
        archive.writestr("steps/000000.json", "{}")
        archive.writestr("agents/profiles.json", "[]")
        archive.writestr("map/map.json", "{}")

    with zip_path.open("rb") as file:
        response = client.post(
            "/api/v1/god/packages/import-preview",
            files={"file": (zip_path.name, file, "application/zip")},
        )

    assert response.status_code == 400
    assert "Replay archives are viewable replay data" in response.text


def test_import_preview_cleans_staging_when_extract_fails(monkeypatch, tmp_path: Path) -> None:
    zip_path = tmp_path / "bad.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("../escape.txt", "nope")
    staging = tmp_path / "staging"
    monkeypatch.setattr(
        package_import_service.package_archives,
        "temp_staging_dir",
        lambda _prefix: staging,
    )

    with pytest.raises(ValueError, match="escapes extract root"):
        package_import_service.create_preview(
            zip_path,
            agentsociety_root=tmp_path / "agentsociety",
            workspace_root=tmp_path / "workspace",
        )

    assert not staging.exists()


def test_map_import_preview_and_install(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    zip_path = _write_map_pack_zip(tmp_path)

    with zip_path.open("rb") as file:
        preview = client.post(
            "/api/v1/god/packages/import-preview",
            files={"file": ("map.zip", file, "application/zip")},
        )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["package_type"] == "map"
    assert payload["resource_id"] == "demo_map"

    install = client.post(
        "/api/v1/god/packages/install",
        json={"preview_token": payload["preview_token"], "conflict_strategy": "save_as"},
    )

    assert install.status_code == 200
    assert (tmp_path / "agentsociety" / "custom" / "maps" / "demo_map" / "map.yaml").exists()


def test_install_preview_cleans_staging_when_rezip_fails(monkeypatch, tmp_path: Path) -> None:
    zip_path = _write_map_pack_zip(tmp_path)
    preview = package_import_service.create_preview(
        zip_path,
        agentsociety_root=tmp_path / "agentsociety",
        workspace_root=tmp_path / "workspace",
    )
    staging = preview.staging_root

    def fail_zip(_source: Path, _target: Path) -> Path:
        raise RuntimeError("zip failed")

    monkeypatch.setattr(package_import_service.package_archives, "zip_directory", fail_zip)

    with pytest.raises(RuntimeError, match="zip failed"):
        package_import_service.install_preview(
            preview_token=preview.token,
            conflict_strategy="save_as",
            agentsociety_root=tmp_path / "agentsociety",
            workspace_root=tmp_path / "workspace",
        )

    assert not staging.exists()


def test_experiment_preview_uses_zip_name_when_old_pack_has_no_id(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    zip_path = tmp_path / "god-town-experiment-pack.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "init/init_config.json",
            '{"env_modules":[{"module_type":"PixelTownSocialEnv","kwargs":{"map_id":"the_ville"}}],"agents":[{"agent_id":1,"agent_type":"JiuwenClawAgent","kwargs":{"id":1}}]}',
        )
        archive.writestr(
            "init/steps.yaml",
            "start_t: '2026-05-11T08:20:00+08:00'\nsteps:\n- type: run\n  num_steps: 1\n  tick: 600\n",
        )

    with zip_path.open("rb") as file:
        preview = client.post(
            "/api/v1/god/packages/import-preview",
            files={"file": (zip_path.name, file, "application/zip")},
        )

    assert preview.status_code == 200
    assert preview.json()["resource_id"] == "god-town"


def test_experiment_import_warns_and_installs_setup_without_run(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    zip_path = tmp_path / "god-town-experiment-pack.zip"
    init_config = {
        "env_modules": [
            {
                "module_type": "PixelTownSocialEnv",
                "kwargs": {
                    "map_id": "the_ville",
                    "map_manifest_path": "/Users/example/GOD/agentsociety/custom/maps/the_ville/map.yaml",
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
                    "session_id": "local-run-agent-1",
                    "trusted_dirs": ["/Users/example/GOD/agentsociety"],
                },
            }
        ],
    }
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("init/init_config.json", json.dumps(init_config))
        archive.writestr(
            "init/steps.yaml",
            "start_t: '2026-05-11T08:20:00+08:00'\nsteps:\n- type: run\n  num_steps: 1\n  tick: 600\n",
        )
        archive.writestr("run.sh", "#!/usr/bin/env bash\n")
        archive.writestr("run/sqlite.db", "db")
        archive.writestr("run/thread_messages.jsonl", "{}")
        archive.writestr("run/agents/1/.runtime/agent_state_snapshot.json", "{}")
        archive.writestr("run_2/sqlite.db", "db")

    with zip_path.open("rb") as file:
        preview = client.post(
            "/api/v1/god/packages/import-preview",
            files={"file": (zip_path.name, file, "application/zip")},
        )
    assert preview.status_code == 200
    payload = preview.json()
    assert any("ignored run content" in warning for warning in payload["validation"]["warnings"])

    install = client.post(
        "/api/v1/god/packages/install",
        json={"preview_token": payload["preview_token"], "conflict_strategy": "save_as"},
    )

    assert install.status_code == 200
    target = Path(install.json()["install_path"])
    assert target.joinpath("init", "init_config.json").exists()
    installed_text = target.joinpath("init", "init_config.json").read_text(encoding="utf-8")
    assert "session_id" not in installed_text
    assert "trusted_dirs" not in installed_text
    assert "/Users/" not in installed_text
    assert target.joinpath("run.sh").exists()
    assert not target.joinpath("run").exists()
    assert not target.joinpath("run_2").exists()
