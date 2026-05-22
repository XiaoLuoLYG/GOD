"""Discovery and validation helpers for GOD pixel-town map packages."""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import json
import os
from pathlib import Path
from typing import Any

import yaml


DEFAULT_MAP_ID = "the_ville"
MANIFEST_FILENAMES = ("map.yaml", "map.yml", "town.yaml", "town.yml", "map.json", "town.json")
REQUIRED_ROUTE_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    "the_ville": (("park", "cafe"), ("home", "market")),
    "pku": (
        ("west_gate", "centennial_hall"),
        ("dormitory", "library"),
        ("weiming_lake", "teaching_building"),
    ),
}


@dataclass(frozen=True)
class MapValidation:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class MapPackage:
    map_id: str
    display_name: str
    package_path: Path
    manifest_path: Path
    manifest: dict[str, Any]
    validation: MapValidation

    @property
    def tile_size(self) -> int:
        return int(self.manifest.get("tile_size") or 32)

    @property
    def locations(self) -> list[dict[str, Any]]:
        values = self.manifest.get("locations") or []
        return [item for item in values if isinstance(item, dict)]

    @property
    def interactions(self) -> list[dict[str, Any]]:
        values = self.manifest.get("interactions") or []
        return [item for item in values if isinstance(item, dict)]

    @property
    def default_location_order(self) -> list[str]:
        raw = self.manifest.get("default_location_order") or []
        return [str(item) for item in raw if str(item).strip()]


def agentsociety_root() -> Path:
    """Return the best current AgentSociety root."""

    candidates: list[Path] = []
    if os.getenv("GOD_ROOT"):
        candidates.append(Path(os.environ["GOD_ROOT"]).expanduser().resolve() / "agentsociety")

    cwd = Path.cwd().resolve()
    candidates.extend([cwd, cwd / "agentsociety"])
    candidates.extend(parent for parent in cwd.parents)

    code_root = Path(__file__).resolve()
    candidates.extend(parent for parent in code_root.parents)

    for candidate in candidates:
        if (candidate / "custom" / "maps").exists():
            return candidate

    return cwd


def maps_root(root: Path | None = None) -> Path:
    return (root or agentsociety_root()) / "custom" / "maps"


def _load_structured(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in map manifest: {path}")
    return data


def _has_walkable_route(
    start: tuple[int, int],
    goal: tuple[int, int],
    walkable: set[tuple[int, int]],
    width: int,
    height: int,
) -> bool:
    if start not in walkable or goal not in walkable:
        return False

    frontier: list[tuple[int, tuple[int, int]]] = [(0, start)]
    cost_so_far: dict[tuple[int, int], int] = {start: 0}
    while frontier:
        _, current = heapq.heappop(frontier)
        if current == goal:
            return True
        x, y = current
        for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= neighbor[0] < width and 0 <= neighbor[1] < height and neighbor in walkable):
                continue
            next_cost = cost_so_far[current] + 1
            if neighbor in cost_so_far and cost_so_far[neighbor] <= next_cost:
                continue
            cost_so_far[neighbor] = next_cost
            priority = next_cost + abs(goal[0] - neighbor[0]) + abs(goal[1] - neighbor[1])
            heapq.heappush(frontier, (priority, neighbor))
    return False


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def safe_resolve(base: Path, raw: str, package_root: Path) -> Path:
    path = Path(raw).expanduser()
    resolved = path if path.is_absolute() else (base / path).resolve()
    if not is_within(resolved, package_root):
        raise ValueError(f"Map package resource escapes package root: {raw}")
    return resolved


