import json
from pathlib import Path

from agentsociety2.backend.routers import replay
from agentsociety2.backend.services import map_packages


def _write_package(root: Path) -> Path:
    package = root / "custom" / "maps" / "demo_map"
    (package / "visuals" / "tiles").mkdir(parents=True)
    (package / "characters").mkdir()
    (package / "visuals" / "tiles" / "ground.png").write_bytes(b"png")
    (package / "visuals" / "preview.png").write_bytes(b"preview")
    (package / "characters" / "Resident.png").write_bytes(b"png")
    (package / "visuals" / "map.json").write_text(
        json.dumps(
            {
                "type": "map",
                "orientation": "orthogonal",
                "width": 2,
                "height": 2,
                "tilewidth": 32,
                "tileheight": 32,
                "tilesets": [
                    {
                        "firstgid": 1,
                        "name": "ground",
                        "image": "tiles/ground.png",
                        "tilewidth": 32,
                        "tileheight": 32,
                        "tilecount": 1,
                        "columns": 1,
                    }
                ],
                "layers": [
                    {"name": "Ground", "type": "tilelayer", "width": 2, "height": 2, "data": [1, 1, 1, 1]},
                    {"name": "Collisions", "type": "tilelayer", "width": 2, "height": 2, "data": [0, 0, 1, 0]},
                ],
            }
        ),
        encoding="utf-8",
    )
    (package / "map.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "map_id: demo_map",
                "display_name: Demo Map",
                "localized:",
                "  en:",
                "    display_name: Demo Map",
                "  zh:",
                "    display_name: 演示地图",
                "tiled_map_path: visuals/map.json",
                "tile_size: 32",
                "character_root: characters",
                "locations:",
                "- id: plaza",
                "  name: Plaza",
                "  aliases: [plaza]",
                "  localized:",
                "    en:",
                "      name: Plaza",
                "      aliases: [plaza]",
                "    zh:",
                "      name: 广场",
                "      aliases: [广场]",
                "  anchor_tile: {x: 0, y: 0}",
                "  interaction_ids: [wait]",
                "interactions:",
                "- id: wait",
                "  name: Wait",
                "  description: Wait in place.",
                "  localized:",
                "    en:",
                "      name: Wait",
                "      description: Wait in place.",
                "    zh:",
                "      name: 等待",
                "      description: 原地等待。",
                "  allowed_location_ids: [plaza]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return package


def test_map_package_validation_and_replay_metadata(tmp_path: Path) -> None:
    agentsociety_root = tmp_path / "agentsociety"
    workspace = agentsociety_root / "quick_experiments"
    package = _write_package(agentsociety_root)
    init_dir = workspace / "hypothesis_demo" / "experiment_1" / "init"
    init_dir.mkdir(parents=True)
    (init_dir / "init_config.json").write_text(
        json.dumps(
            {
                "env_modules": [
                    {
                        "module_type": "PixelTownSocialEnv",
                        "kwargs": {
                            "map_id": "demo_map",
                            "map_manifest_path": "custom/maps/demo_map/map.yaml",
                        },
                    }
                ],
                "agents": [],
            }
        ),
        encoding="utf-8",
    )

    package_info = map_packages.load_map_package_by_manifest(package / "map.yaml")
    assert package_info.validation.ok is True

    info = replay._map_info_response(str(workspace), "demo", "1")
    assert info.map_id == "demo_map"
    assert info.preview_url == (
        "/api/v1/replay/demo/1/map/preview?workspace_path=" + str(workspace)
    )
    assert info.tilesets[0].image_url.startswith("/api/v1/replay/demo/1/map/assets/0")
    assert info.character_sprites[0].name == "Resident"
    assert info.locations[0].id == "plaza"
    assert info.localized["zh"]["display_name"] == "演示地图"
    assert info.locations[0].localized["zh"]["name"] == "广场"
    assert info.interactions[0].localized["en"]["description"] == "Wait in place."

    summary = map_packages.map_package_summary(package_info, agentsociety_root)
    assert summary["localized"]["zh"]["display_name"] == "演示地图"


def test_map_package_rejects_resource_escape(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "agentsociety")
    map_json = package / "visuals" / "map.json"
    data = json.loads(map_json.read_text(encoding="utf-8"))
    data["tilesets"][0]["image"] = "../../../outside.png"
    map_json.write_text(json.dumps(data), encoding="utf-8")

    validation = map_packages.validate_manifest_path(package / "map.yaml")

    assert validation.ok is False
    assert any("escapes package root" in message for message in validation.errors)


def test_character_sprite_path_rejects_unsafe_character_root(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "agentsociety")
    manifest_path = package / "map.yaml"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace("character_root: characters", "character_root: ../outside"),
        encoding="utf-8",
    )

    package_info = map_packages.load_map_package_by_manifest(manifest_path)

    assert package_info.validation.ok is False
    assert any("escapes package root" in message for message in package_info.validation.errors)


def test_empty_character_root_warning_uses_role_image_language(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "agentsociety")
    (package / "characters" / "Resident.png").unlink()

    validation = map_packages.validate_manifest_path(package / "map.yaml")

    assert validation.ok is True
    assert any("role walking image PNGs" in message for message in validation.warnings)
    assert all("sprite" not in message.lower() for message in validation.warnings)


def test_map_package_without_character_root_is_valid_for_agent_pack_decoupling(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "agentsociety")
    (package / "characters" / "Resident.png").unlink()
    (package / "characters").rmdir()
    manifest = package / "map.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("character_root: characters\n", ""),
        encoding="utf-8",
    )

    validation = map_packages.validate_manifest_path(manifest)

    assert validation.ok is True
    assert all("character_root" not in message for message in validation.warnings)


