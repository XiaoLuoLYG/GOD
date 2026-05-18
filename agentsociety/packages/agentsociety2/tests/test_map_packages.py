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
                "tiled_map_path: visuals/map.json",
                "tile_size: 32",
                "character_root: characters",
                "locations:",
                "- id: plaza",
                "  name: Plaza",
                "  aliases: [plaza]",
                "  anchor_tile: {x: 0, y: 0}",
                "  interaction_ids: [wait]",
                "interactions:",
                "- id: wait",
                "  name: Wait",
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


def test_map_package_rejects_resource_escape(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "agentsociety")
    map_json = package / "visuals" / "map.json"
    data = json.loads(map_json.read_text(encoding="utf-8"))
    data["tilesets"][0]["image"] = "../../../outside.png"
    map_json.write_text(json.dumps(data), encoding="utf-8")

    validation = map_packages.validate_manifest_path(package / "map.yaml")

    assert validation.ok is False
    assert any("escapes package root" in message for message in validation.errors)


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