def _manifest_path_for_dir(path: Path) -> Path | None:
    for filename in MANIFEST_FILENAMES:
        candidate = path / filename
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def resolve_manifest_path(map_id: str | None = None, root: Path | None = None) -> Path:
    root = root or agentsociety_root()
    requested = str(map_id or DEFAULT_MAP_ID).strip() or DEFAULT_MAP_ID
    direct_dir = maps_root(root) / requested
    direct_manifest = _manifest_path_for_dir(direct_dir)
    if direct_manifest:
        return direct_manifest.resolve()

    for package_dir in sorted(maps_root(root).iterdir() if maps_root(root).exists() else []):
        if not package_dir.is_dir() or package_dir.name.startswith(("_", ".")):
            continue
        manifest_path = _manifest_path_for_dir(package_dir)
        if not manifest_path:
            continue
        try:
            manifest = _load_structured(manifest_path)
        except Exception:
            continue
        if str(manifest.get("map_id") or package_dir.name) == requested:
            return manifest_path.resolve()

    if requested != DEFAULT_MAP_ID:
        return resolve_manifest_path(DEFAULT_MAP_ID, root)

    raise FileNotFoundError(f"No map package manifest found for map_id={requested!r}")


def tiled_map_path(package: MapPackage) -> Path:
    raw = str(package.manifest.get("tiled_map_path") or "visuals/map.json")
    return safe_resolve(package.manifest_path.parent, raw, package.package_path)


def load_tiled_map(package: MapPackage) -> tuple[Path, dict[str, Any]]:
    path = tiled_map_path(package)
    return path, _load_structured(path)


def tileset_image_path(package: MapPackage, tileset_index: int) -> Path:
    map_path, tiled_map = load_tiled_map(package)
    tilesets = tiled_map.get("tilesets", []) or []
    if tileset_index < 0 or tileset_index >= len(tilesets):
        raise IndexError("Tileset not found")
    tileset = tilesets[tileset_index]
    if not isinstance(tileset, dict) or not tileset.get("image"):
        raise FileNotFoundError("Tileset image not found")
    return safe_resolve(map_path.parent, str(tileset["image"]), package.package_path)


def character_root_path(package: MapPackage) -> Path | None:
    raw = str(package.manifest.get("character_root") or "characters").strip()
    if not raw:
        return None
    path = safe_resolve(package.manifest_path.parent, raw, package.package_path)
    return path if path.exists() and path.is_dir() else None


def character_sprites(package: MapPackage) -> list[dict[str, Any]]:
    root = character_root_path(package)
    if root is None:
        return []
    return [
        {
            "name": path.stem,
            "filename": path.name,
            "frame_width": int(package.manifest.get("character_frame_width") or package.tile_size),
            "frame_height": int(package.manifest.get("character_frame_height") or package.tile_size),
        }
        for path in sorted(root.glob("*.png"))
        if path.is_file()
    ]


def character_sprite_path(package: MapPackage, character_name: str) -> Path:
    root = character_root_path(package)
    if root is None:
        raise FileNotFoundError("Map package has no character sprites")
    safe_name = Path(character_name).name
    for candidate in (root / safe_name, root / f"{safe_name}.png"):
        resolved = candidate.resolve()
        if is_within(resolved, root) and resolved.exists() and resolved.is_file():
            return resolved
    raise FileNotFoundError(f"Character sprite not found: {character_name}")


def location_asset_path(package: MapPackage, location_id: str) -> Path:
    requested = str(location_id)
    for location in package.locations:
        if str(location.get("id") or "") != requested:
            continue
        visual_asset = str(location.get("visual_asset") or "").strip()
        if not visual_asset:
            raise FileNotFoundError("Location has no visual asset")
        return safe_resolve(package.manifest_path.parent, visual_asset, package.package_path)
    raise FileNotFoundError(f"Location not found: {location_id}")