def test_missing_map_id_falls_back_to_default(tmp_path: Path) -> None:
    agentsociety_root = tmp_path / "agentsociety"
    package = _write_package(agentsociety_root)
    default_package = package.rename(package.parent / "the_ville")
    manifest = json.loads((default_package / "visuals" / "map.json").read_text(encoding="utf-8"))
    (default_package / "visuals" / "map.json").write_text(json.dumps(manifest), encoding="utf-8")
    (default_package / "map.yaml").write_text(
        (default_package / "map.yaml").read_text(encoding="utf-8").replace("demo_map", "the_ville"),
        encoding="utf-8",
    )

    package_info = map_packages.load_map_package("missing_map", agentsociety_root)

    assert package_info.map_id == "the_ville"


def test_generated_map_packages_are_discovered_but_drafts_are_hidden(tmp_path: Path) -> None:
    agentsociety_root = tmp_path / "agentsociety"
    authored_package = _write_package(agentsociety_root)
    authored_package.rename(authored_package.parent / "the_ville")
    authored_manifest = authored_package.parent / "the_ville" / "map.yaml"
    authored_manifest.write_text(
        authored_manifest.read_text(encoding="utf-8").replace("demo_map", "the_ville"),
        encoding="utf-8",
    )

    legacy_root = agentsociety_root / "custom" / "generated_maps"
    legacy_package = _write_package(tmp_path / "legacy_source")
    legacy = legacy_root / "moon_tower"
    legacy.parent.mkdir(parents=True)
    legacy_package.rename(legacy)
    (legacy / "map.yaml").write_text(
        (legacy / "map.yaml").read_text(encoding="utf-8").replace("demo_map", "moon_tower"),
        encoding="utf-8",
    )
    draft_package = _write_package(tmp_path / "draft_source")
    draft = legacy_root / "_drafts" / "draft_123"
    draft.parent.mkdir(parents=True)
    draft_package.rename(draft)
    (draft / "map.yaml").write_text(
        (draft / "map.yaml").read_text(encoding="utf-8").replace("demo_map", "draft_123"),
        encoding="utf-8",
    )

    packages = map_packages.list_map_packages(agentsociety_root)

    by_id = {package.map_id: package for package in packages}
    assert set(by_id) == {"the_ville", "moon_tower"}
    assert "draft_123" not in by_id


def test_import_map_pack_zip_installs_into_custom_maps(tmp_path: Path) -> None:
    source_root = tmp_path / "source_agentsociety"
    package = _write_package(source_root)
    zip_path = tmp_path / "demo-map.zip"
    map_packages.export_map_pack(
        map_packages.load_map_package_by_manifest(package / "map.yaml"),
        zip_path,
    )

    target_root = tmp_path / "target_agentsociety"
    imported = map_packages.import_map_pack_zip(zip_path, root=target_root)

    assert imported.map_id == "demo_map"
    assert imported.validation.ok is True
    assert (target_root / "custom" / "maps" / "demo_map" / "map.yaml").exists()


def test_generated_map_validation_rejects_isolated_location_anchors(tmp_path: Path) -> None:
    package = tmp_path / "agentsociety" / "custom" / "generated_maps" / "isolated_world"
    (package / "visuals" / "tiles").mkdir(parents=True)
    (package / "characters").mkdir()
    (package / "visuals" / "tiles" / "ground.png").write_bytes(b"png")
    (package / "characters" / "Resident.png").write_bytes(b"png")
    collisions = [1] * 25
    collisions[1 * 5 + 1] = 0
    collisions[3 * 5 + 3] = 0
    (package / "visuals" / "map.json").write_text(
        json.dumps(
            {
                "type": "map",
                "orientation": "orthogonal",
                "width": 5,
                "height": 5,
                "tilewidth": 32,
                "tileheight": 32,
                "tilesets": [
                    {
                        "firstgid": 1,
                        "name": "ground",
                        "image": "tiles/ground.png",
                        "tilewidth": 32,
                        "tileheight": 32,
                        "tilecount": 1,
                        "columns": 1,
                    }
                ],
                "layers": [
                    {"name": "Ground", "type": "tilelayer", "width": 5, "height": 5, "data": [1] * 25},
                    {"name": "Collisions", "type": "tilelayer", "width": 5, "height": 5, "data": collisions},
                ],
            }
        ),
        encoding="utf-8",
    )
    (package / "map.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "map_id: isolated_world",
                "display_name: Isolated World",
                "tiled_map_path: visuals/map.json",
                "tile_size: 32",
                "character_root: characters",
                "default_location_order: [alpha, beta]",
                "locations:",
                "- id: alpha",
                "  name: Alpha",
                "  anchor_tile: {x: 1, y: 1}",
                "  interaction_ids: [wait_alpha]",
                "- id: beta",
                "  name: Beta",
                "  anchor_tile: {x: 3, y: 3}",
                "  interaction_ids: [wait_beta]",
                "interactions:",
                "- id: wait_alpha",
                "  name: Wait Alpha",
                "  allowed_location_ids: [alpha]",
                "- id: wait_beta",
                "  name: Wait Beta",
                "  allowed_location_ids: [beta]",
                "",
            ]
        ),
        encoding="utf-8",
    )

    validation = map_packages.validate_manifest_path(package / "map.yaml")

    assert validation.ok is False
    assert any("generated route alpha->beta is not reachable" in message for message in validation.errors)
