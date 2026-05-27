import json
from functools import partial
from pathlib import Path

import anyio
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from agentsociety2.backend.routers import god_setup, map_studio
from agentsociety2.backend.routers.map_studio import (
    CollisionEdit,
    MapDraftCreateRequest,
    MapDraftPatchRequest,
    PublishDraftRequest,
)
from agentsociety2.backend.services import map_generation


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
        "IMAGE_GEN_API_KEY",
        "IMAGE_GEN_API_BASE",
        "IMAGE_GEN_MODEL_NAME",
        "IMAGE_GEN_PROVIDER",
    ):
        monkeypatch.delenv(key, raising=False)


def _write_default_map_root(tmp_path: Path) -> None:
    maps_root = tmp_path / "agentsociety" / "custom" / "maps" / "the_ville"
    (maps_root / "visuals").mkdir(parents=True)
    (maps_root / "visuals" / "map.json").write_text(
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
    (maps_root / "map.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "map_id: the_ville",
                "display_name: The Ville",
                "tiled_map_path: visuals/map.json",
                "tile_size: 32",
                "locations:",
                "- id: plaza",
                "  name: Plaza",
                "  anchor_tile: {x: 1, y: 1}",
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


def _map_image_bytes() -> bytes:
    image = Image.new("RGB", (896, 640), (22, 28, 38))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 896, 640), fill=(28, 38, 52))
    draw.ellipse((80, 80, 380, 320), fill=(86, 94, 110))
    draw.rectangle((404, 70, 486, 360), fill=(78, 184, 206))
    draw.rectangle((0, 300, 896, 350), fill=(188, 198, 210))
    draw.rectangle((420, 0, 470, 640), fill=(188, 198, 210))
    return map_generation.encode_png_bytes(image)


