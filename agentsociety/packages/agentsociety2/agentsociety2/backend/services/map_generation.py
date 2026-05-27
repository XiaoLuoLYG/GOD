"""Map Studio draft generation and publish helpers."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any
import uuid

import aiohttp
from fastapi import HTTPException
from PIL import Image, ImageDraw, UnidentifiedImageError
import yaml

from agentsociety2.backend.services.map_packages import (
    generated_maps_root,
    safe_resolve,
    validate_manifest_path,
)


MAP_WIDTH = 140
MAP_HEIGHT = 100
TILE_SIZE = 32
FULL_MAP_SIZE = (MAP_WIDTH * TILE_SIZE, MAP_HEIGHT * TILE_SIZE)
PREVIEW_SIZE = (896, 640)
IMAGE_MODEL_DEFAULTS = {
    "IMAGE_GEN_API_BASE": "https://api.openai.com/v1",
    "IMAGE_GEN_MODEL_NAME": "gpt-image-1.5",
    "IMAGE_GEN_PROVIDER": "openai",
}
DEFAULT_STYLE_REFERENCE_CANDIDATES = (
    "custom/maps/pku/visuals/preview.png",
    "custom/maps/pku/visuals/map_assets/pku_generated/pku_full_map_tileset.png",
    "custom/maps/the_ville/visuals/map_assets/cute_rpg_word_VXAce/tilesets/CuteRPG_Field_B.png",
)


def encode_png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _default_style_reference(root: Path) -> tuple[bytes | None, str, str, str]:
    for relative in DEFAULT_STYLE_REFERENCE_CANDIDATES:
        try:
            path = safe_resolve(root, relative, root)
        except ValueError:
            continue
        if path.exists() and path.is_file():
            return path.read_bytes(), path.name, "image/png", "god_default"
    return None, "reference.png", "image/png", "none"


def _resolve_style_reference(
    root: Path,
    *,
    reference_bytes: bytes | None,
    reference_filename: str,
    reference_content_type: str,
) -> tuple[bytes | None, str, str, str]:
    if reference_bytes:
        return (
            reference_bytes,
            Path(reference_filename or "reference.png").name,
            reference_content_type or "image/png",
            "uploaded",
        )
    return _default_style_reference(root)


def _collision_data_from_package(package_path: Path) -> list[int]:
    map_path = package_path / "visuals" / "map.json"
    try:
        tiled_map = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    for layer in tiled_map.get("layers", []) or []:
        if layer.get("name") == "Collisions" and isinstance(layer.get("data"), list):
            return [int(value or 0) for value in layer["data"]]
    return []


def _write_collision_data(package_path: Path, collision_data: list[int]) -> None:
    map_path = package_path / "visuals" / "map.json"
    tiled_map = json.loads(map_path.read_text(encoding="utf-8"))
    for layer in tiled_map.get("layers", []) or []:
        if layer.get("name") == "Collisions" and isinstance(layer.get("data"), list):
            layer["data"] = [int(value or 0) for value in collision_data]
            break
    map_path.write_text(json.dumps(tiled_map, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sanitize_map_id(value: str, fallback: str = "generated_map") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_\-\u4e00-\u9fff]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_-")
    return text[:48] or f"{fallback}_{uuid.uuid4().hex[:8]}"


def drafts_root(root: Path) -> Path:
    return generated_maps_root(root) / "_drafts"


def draft_package_path(root: Path, draft_id: str) -> Path:
    safe_id = Path(draft_id).name
    return safe_resolve(drafts_root(root), safe_id, drafts_root(root))


def _draft_meta_path(package_path: Path) -> Path:
    return package_path / "draft.json"


def _image_config_value(config: dict[str, str] | None, key: str) -> str:
    if config and config.get(key):
        return str(config[key]).strip()
    if os.getenv(key):
        return str(os.environ[key]).strip()
    return IMAGE_MODEL_DEFAULTS.get(key, "")


def _prompt_title(prompt: str) -> tuple[str, str]:
    compact = " ".join(str(prompt or "").split())
    if not compact:
        return "Generated Pixel World", "生成像素世界"
    words = compact[:64]
    return words[:1].upper() + words[1:], f"{words} 像素地图"


def _is_moon_prompt(prompt: str) -> bool:
    text = str(prompt or "").lower()
    return any(token in text for token in ("moon", "lunar", "cyber", "tower", "赛博", "月球", "高塔"))


def _semantic_locations(prompt: str) -> list[dict[str, Any]]:
    if _is_moon_prompt(prompt):
        raw = [
            ("central_tower", "Central Tower", "中央高塔", "landmark", (70, 28), (65, 12, 10, 22)),
            ("landing_pad", "Landing Pad", "登陆平台", "gate", (24, 50), (15, 43, 18, 14)),
            ("habitat_dome", "Habitat Dome", "居住穹顶", "home", (46, 68), (38, 60, 18, 16)),
            ("power_core", "Power Core", "能源核心", "workshop", (92, 58), (85, 49, 16, 18)),
            ("market_dome", "Market Dome", "集市穹顶", "market", (71, 78), (62, 72, 19, 12)),
            ("observatory", "Observatory", "观测站", "library", (113, 36), (105, 29, 17, 14)),
            ("rover_garage", "Rover Garage", "月面车库", "workshop", (32, 24), (25, 17, 16, 13)),
        ]
    else:
        raw = [
            ("central_plaza", "Central Plaza", "中心广场", "public", (70, 50), (61, 43, 18, 14)),
            ("workshop", "Workshop", "工坊", "workshop", (31, 30), (24, 23, 15, 14)),
            ("cafe", "Cafe", "咖啡馆", "market", (48, 70), (40, 64, 16, 12)),
            ("garden", "Garden", "花园", "park", (96, 72), (88, 65, 18, 14)),
            ("archive", "Archive", "档案馆", "library", (108, 31), (100, 24, 16, 14)),
            ("clinic", "Clinic", "诊所", "clinic", (73, 23), (66, 16, 15, 14)),
        ]

    locations: list[dict[str, Any]] = []
    for location_id, name_en, name_zh, scene_type, anchor, bounds in raw:
        interaction_id = f"{location_id}_visit"
        locations.append(
            {
                "id": location_id,
                "name": name_zh,
                "aliases": [location_id.replace("_", " "), name_en, name_zh],
                "localized": {
                    "en": {"name": name_en, "aliases": [location_id.replace("_", " "), name_en]},
                    "zh": {"name": name_zh, "aliases": [name_zh]},
                },
                "anchor_tile": {"x": anchor[0], "y": anchor[1]},
                "scene_type": scene_type,
                "bounds": {"x": bounds[0], "y": bounds[1], "w": bounds[2], "h": bounds[3]},
                "interaction_ids": [interaction_id],
                "visual_asset": f"location_assets/{location_id}.png",
            }
        )
    return locations


def _semantic_interactions(locations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    interactions: list[dict[str, Any]] = []
    for location in locations:
        location_id = str(location["id"])
        name_zh = str(location["localized"]["zh"]["name"])
        name_en = str(location["localized"]["en"]["name"])
        interaction_id = f"{location_id}_visit"
        interactions.append(
            {
                "id": interaction_id,
                "name": f"在{name_zh}活动",
                "description": f"围绕{name_zh}进行观察、交流或日常任务。",
                "localized": {
                    "en": {
                        "name": f"Visit {name_en}",
                        "description": f"Observe, talk, or handle daily tasks around {name_en}.",
                    },
                    "zh": {
                        "name": f"在{name_zh}活动",
                        "description": f"围绕{name_zh}进行观察、交流或日常任务。",
                    },
                },
                "allowed_location_ids": [location_id],
                "effects": {
                    "action": f"{{agent_name}} 在{name_zh}活动",
                    "status": "探索中",
                    "emotion": "好奇",
                    "latest_event": f"{{agent_name}} 抵达{name_zh}。",
                },
            }
        )
    return interactions


def _collision_data(locations: list[dict[str, Any]]) -> list[int]:
    data = [0] * (MAP_WIDTH * MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            if x in (0, MAP_WIDTH - 1) or y in (0, MAP_HEIGHT - 1):
                data[y * MAP_WIDTH + x] = 1
    for location in locations:
        bounds = location.get("bounds") or {}
        anchor = location.get("anchor_tile") or {}
        try:
            bx, by, bw, bh = int(bounds["x"]), int(bounds["y"]), int(bounds["w"]), int(bounds["h"])
            ax, ay = int(anchor["x"]), int(anchor["y"])
        except Exception:
            continue
        for y in range(max(1, by), min(MAP_HEIGHT - 1, by + bh)):
            for x in range(max(1, bx), min(MAP_WIDTH - 1, bx + bw)):
                if abs(x - ax) + abs(y - ay) > 2:
                    data[y * MAP_WIDTH + x] = 1
        for x, y in ((ax, ay), (ax + 1, ay), (ax - 1, ay), (ax, ay + 1), (ax, ay - 1)):
            if 0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT:
                data[y * MAP_WIDTH + x] = 0
    return data


def _apply_collision_edits(data: list[int], edits: list[dict[str, Any]]) -> list[int]:
    next_data = list(data)
    for edit in edits:
        try:
            x = int(edit["x"])
            y = int(edit["y"])
            blocked = bool(edit["blocked"])
        except Exception:
            continue
        if 0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT:
            next_data[y * MAP_WIDTH + x] = 1 if blocked else 0
    return next_data


def _open_image(raw: bytes) -> Image.Image:
    try:
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=502, detail=f"Image model returned unreadable image data: {exc}") from exc


def _placeholder_map(prompt: str) -> bytes:
    image = Image.new("RGB", PREVIEW_SIZE, (34, 42, 58))
    draw = ImageDraw.Draw(image)
    moon = _is_moon_prompt(prompt)
    ground = (48, 55, 72) if moon else (74, 118, 92)
    road = (180, 188, 196) if moon else (202, 184, 132)
    accent = (66, 206, 224) if moon else (222, 96, 76)
    draw.rectangle((0, 0, PREVIEW_SIZE[0], PREVIEW_SIZE[1]), fill=ground)
    for x in range(0, PREVIEW_SIZE[0], 64):
        draw.line((x, 0, x + 200, PREVIEW_SIZE[1]), fill=(255, 255, 255, 18), width=1)
    draw.rectangle((0, 294, PREVIEW_SIZE[0], 346), fill=road)
    draw.rectangle((424, 0, 474, PREVIEW_SIZE[1]), fill=road)
    draw.ellipse((66, 82, 370, 312), fill=(92, 99, 114) if moon else (64, 132, 86))
    draw.rectangle((405, 64, 493, 366), fill=accent)
    draw.polygon([(449, 22), (389, 96), (508, 96)], fill=(184, 230, 245) if moon else (245, 196, 96))
    for left, top, color in (
        (134, 414, (118, 132, 160)),
        (252, 142, (92, 134, 170)),
        (600, 390, (94, 160, 130)),
        (676, 168, (130, 118, 168)),
    ):
        draw.rounded_rectangle((left, top, left + 112, top + 82), radius=10, fill=color)
    return encode_png_bytes(image)


async def _download_image_url(url: str, api_key: str) -> bytes:
    timeout = aiohttp.ClientTimeout(total=float(os.getenv("GOD_IMAGE_DOWNLOAD_TIMEOUT", "90")))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            data = await response.read()
            if response.status >= 400:
                raise HTTPException(status_code=502, detail=f"Image download failed: {data[:400]!r}")
            return data


async def _request_openai_image(
    *,
    api_key: str,
    api_base: str,
    model: str,
    prompt: str,
    reference_bytes: bytes | None = None,
    reference_filename: str = "reference.png",
    reference_content_type: str = "image/png",
) -> bytes:
    base = api_base.rstrip("/") or IMAGE_MODEL_DEFAULTS["IMAGE_GEN_API_BASE"]
    timeout = aiohttp.ClientTimeout(total=float(os.getenv("GOD_MAP_STUDIO_IMAGE_TIMEOUT", "240")))
    if reference_bytes:
        url = base if base.endswith("/images/edits") else f"{base}/images/edits"
        form = aiohttp.FormData()
        form.add_field("model", model)
        form.add_field("prompt", prompt)
        form.add_field("size", os.getenv("GOD_MAP_STUDIO_IMAGE_SIZE", "1536x1024"))
        form.add_field("n", "1")
        form.add_field("image", reference_bytes, filename=Path(reference_filename).name, content_type=reference_content_type)
        payload_data: Any = form
        headers = {"authorization": f"Bearer {api_key}"}
    else:
        url = base if base.endswith("/images/generations") else f"{base}/images/generations"
        payload_data = {
            "model": model,
            "prompt": prompt,
            "size": os.getenv("GOD_MAP_STUDIO_IMAGE_SIZE", "1536x1024"),
            "n": 1,
            "output_format": "png",
        }
        headers = {"authorization": f"Bearer {api_key}", "content-type": "application/json"}
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            post_kwargs = {"headers": headers}
            if reference_bytes:
                post_kwargs["data"] = payload_data
            else:
                post_kwargs["json"] = payload_data
            async with session.post(url, **post_kwargs) as response:
                text = await response.text()
                if response.status >= 400:
                    sanitized = re.sub(r"sk-[A-Za-z0-9_\-*.]{8,}", "[redacted-api-key]", text)
                    raise HTTPException(status_code=502, detail=f"Image model request failed: {sanitized[:800]}")
                payload = json.loads(text)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Image model request timed out") from exc
    except aiohttp.ClientError as exc:
        raise HTTPException(status_code=502, detail=f"Image model request failed: {exc}") from exc

    item = (payload.get("data") or [{}])[0]
    if isinstance(item, dict) and item.get("b64_json"):
        return base64.b64decode(str(item["b64_json"]))
    if isinstance(item, dict) and item.get("url"):
        return await _download_image_url(str(item["url"]), api_key)
    raise HTTPException(status_code=502, detail="Image model response did not include image data")


async def generate_map_image(
    *,
    prompt: str,
    image_config: dict[str, str] | None = None,
    reference_bytes: bytes | None = None,
    reference_filename: str = "reference.png",
    reference_content_type: str = "image/png",
) -> bytes:
    api_key = _image_config_value(image_config, "IMAGE_GEN_API_KEY")
    if not api_key:
        return _placeholder_map(prompt)
    provider = _image_config_value(image_config, "IMAGE_GEN_PROVIDER") or "openai"
    if provider.lower() != "openai":
        raise HTTPException(status_code=400, detail=f"Unsupported IMAGE_GEN_PROVIDER for Map Studio: {provider}")
    return await _request_openai_image(
        api_key=api_key,
        api_base=_image_config_value(image_config, "IMAGE_GEN_API_BASE"),
        model=_image_config_value(image_config, "IMAGE_GEN_MODEL_NAME"),
        prompt=_map_image_prompt(prompt),
        reference_bytes=reference_bytes,
        reference_filename=reference_filename,
        reference_content_type=reference_content_type,
    )


def _map_image_prompt(prompt: str) -> str:
    return (
        "Create one complete GOD PixelReplay-compatible cute pixel-art RPG map. "
        "Use an orthogonal top-down view compatible with 32x32 readable tiles. "
        "Match the visual language of PKU/The Ville-style GOD maps: soft cute RPG palette, small readable landmarks, clear paths, plazas, buildings, and walkable public spaces. "
        "Keep the whole world visible in one coherent map image, not a poster or cinematic illustration. "
        "No labels, no text, no UI, no border, no perspective camera, no floating decorative overlays. "
        "User world prompt: "
        f"{str(prompt or '').strip()[:1200]}"
    )


def _prepare_full_map(raw: bytes) -> Image.Image:
    image = _open_image(raw)
    return image.resize(FULL_MAP_SIZE, Image.Resampling.NEAREST)


def _location_asset_filename(location: dict[str, Any], index: int) -> str:
    raw_name = Path(str(location.get("id") or "")).name
    safe_name = raw_name.replace("/", "").replace("\\", "").strip()
    if not safe_name:
        safe_name = f"location_{index + 1}"
    return f"{safe_name}.png"


def _write_location_assets(package_path: Path, full_map: Image.Image, locations: list[dict[str, Any]]) -> None:
    asset_root = package_path / "location_assets"
    asset_root.mkdir(parents=True, exist_ok=True)
    for index, location in enumerate(locations):
        bounds = location.get("bounds") or {}
        try:
            x = int(bounds["x"]) * TILE_SIZE
            y = int(bounds["y"]) * TILE_SIZE
            w = max(1, int(bounds["w"])) * TILE_SIZE
            h = max(1, int(bounds["h"])) * TILE_SIZE
        except Exception:
            anchor = location.get("anchor_tile") or {}
            x = max(0, (int(anchor.get("x", 1)) - 2) * TILE_SIZE)
            y = max(0, (int(anchor.get("y", 1)) - 2) * TILE_SIZE)
            w = h = TILE_SIZE * 5
        crop = full_map.crop((x, y, min(FULL_MAP_SIZE[0], x + w), min(FULL_MAP_SIZE[1], y + h)))
        crop.thumbnail((160, 160), Image.Resampling.LANCZOS)
        asset_path = safe_resolve(asset_root, _location_asset_filename(location, index), asset_root)
        asset_path.write_bytes(encode_png_bytes(crop.convert("RGBA")))


def _manifest(prompt: str, map_id: str, locations: list[dict[str, Any]]) -> dict[str, Any]:
    title_en, title_zh = _prompt_title(prompt)
    interactions = _semantic_interactions(locations)
    return {
        "schema_version": 1,
        "map_id": map_id,
        "display_name": title_zh,
        "localized": {
            "en": {"display_name": title_en},
            "zh": {"display_name": title_zh},
        },
        "tiled_map_path": "visuals/map.json",
        "tile_size": TILE_SIZE,
        "character_root": "characters",
        "default_location_order": [str(location["id"]) for location in locations],
        "spawn_points": [
            {"id": f"spawn_{index + 1}", "location_id": str(location["id"])}
            for index, location in enumerate(locations[:6])
        ],
        "locations": locations,
        "interactions": interactions,
    }


def _tiled_map(collision_data: list[int]) -> dict[str, Any]:
    ground = [index + 1 for index in range(MAP_WIDTH * MAP_HEIGHT)]
    return {
        "type": "map",
        "version": "1.10",
        "tiledversion": "1.10.2",
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "width": MAP_WIDTH,
        "height": MAP_HEIGHT,
        "tilewidth": TILE_SIZE,
        "tileheight": TILE_SIZE,
        "infinite": False,
        "tilesets": [
            {
                "firstgid": 1,
                "name": "Generated_Full_Map",
                "image": "map_assets/generated_full_map_tileset.png",
                "imagewidth": FULL_MAP_SIZE[0],
                "imageheight": FULL_MAP_SIZE[1],
                "tilewidth": TILE_SIZE,
                "tileheight": TILE_SIZE,
                "tilecount": MAP_WIDTH * MAP_HEIGHT,
                "columns": MAP_WIDTH,
                "margin": 0,
                "spacing": 0,
            }
        ],
        "layers": [
            {
                "id": 1,
                "name": "Ground",
                "type": "tilelayer",
                "visible": True,
                "opacity": 1,
                "x": 0,
                "y": 0,
                "width": MAP_WIDTH,
                "height": MAP_HEIGHT,
                "data": ground,
            },
            {
                "id": 2,
                "name": "Collisions",
                "type": "tilelayer",
                "visible": True,
                "opacity": 1,
                "x": 0,
                "y": 0,
                "width": MAP_WIDTH,
                "height": MAP_HEIGHT,
                "data": collision_data,
            },
        ],
    }


def _write_package(package_path: Path, *, prompt: str, map_id: str, raw_image: bytes, warnings: list[str]) -> dict[str, Any]:
    if package_path.exists():
        shutil.rmtree(package_path)
    (package_path / "visuals" / "map_assets").mkdir(parents=True, exist_ok=True)
    (package_path / "characters").mkdir(parents=True, exist_ok=True)

    full_map = _prepare_full_map(raw_image)
    (package_path / "visuals" / "map_assets" / "generated_full_map_tileset.png").write_bytes(
        encode_png_bytes(full_map)
    )
    preview = full_map.copy()
    preview.thumbnail(PREVIEW_SIZE, Image.Resampling.LANCZOS)
    (package_path / "visuals" / "preview.png").write_bytes(encode_png_bytes(preview.convert("RGB")))

    locations = _semantic_locations(prompt)
    _write_location_assets(package_path, full_map, locations)
    manifest = _manifest(prompt, map_id, locations)
    collision_data = _collision_data(locations)
    (package_path / "visuals" / "map.json").write_text(
        json.dumps(_tiled_map(collision_data), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (package_path / "map.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (package_path / "README.md").write_text(
        f"# {manifest['display_name']}\n\nGenerated by GOD Map Studio from prompt:\n\n> {prompt}\n",
        encoding="utf-8",
    )
    (package_path / "ATTRIBUTION.md").write_text(
        "# Attribution\n\nGenerated locally by GOD Map Studio using the configured image model or local placeholder fallback.\n",
        encoding="utf-8",
    )
    return _state_from_package(package_path, prompt=prompt, warnings=warnings)


async def create_draft(
    *,
    root: Path,
    prompt: str,
    image_config: dict[str, str] | None = None,
    reference_bytes: bytes | None = None,
    reference_filename: str = "reference.png",
    reference_content_type: str = "image/png",
) -> dict[str, Any]:
    drafts_root(root).mkdir(parents=True, exist_ok=True)
    draft_id = f"draft_{uuid.uuid4().hex[:12]}"
    map_id = sanitize_map_id(prompt, "generated_map")
    warnings: list[str] = []
    uses_local_placeholder = not _image_config_value(image_config, "IMAGE_GEN_API_KEY")
    if uses_local_placeholder:
        warnings.append("IMAGE_GEN_API_KEY is not configured; Map Studio used a local placeholder image.")
    resolved_reference_bytes, resolved_reference_filename, resolved_reference_content_type, style_reference_used = (
        _resolve_style_reference(
            root,
            reference_bytes=reference_bytes,
            reference_filename=reference_filename,
            reference_content_type=reference_content_type,
        )
    )
    raw_image = await generate_map_image(
        prompt=prompt,
        image_config=image_config,
        reference_bytes=resolved_reference_bytes,
        reference_filename=resolved_reference_filename,
        reference_content_type=resolved_reference_content_type,
    )
    state = _write_package(
        draft_package_path(root, draft_id),
        prompt=prompt,
        map_id=map_id,
        raw_image=raw_image,
        warnings=warnings,
    )
    state["draft_id"] = draft_id
    state["style_reference_used"] = "local_placeholder" if uses_local_placeholder else style_reference_used
    _write_state(draft_package_path(root, draft_id), state)
    return state


def _state_from_package(package_path: Path, *, prompt: str, warnings: list[str]) -> dict[str, Any]:
    manifest = yaml.safe_load((package_path / "map.yaml").read_text(encoding="utf-8")) or {}
    validation = validate_manifest_path(package_path / "map.yaml")
    state = {
        "draft_id": package_path.name,
        "map_id": str(manifest.get("map_id") or package_path.name),
        "prompt": prompt,
        "status": "ready" if validation.ok else "needs_fix",
        "package_path": str(package_path),
        "locations": manifest.get("locations") or [],
        "interactions": manifest.get("interactions") or [],
        "validation": validation.as_dict(),
        "warnings": list(warnings) + list(validation.warnings),
        "collision_data": _collision_data_from_package(package_path),
        "style_reference_used": "none",
    }
    return state


def _write_state(package_path: Path, state: dict[str, Any]) -> None:
    _draft_meta_path(package_path).write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_draft(*, root: Path, draft_id: str) -> dict[str, Any]:
    package_path = draft_package_path(root, draft_id)
    if not package_path.exists():
        raise HTTPException(status_code=404, detail=f"Map Studio draft not found: {draft_id}")
    meta_path = _draft_meta_path(package_path)
    if meta_path.exists():
        state = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        state = _state_from_package(package_path, prompt="", warnings=[])
    validation = validate_manifest_path(package_path / "map.yaml")
    state["validation"] = validation.as_dict()
    state["status"] = "ready" if validation.ok else "needs_fix"
    state["warnings"] = list(dict.fromkeys([*state.get("warnings", []), *validation.warnings]))
    state["collision_data"] = _collision_data_from_package(package_path)
    state["style_reference_used"] = str(state.get("style_reference_used") or "none")
    return state


def patch_draft(
    *,
    root: Path,
    draft_id: str,
    locations: list[dict[str, Any]] | None = None,
    interactions: list[dict[str, Any]] | None = None,
    collision_edits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    package_path = draft_package_path(root, draft_id)
    state = load_draft(root=root, draft_id=draft_id)
    manifest_path = package_path / "map.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if locations is not None:
        existing = [
            item for item in manifest.get("locations", [])
            if isinstance(item, dict) and item.get("id")
        ]
        by_id = {str(item["id"]): dict(item) for item in existing}
        order = [str(item["id"]) for item in existing]
        for location in locations:
            location_id = str(location.get("id") or "").strip()
            if not location_id:
                continue
            if location_id not in by_id:
                order.append(location_id)
            by_id[location_id] = location
        manifest["locations"] = [by_id[location_id] for location_id in order if location_id in by_id]
    if interactions is not None:
        existing_interactions = [
            item for item in manifest.get("interactions", [])
            if isinstance(item, dict) and item.get("id")
        ]
        by_interaction_id = {str(item["id"]): dict(item) for item in existing_interactions}
        interaction_order = [str(item["id"]) for item in existing_interactions]
        for interaction in interactions:
            interaction_id = str(interaction.get("id") or "").strip()
            if not interaction_id:
                continue
            if interaction_id not in by_interaction_id:
                interaction_order.append(interaction_id)
            by_interaction_id[interaction_id] = interaction
        manifest["interactions"] = [
            by_interaction_id[interaction_id]
            for interaction_id in interaction_order
            if interaction_id in by_interaction_id
        ]
    manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")

    if collision_edits:
        map_path = package_path / "visuals" / "map.json"
        tiled_map = json.loads(map_path.read_text(encoding="utf-8"))
        for layer in tiled_map.get("layers", []) or []:
            if layer.get("name") == "Collisions" and isinstance(layer.get("data"), list):
                layer["data"] = _apply_collision_edits(layer["data"], collision_edits)
                break
        map_path.write_text(json.dumps(tiled_map, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    next_state = _state_from_package(
        package_path,
        prompt=str(state.get("prompt") or ""),
        warnings=[str(item) for item in state.get("warnings", []) if "Validation" not in str(item)],
    )
    next_state["draft_id"] = draft_id
    next_state["style_reference_used"] = str(state.get("style_reference_used") or "none")
    next_state["collision_data"] = _collision_data_from_package(package_path)
    _write_state(package_path, next_state)
    return next_state


async def regenerate_image(
    *,
    root: Path,
    draft_id: str,
    image_config: dict[str, str] | None = None,
) -> dict[str, Any]:
    state = load_draft(root=root, draft_id=draft_id)
    package_path = draft_package_path(root, draft_id)
    uses_local_placeholder = not _image_config_value(image_config, "IMAGE_GEN_API_KEY")
    manifest_path = package_path / "map.yaml"
    current_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    preserved_manifest_fields = {
        key: current_manifest[key]
        for key in ("locations", "interactions", "default_location_order", "spawn_points")
        if key in current_manifest
    }
    preserved_collision_data = _collision_data_from_package(package_path)
    resolved_reference_bytes, resolved_reference_filename, resolved_reference_content_type, style_reference_used = (
        _resolve_style_reference(
            root,
            reference_bytes=None,
            reference_filename="reference.png",
            reference_content_type="image/png",
        )
    )
    raw_image = await generate_map_image(
        prompt=str(state.get("prompt") or ""),
        image_config=image_config,
        reference_bytes=resolved_reference_bytes,
        reference_filename=resolved_reference_filename,
        reference_content_type=resolved_reference_content_type,
    )
    next_state = _write_package(
        package_path,
        prompt=str(state.get("prompt") or ""),
        map_id=str(state.get("map_id") or draft_id),
        raw_image=raw_image,
        warnings=[str(item) for item in state.get("warnings", [])],
    )
    if preserved_manifest_fields:
        next_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        next_manifest.update(preserved_manifest_fields)
        manifest_path.write_text(yaml.safe_dump(next_manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
        preserved_locations = preserved_manifest_fields.get("locations")
        if isinstance(preserved_locations, list):
            asset_root = package_path / "location_assets"
            shutil.rmtree(asset_root, ignore_errors=True)
            full_map = Image.open(package_path / "visuals" / "map_assets" / "generated_full_map_tileset.png").convert("RGB")
            _write_location_assets(package_path, full_map, preserved_locations)
    if preserved_collision_data:
        _write_collision_data(package_path, preserved_collision_data)
    next_state = _state_from_package(
        package_path,
        prompt=str(state.get("prompt") or ""),
        warnings=[str(item) for item in state.get("warnings", [])],
    )
    next_state["draft_id"] = draft_id
    next_state["style_reference_used"] = "local_placeholder" if uses_local_placeholder else style_reference_used
    _write_state(package_path, next_state)
    return next_state


def validate_draft(*, root: Path, draft_id: str) -> dict[str, Any]:
    state = load_draft(root=root, draft_id=draft_id)
    _write_state(draft_package_path(root, draft_id), state)
    return state


def _unique_publish_path(root: Path, requested_map_id: str) -> tuple[str, Path]:
    base = sanitize_map_id(requested_map_id, "generated_map")
    published_root = generated_maps_root(root)
    published_root.mkdir(parents=True, exist_ok=True)
    map_id = base
    suffix = 2
    while (published_root / map_id).exists():
        map_id = f"{base}_{suffix}"
        suffix += 1
    return map_id, published_root / map_id


def publish_draft(*, root: Path, draft_id: str, map_id: str | None = None) -> dict[str, Any]:
    state = validate_draft(root=root, draft_id=draft_id)
    validation = state.get("validation") or {}
    if not validation.get("ok"):
        raise HTTPException(status_code=400, detail={"message": "Draft validation failed", "validation": validation})
    source = draft_package_path(root, draft_id)
    publish_map_id, target = _unique_publish_path(root, map_id or str(state.get("map_id") or draft_id))
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("draft.json"),
    )
    manifest_path = target / "map.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    manifest["map_id"] = publish_map_id
    manifest["display_name"] = publish_map_id
    localized = manifest.get("localized")
    if not isinstance(localized, dict):
        localized = {}
    for locale in ("en", "zh"):
        locale_values = localized.get(locale)
        if not isinstance(locale_values, dict):
            locale_values = {}
            localized[locale] = locale_values
        locale_values["display_name"] = publish_map_id
    manifest["localized"] = localized
    manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
    validation = validate_manifest_path(manifest_path)
    if not validation.ok:
        shutil.rmtree(target, ignore_errors=True)
        raise HTTPException(status_code=400, detail={"message": "Published package validation failed", "validation": validation.as_dict()})
    return {
        "map_id": publish_map_id,
        "package_path": str(target),
        "manifest_path": str(manifest_path),
        "validation": validation.as_dict(),
        "setup_url": f"/setup?map_id={publish_map_id}",
    }