def validate_manifest_path(manifest_path: Path) -> MapValidation:
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = manifest_path.resolve()
    package_root = manifest_path.parent

    try:
        manifest = _load_structured(manifest_path)
    except Exception as exc:
        return MapValidation(False, (f"manifest could not be read: {exc}",), ())

    for key in ("map_id", "display_name", "tile_size", "tiled_map_path", "locations"):
        if key not in manifest or manifest.get(key) in (None, ""):
            errors.append(f"missing required field: {key}")
    map_id = str(manifest.get("map_id") or package_root.name)

    try:
        map_path = safe_resolve(package_root, str(manifest.get("tiled_map_path") or "visuals/map.json"), package_root)
    except ValueError as exc:
        errors.append(str(exc))
        map_path = package_root / "__invalid__.json"

    tiled_map: dict[str, Any] = {}
    if not map_path.exists():
        errors.append(f"tiled_map_path missing: {map_path}")
    else:
        try:
            tiled_map = _load_structured(map_path)
        except Exception as exc:
            errors.append(f"tiled map could not be read: {exc}")

    width = int(tiled_map.get("width") or 0)
    height = int(tiled_map.get("height") or 0)
    if tiled_map:
        if str(tiled_map.get("orientation") or "orthogonal") != "orthogonal":
            errors.append("v1 map packages support only orthogonal Tiled maps")
        tilewidth = int(tiled_map.get("tilewidth") or 0)
        tileheight = int(tiled_map.get("tileheight") or 0)
        tile_size = int(manifest.get("tile_size") or 0)
        if tile_size <= 0:
            errors.append("tile_size must be a positive integer")
        if tilewidth and tileheight and tile_size and (tilewidth != tile_size or tileheight != tile_size):
            warnings.append(f"manifest tile_size {tile_size} differs from tiled map {tilewidth}x{tileheight}")

    collisions = next(
        (
            layer
            for layer in tiled_map.get("layers", []) or []
            if isinstance(layer, dict)
            and layer.get("name") == "Collisions"
            and layer.get("type") == "tilelayer"
        ),
        None,
    )
    walkable: set[tuple[int, int]] = set()
    if not collisions or not isinstance(collisions.get("data"), list):
        errors.append("tiled map must include a tile layer named Collisions")
    else:
        for index, gid in enumerate(collisions["data"]):
            if int(gid or 0) == 0:
                walkable.add((index % width, index // width))

    for index, tileset in enumerate(tiled_map.get("tilesets", []) or []):
        if not isinstance(tileset, dict) or not tileset.get("image"):
            continue
        try:
            image_path = safe_resolve(map_path.parent, str(tileset["image"]), package_root)
        except ValueError as exc:
            errors.append(f"tileset[{index}] {exc}")
            continue
        if not image_path.exists() or not image_path.is_file():
            errors.append(f"tileset[{index}] image missing: {image_path}")

    locations = manifest.get("locations") or []
    if not isinstance(locations, list) or not locations:
        errors.append("locations must be a non-empty list")
        locations = []
    location_ids: set[str] = set()
    location_anchors: dict[str, tuple[int, int]] = {}
    for item in locations:
        if not isinstance(item, dict):
            errors.append(f"invalid location entry: {item!r}")
            continue
        location_id = str(item.get("id") or "").strip()
        if not location_id:
            errors.append(f"location missing id: {item!r}")
            continue
        if location_id in location_ids:
            errors.append(f"duplicate location id: {location_id}")
        location_ids.add(location_id)
        anchor = item.get("anchor_tile") or {}
        try:
            x = int(anchor["x"])
            y = int(anchor["y"])
        except Exception:
            errors.append(f"location {location_id} missing integer anchor_tile")
            continue
        if x < 0 or y < 0 or x >= width or y >= height:
            errors.append(f"location {location_id} anchor out of bounds: ({x}, {y})")
        elif collisions and (x, y) not in walkable:
            warnings.append(f"location {location_id} anchor is not walkable: ({x}, {y})")
        else:
            location_anchors[location_id] = (x, y)
        visual_asset = str(item.get("visual_asset") or "").strip()
        if visual_asset:
            try:
                visual_path = safe_resolve(package_root, visual_asset, package_root)
            except ValueError as exc:
                errors.append(f"location {location_id} {exc}")
                continue
            if not visual_path.exists() or not visual_path.is_file():
                errors.append(f"location {location_id} visual_asset missing: {visual_path}")

    if walkable and width > 0 and height > 0:
        for start_id, goal_id in REQUIRED_ROUTE_PAIRS.get(map_id, ()):
            start = location_anchors.get(start_id)
            goal = location_anchors.get(goal_id)
            if start is None or goal is None:
                errors.append(f"required route {start_id}->{goal_id} references unknown location")
            elif not _has_walkable_route(start, goal, walkable, width, height):
                errors.append(f"required route {start_id}->{goal_id} is not reachable")

    interactions = manifest.get("interactions") or []
    if not isinstance(interactions, list):
        errors.append("interactions must be a list")
        interactions = []
    interaction_ids: set[str] = set()
    for item in interactions:
        if not isinstance(item, dict):
            errors.append(f"invalid interaction entry: {item!r}")
            continue
        interaction_id = str(item.get("id") or "").strip()
        if not interaction_id:
            errors.append(f"interaction missing id: {item!r}")
            continue
        if interaction_id in interaction_ids:
            errors.append(f"duplicate interaction id: {interaction_id}")
        interaction_ids.add(interaction_id)
        for location_id in item.get("allowed_location_ids", []) or []:
            if str(location_id) not in location_ids:
                errors.append(f"interaction {interaction_id} references unknown location: {location_id}")

    for item in locations:
        if not isinstance(item, dict):
            continue
        location_id = str(item.get("id") or "").strip()
        for interaction_id in item.get("interaction_ids", []) or []:
            if str(interaction_id) not in interaction_ids:
                errors.append(f"location {location_id} references unknown interaction: {interaction_id}")

    char_root = str(manifest.get("character_root") or "characters").strip()
    if char_root:
        try:
            root = safe_resolve(package_root, char_root, package_root)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if not root.exists() or not root.is_dir():
                warnings.append(f"character_root missing: {root}")
            elif not any(root.glob("*.png")):
                warnings.append(f"character_root has no png sprites: {root}")

    return MapValidation(not errors, tuple(errors), tuple(warnings))


def load_map_package_by_manifest(manifest_path: Path) -> MapPackage:
    manifest_path = manifest_path.resolve()
    manifest = _load_structured(manifest_path)
    map_id = str(manifest.get("map_id") or manifest_path.parent.name)
    display_name = str(manifest.get("display_name") or map_id)
    return MapPackage(
        map_id=map_id,
        display_name=display_name,
        package_path=manifest_path.parent,
        manifest_path=manifest_path,
        manifest=manifest,
        validation=validate_manifest_path(manifest_path),
    )


def load_map_package(map_id: str | None = None, root: Path | None = None) -> MapPackage:
    return load_map_package_by_manifest(resolve_manifest_path(map_id, root))


def list_map_packages(root: Path | None = None) -> list[MapPackage]:
    root = root or agentsociety_root()
    found: list[MapPackage] = []
    root_path = maps_root(root)
    if not root_path.exists():
        return found
    for package_dir in sorted(root_path.iterdir()):
        if not package_dir.is_dir() or package_dir.name.startswith(("_", ".")):
            continue
        manifest_path = _manifest_path_for_dir(package_dir)
        if not manifest_path:
            continue
        try:
            found.append(load_map_package_by_manifest(manifest_path))
        except Exception:
            validation = validate_manifest_path(manifest_path)
            found.append(
                MapPackage(
                    map_id=package_dir.name,
                    display_name=package_dir.name,
                    package_path=package_dir,
                    manifest_path=manifest_path,
                    manifest={},
                    validation=validation,
                )
            )
    return found


def relative_manifest_path(package: MapPackage, root: Path | None = None) -> str:
    root = root or agentsociety_root()
    try:
        return str(package.manifest_path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(package.manifest_path)


def localized_metadata(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    localized: dict[str, dict[str, Any]] = {}
    for locale, fields in value.items():
        if not isinstance(fields, dict):
            continue
        localized[str(locale)] = {str(key): item for key, item in fields.items()}
    return localized


def map_package_summary(package: MapPackage, root: Path | None = None) -> dict[str, Any]:
    return {
        "map_id": package.map_id,
        "display_name": package.display_name,
        "localized": localized_metadata(package.manifest.get("localized")),
        "package_path": str(package.package_path),
        "manifest_path": str(package.manifest_path),
        "manifest_config_path": relative_manifest_path(package, root),
        "tile_size": package.tile_size,
        "location_count": len(package.locations),
        "interaction_count": len(package.interactions),
        "locations": package.locations,
        "interactions": package.interactions,
        "default_location_order": package.default_location_order,
        "character_count": len(character_sprites(package)),
        "validation_status": package.validation.as_dict(),
    }