def test_map_studio_draft_patch_publish_and_setup_visibility(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    _write_default_map_root(tmp_path)

    async def fake_image(**_kwargs):
        return _map_image_bytes()

    monkeypatch.setattr(map_generation, "generate_map_image", fake_image)

    created = anyio.run(
        map_studio.create_draft,
        MapDraftCreateRequest(prompt="Moon base with a tall Cybertron tower"),
    )

    assert created.status == "ready"
    assert created.validation.ok is True
    assert created.preview_url.endswith(f"/drafts/{created.draft_id}/preview.png")
    draft_path = tmp_path / "agentsociety" / "custom" / "generated_maps" / "_drafts" / created.draft_id
    assert (draft_path / "map.yaml").exists()
    tiled = json.loads((draft_path / "visuals" / "map.json").read_text(encoding="utf-8"))
    assert tiled["width"] == 140
    assert tiled["height"] == 100
    assert tiled["layers"][1]["name"] == "Collisions"

    first_location = created.locations[0].model_copy(deep=True)
    first_location.anchor_tile = {"x": 5, "y": 5}
    patched = anyio.run(
        map_studio.patch_draft,
        created.draft_id,
        MapDraftPatchRequest(
            locations=[first_location],
            collision_edits=[CollisionEdit(x=5, y=5, blocked=False)],
        ),
    )

    assert patched.locations[0].anchor_tile == {"x": 5, "y": 5}
    assert patched.validation.ok is True

    published = anyio.run(
        map_studio.publish_draft,
        created.draft_id,
        PublishDraftRequest(map_id="moon_tower"),
    )

    assert published.map_id == "moon_tower"
    assert Path(published.package_path).name == "moon_tower"
    status = anyio.run(god_setup.setup_status)
    by_id = {item["map_id"]: item for item in status["maps"]}
    assert by_id["moon_tower"]["validation_status"]["ok"] is True
    assert by_id["moon_tower"]["display_name"] == "moon_tower"

    manifest_path = Path(published.manifest_path)
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert manifest["display_name"] == "moon_tower"
    assert manifest["localized"]["zh"]["display_name"] == "moon_tower"
    assert manifest["localized"]["en"]["display_name"] == "moon_tower"


def test_map_studio_uses_default_style_reference_when_no_upload(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    monkeypatch.setenv("IMAGE_GEN_API_KEY", "sk-test")
    _write_default_map_root(tmp_path)
    reference_path = tmp_path / "agentsociety" / "custom" / "maps" / "pku" / "visuals" / "preview.png"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_bytes(_map_image_bytes())
    captured: dict[str, object] = {}

    async def fake_image(**kwargs):
        captured.update(kwargs)
        return _map_image_bytes()

    monkeypatch.setattr(map_generation, "generate_map_image", fake_image)

    created = anyio.run(
        map_studio.create_draft,
        MapDraftCreateRequest(prompt="Quiet university campus"),
    )

    assert captured["reference_bytes"] == reference_path.read_bytes()
    assert captured["reference_filename"] == "preview.png"
    assert created.style_reference_used == "god_default"
    assert len(created.collision_data) == map_generation.MAP_WIDTH * map_generation.MAP_HEIGHT


def test_map_studio_upload_reference_takes_precedence(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    _write_default_map_root(tmp_path)
    default_path = tmp_path / "agentsociety" / "custom" / "maps" / "pku" / "visuals" / "preview.png"
    default_path.parent.mkdir(parents=True, exist_ok=True)
    default_path.write_bytes(b"default-reference")
    uploaded = _map_image_bytes()
    captured: dict[str, object] = {}

    async def fake_image(**kwargs):
        captured.update(kwargs)
        return _map_image_bytes()

    monkeypatch.setattr(map_generation, "generate_map_image", fake_image)

    state = anyio.run(
        partial(
            map_generation.create_draft,
            root=tmp_path / "agentsociety",
            prompt="Uploaded reference world",
            image_config={"IMAGE_GEN_API_KEY": "sk-test"},
            reference_bytes=uploaded,
            reference_filename="custom.png",
            reference_content_type="image/png",
        )
    )

    assert captured["reference_bytes"] == uploaded
    assert captured["reference_filename"] == "custom.png"
    assert state["style_reference_used"] == "uploaded"


def test_map_studio_reports_local_placeholder_without_image_key(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    _write_default_map_root(tmp_path)
    reference_path = tmp_path / "agentsociety" / "custom" / "maps" / "pku" / "visuals" / "preview.png"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_bytes(_map_image_bytes())

    created = anyio.run(
        map_studio.create_draft,
        MapDraftCreateRequest(prompt="Quiet university campus"),
    )

    assert created.style_reference_used == "local_placeholder"
    assert any("local placeholder" in warning for warning in created.warnings)


def test_map_studio_saves_image_config_from_create_after_success(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    _write_default_map_root(tmp_path)
    captured: dict[str, object] = {}

    async def fake_image(**kwargs):
        captured.update(kwargs)
        return _map_image_bytes()

    monkeypatch.setattr(map_generation, "generate_map_image", fake_image)

    created = anyio.run(
        map_studio.create_draft,
        MapDraftCreateRequest(
            prompt="Moon base with paths",
            image_config={
                "IMAGE_GEN_API_KEY": "test-map-image-key",
                "IMAGE_GEN_API_BASE": "https://api.openai.com/v1",
                "IMAGE_GEN_MODEL_NAME": "gpt-image-1.5",
                "IMAGE_GEN_PROVIDER": "openai",
            },
        ),
    )

    assert created.style_reference_used != "local_placeholder"
    assert captured["image_config"]["IMAGE_GEN_API_KEY"] == "test-map-image-key"
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "IMAGE_GEN_API_KEY=test-map-image-key" in env_text
    assert "IMAGE_GEN_MODEL_NAME=gpt-image-1.5" in env_text


def test_map_studio_saves_image_config_endpoint_redacts_status(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    _write_default_map_root(tmp_path)

    status = anyio.run(
        map_studio.save_image_config,
        map_studio.MapImageConfigRequest(
            image_config={
                "image_api_key": "test-map-image-key",
                "image_api_base": "https://api.openai.com/v1",
                "image_model": "gpt-image-1.5",
                "image_provider": "openai",
            },
        ),
    )

    assert status["image_model_config"]["IMAGE_GEN_API_KEY"]["configured"] is True
    assert status["image_model_config"]["IMAGE_GEN_API_KEY"]["value"].endswith("key")
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "IMAGE_GEN_API_KEY=test-map-image-key" in env_text
    assert "IMAGE_GEN_API_BASE=https://api.openai.com/v1" in env_text


def test_map_studio_patch_returns_updated_collision_data(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    _write_default_map_root(tmp_path)

    async def fake_image(**_kwargs):
        return _map_image_bytes()

    monkeypatch.setattr(map_generation, "generate_map_image", fake_image)
    created = anyio.run(
        map_studio.create_draft,
        MapDraftCreateRequest(prompt="Moon base with paths"),
    )

    patched = anyio.run(
        map_studio.patch_draft,
        created.draft_id,
        MapDraftPatchRequest(collision_edits=[CollisionEdit(x=12, y=9, blocked=True)]),
    )

    assert patched.collision_data[9 * map_generation.MAP_WIDTH + 12] == 1

    patched_again = anyio.run(
        map_studio.patch_draft,
        created.draft_id,
        MapDraftPatchRequest(collision_edits=[CollisionEdit(x=12, y=9, blocked=False)]),
    )

    assert patched_again.collision_data[9 * map_generation.MAP_WIDTH + 12] == 0


def test_map_studio_regenerate_preserves_calibration(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    _write_default_map_root(tmp_path)

    async def fake_image(**_kwargs):
        return _map_image_bytes()

    monkeypatch.setattr(map_generation, "generate_map_image", fake_image)
    created = anyio.run(
        map_studio.create_draft,
        MapDraftCreateRequest(prompt="Moon base with paths"),
    )
    first_location = created.locations[0].model_copy(deep=True)
    first_location.anchor_tile = {"x": 12, "y": 9}
    patched = anyio.run(
        map_studio.patch_draft,
        created.draft_id,
        MapDraftPatchRequest(
            locations=[first_location],
            collision_edits=[CollisionEdit(x=12, y=9, blocked=True)],
        ),
    )

    regenerated = anyio.run(map_studio.regenerate_image, created.draft_id)

    assert regenerated.locations[0].anchor_tile == patched.locations[0].anchor_tile
    assert regenerated.collision_data[9 * map_generation.MAP_WIDTH + 12] == 1


def test_map_studio_regenerate_constrains_location_asset_paths(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    _write_default_map_root(tmp_path)

    async def fake_image(**_kwargs):
        return _map_image_bytes()

    monkeypatch.setattr(map_generation, "generate_map_image", fake_image)
    created = anyio.run(
        map_studio.create_draft,
        MapDraftCreateRequest(prompt="Moon base with paths"),
    )
    first_location = created.locations[0].model_copy(deep=True)
    first_location.id = "../escape"

    anyio.run(
        map_studio.patch_draft,
        created.draft_id,
        MapDraftPatchRequest(locations=[first_location]),
    )
    anyio.run(map_studio.regenerate_image, created.draft_id)

    draft_path = tmp_path / "agentsociety" / "custom" / "generated_maps" / "_drafts" / created.draft_id
    assert not (draft_path / "escape.png").exists()
    assert (draft_path / "location_assets" / "escape.png").exists()


def test_map_studio_create_route_returns_style_and_collision_fields(monkeypatch, tmp_path):
    _configure_tmp_god(monkeypatch, tmp_path)
    _write_default_map_root(tmp_path)

    async def fake_image(**_kwargs):
        return _map_image_bytes()

    monkeypatch.setattr(map_generation, "generate_map_image", fake_image)
    app = FastAPI()
    app.include_router(map_studio.router)

    response = TestClient(app).post(
        "/api/v1/god/map-studio/drafts",
        json={"prompt": "Quiet university campus"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["style_reference_used"] == "local_placeholder"
    assert len(payload["collision_data"]) == map_generation.MAP_WIDTH * map_generation.MAP_HEIGHT
