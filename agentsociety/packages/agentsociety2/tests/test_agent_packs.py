from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from agentsociety2.backend.services import agent_packs


def _write_agent_pack(root: Path, pack_id: str, *, map_id: str | None = None) -> Path:
    if map_id:
        package = root / "custom" / "maps" / map_id / "agent_packs" / pack_id
    else:
        package = root / "custom" / "agent_packs" / pack_id
    (package / "agents" / "alice").mkdir(parents=True)
    (package / "characters").mkdir()
    (package / "characters" / "Alice.png").write_bytes(b"sprite")
    (package / "agents" / "alice" / "profile.json").write_text(
        json.dumps(
            {
                "name": "Alice",
                "role": "tester",
                "appearance": {"character_sprite": "Alice"},
                "routine": {"initial_location": "old_place"},
            }
        ),
        encoding="utf-8",
    )
    (package / "agents" / "alice" / "runtime.json").write_text(
        json.dumps({"agent_type": "JiuwenClawAgent", "skill_ids": ["routine.daily"]}),
        encoding="utf-8",
    )
    (package / "agent_pack.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                f"pack_id: {pack_id}",
                "display_name: Alice Pack",
                "agents:",
                "- id: alice",
                "  name: Alice",
                "  profile_path: agents/alice/profile.json",
                "  runtime_path: agents/alice/runtime.json",
                "  sprite:",
                "    path: characters/Alice.png",
                "    frame_width: 32",
                "    frame_height: 32",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return package


def test_discovers_global_and_map_local_agent_packs(tmp_path: Path) -> None:
    root = tmp_path / "agentsociety"
    _write_agent_pack(root, "global_alice")
    _write_agent_pack(root, "map_alice", map_id="demo_map")

    packs = agent_packs.list_agent_packs(root=root, map_id="demo_map")

    by_id = {pack.pack_id: pack for pack in packs}
    assert {"global_alice", "map_alice"} <= set(by_id)
    assert by_id["global_alice"].scope == "global"
    assert by_id["map_alice"].scope == "map"
    assert by_id["map_alice"].map_id == "demo_map"
    assert by_id["global_alice"].agents[0]["profile"]["name"] == "Alice"
    assert by_id["global_alice"].agents[0]["sprite"]["image_url"].endswith("characters/Alice.png")
    assert by_id["global_alice"].validation.ok is True


def test_find_agent_pack_prefers_selected_map_local_pack(tmp_path: Path) -> None:
    root = tmp_path / "agentsociety"
    global_package = _write_agent_pack(root, "shared_alice")
    map_package = _write_agent_pack(root, "shared_alice", map_id="demo_map")
    global_package.joinpath("agents", "alice", "profile.json").write_text(
        json.dumps({"name": "Global Alice"}),
        encoding="utf-8",
    )
    map_package.joinpath("agents", "alice", "profile.json").write_text(
        json.dumps({"name": "Map Alice"}),
        encoding="utf-8",
    )

    selected = agent_packs.find_agent_pack("shared_alice", root=root, map_id="demo_map")

    assert selected.scope == "map"
    assert selected.map_id == "demo_map"
    assert selected.agents[0]["profile"]["name"] == "Map Alice"


def test_agent_pack_validation_reports_missing_declared_assets(tmp_path: Path) -> None:
    package = _write_agent_pack(tmp_path / "agentsociety", "broken")
    (package / "agents" / "alice" / "profile.json").unlink()
    (package / "characters" / "Alice.png").unlink()

    validation = agent_packs.validate_agent_pack_path(package / "agent_pack.yaml")

    assert validation.ok is False
    assert any("profile_path missing" in message for message in validation.errors)
    assert any("sprite path missing" in message for message in validation.errors)


def test_agent_pack_rejects_paths_that_escape_package_root(tmp_path: Path) -> None:
    package = _write_agent_pack(tmp_path / "agentsociety", "unsafe")
    manifest = package / "agent_pack.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "profile_path: agents/alice/profile.json",
            "profile_path: ../outside/profile.json",
        ),
        encoding="utf-8",
    )

    validation = agent_packs.validate_agent_pack_path(manifest)

    assert validation.ok is False
    assert any("escapes package root" in message for message in validation.errors)


def test_export_and_import_agent_pack_zip_preserves_structure(tmp_path: Path) -> None:
    root = tmp_path / "agentsociety"
    package = _write_agent_pack(root, "alice_pack")
    pack = agent_packs.load_agent_pack_by_manifest(package / "agent_pack.yaml")
    zip_path = tmp_path / "alice_pack.zip"

    agent_packs.export_agent_pack(pack, zip_path)
    imported_root = tmp_path / "imported_agentsociety"
    imported = agent_packs.import_agent_pack_zip(zip_path, root=imported_root)

    assert imported.pack_id == "alice_pack"
    assert imported.validation.ok is True
    assert (imported_root / "custom" / "agent_packs" / "alice_pack" / "characters" / "Alice.png").exists()
    with ZipFile(zip_path) as archive:
        assert "agent_pack.yaml" in archive.namelist()
        assert "agents/alice/profile.json" in archive.namelist()
        assert "characters/Alice.png" in archive.namelist()


def test_import_agent_pack_zip_rejects_archives_without_manifest(tmp_path: Path) -> None:
    zip_path = tmp_path / "bad.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("profile.json", "{}")

    with pytest.raises(ValueError, match="agent_pack.yaml"):
        agent_packs.import_agent_pack_zip(zip_path, root=tmp_path / "agentsociety")
