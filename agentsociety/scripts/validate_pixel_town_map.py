#!/usr/bin/env python3
"""Validate a PixelTownSocialEnv manifest.

For the canonical ``the_ville`` map, this also checks compatibility with the
original Generative Agents matrix semantics.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any

import yaml


REQUIRED_ORIGINAL_LOCATIONS = {
    "home",
    "school",
    "library",
    "cafe",
    "park",
    "supply_store",
    "market",
    "pharmacy",
    "pub",
    "dorm",
}
REMOVED_GENERATED_LOCATIONS = {
    "town_square",
    "tool_shed",
    "community_board",
    "civil_defense_center",
    "old_zhang_yard",
    "clinic",
    "prison",
    "volcano",
    "volcano_edge",
}
DEFAULT_GENERATIVE_MATRIX_ROOT = os.environ.get(
    "GOD_GENERATIVE_MATRIX_ROOT",
    "",
).strip()


def _load(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) if path.suffix.lower() in {".yaml", ".yml"} else json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in {path}")
    return data


def _resolve(base: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def _resolve_matrix_root(matrix_root: Path | None) -> Path | None:
    if matrix_root is not None:
        return matrix_root
    if DEFAULT_GENERATIVE_MATRIX_ROOT:
        return Path(DEFAULT_GENERATIVE_MATRIX_ROOT).expanduser()
    return None


def _walkable_tiles(tiled_map: dict[str, Any]) -> set[tuple[int, int]]:
    width = int(tiled_map.get("width") or 0)
    height = int(tiled_map.get("height") or 0)
    collisions = next(
        (
            layer
            for layer in tiled_map.get("layers", []) or []
            if layer.get("name") == "Collisions" and layer.get("type") == "tilelayer"
        ),
        None,
    )
    if not collisions or not isinstance(collisions.get("data"), list):
        return {(x, y) for y in range(height) for x in range(width)}
    return {
        (index % width, index // width)
        for index, gid in enumerate(collisions["data"])
        if int(gid or 0) == 0
    }


def _bounds_tuple(bounds: dict[str, Any] | None) -> tuple[int, int, int, int] | None:
    if not isinstance(bounds, dict):
        return None
    try:
        x = int(bounds["x"])
        y = int(bounds["y"])
        w = int(bounds["w"])
        h = int(bounds["h"])
    except Exception:
        return None
    if w <= 0 or h <= 0:
        return None
    return (x, y, x + w - 1, y + h - 1)


def _load_flat_grid(path: Path, width: int, height: int) -> list[list[str]]:
    values: list[str] = []
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.reader(file):
            values.extend(cell.strip() for cell in row)
    expected = width * height
    if len(values) != expected:
        raise ValueError(f"{path} has {len(values)} cells; expected {expected}")
    return [values[index * width : (index + 1) * width] for index in range(height)]


def _load_blocks(path: Path) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.reader(file):
            if row:
                blocks[row[0].strip()] = [cell.strip() for cell in row[1:]]
    return blocks


class OriginalVilleMatrix:
    def __init__(self, root: Path) -> None:
        meta = json.loads((root / "maze_meta_info.json").read_text(encoding="utf-8"))
        self.width = int(meta["maze_width"])
        self.height = int(meta["maze_height"])
        maze = root / "maze"
        blocks = root / "special_blocks"
        self.sector_grid = _load_flat_grid(maze / "sector_maze.csv", self.width, self.height)
        self.arena_grid = _load_flat_grid(maze / "arena_maze.csv", self.width, self.height)
        self.object_grid = _load_flat_grid(maze / "game_object_maze.csv", self.width, self.height)
        self.sector_blocks = _load_blocks(blocks / "sector_blocks.csv")
        self.arena_blocks = _load_blocks(blocks / "arena_blocks.csv")
        self.object_blocks = _load_blocks(blocks / "game_object_blocks.csv")

    @staticmethod
    def _bbox(cells: list[tuple[int, int]]) -> tuple[int, int, int, int] | None:
        if not cells:
            return None
        xs = [x for x, _ in cells]
        ys = [y for _, y in cells]
        return (min(xs), min(ys), max(xs), max(ys))

    def _cells_for(
        self,
        grid: list[list[str]],
        blocks: dict[str, list[str]],
        address_parts: list[str],
    ) -> list[tuple[int, int]]:
        cells: list[tuple[int, int]] = []
        for y, row in enumerate(grid):
            for x, gid in enumerate(row):
                parts = blocks.get(gid)
                if parts and parts[-len(address_parts) :] == address_parts:
                    cells.append((x, y))
        return cells

    def semantic_bbox(self, source_address: str) -> tuple[int, int, int, int] | None:
        parts = [part.strip() for part in str(source_address).split(":") if part.strip()]
        if len(parts) == 2:
            return self._bbox(self._cells_for(self.sector_grid, self.sector_blocks, parts))
        if len(parts) == 3:
            return self._bbox(self._cells_for(self.arena_grid, self.arena_blocks, parts))
        return None

    def object_bbox(
        self,
        object_name: str,
        within: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int] | None:
        x0, y0, x1, y1 = within
        cells: list[tuple[int, int]] = []
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                gid = self.object_grid[y][x]
                parts = self.object_blocks.get(gid)
                if parts and parts[-1] == object_name:
                    cells.append((x, y))
        return self._bbox(cells)


def _contains(bounds: tuple[int, int, int, int], x: int, y: int) -> bool:
    return bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]


def validate_manifest(manifest_path: Path, matrix_root: Path | None = None) -> list[str]:
    manifest_path = manifest_path.resolve()
    manifest = _load(manifest_path)
    errors: list[str] = []
    warnings: list[str] = []
    map_id = str(manifest.get("map_id") or manifest_path.parent.name)
    is_the_ville = map_id == "the_ville"

    tiled_map_path = _resolve(manifest_path.parent, str(manifest.get("tiled_map_path") or "map.json"))
    if not tiled_map_path.exists():
        return [f"ERROR tiled_map_path missing: {tiled_map_path}"]
    tiled_map = _load(tiled_map_path)
    width = int(tiled_map.get("width") or 0)
    height = int(tiled_map.get("height") or 0)
    if width <= 0 or height <= 0:
        errors.append(f"map must have positive width and height, got {width}x{height}")
    if is_the_ville and (width, height) != (140, 100):
        errors.append(f"expected original The Ville map size 140x100, got {width}x{height}")
    if is_the_ville and tiled_map_path.name != "the_ville_jan7.json":
        errors.append(f"manifest should reference original map file the_ville_jan7.json, got {tiled_map_path.name}")

    walkable = _walkable_tiles(tiled_map)
    tileset_parent = tiled_map_path.parent
    for index, tileset in enumerate(tiled_map.get("tilesets", []) or []):
        if not isinstance(tileset, dict) or not tileset.get("image"):
            continue
        image_path = _resolve(tileset_parent, str(tileset["image"]))
        if not image_path.exists():
            errors.append(f"tileset[{index}] image missing: {image_path}")
        if is_the_ville and "community_life" in image_path.name:
            errors.append(f"generated AgentSociety tileset must not be used: {image_path}")

    matrix: OriginalVilleMatrix | None = None
    resolved_matrix_root = _resolve_matrix_root(matrix_root)
    if is_the_ville and resolved_matrix_root is None:
        warnings.append(
            "original generative_agents matrix not configured; set "
            "GOD_GENERATIVE_MATRIX_ROOT or pass --generative-matrix-root to enable "
            "semantic-source validation"
        )
    elif is_the_ville and resolved_matrix_root.exists():
        matrix = OriginalVilleMatrix(resolved_matrix_root)
    elif is_the_ville:
        warnings.append(f"original generative_agents matrix not found; skipped semantic-source validation: {resolved_matrix_root}")

    locations = manifest.get("locations") or []
    interactions = manifest.get("interactions") or []
    if not isinstance(locations, list) or not locations:
        errors.append("manifest must define at least one location")
        locations = []
    if not isinstance(interactions, list):
        errors.append("manifest interactions must be a list")
        interactions = []

    location_ids: set[str] = set()
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
        if is_the_ville and location_id in REMOVED_GENERATED_LOCATIONS:
            errors.append(f"generated or unsupported location should be removed: {location_id}")

        anchor = item.get("anchor_tile") or {}
        try:
            x = int(anchor["x"])
            y = int(anchor["y"])
        except Exception:
            errors.append(f"location {location_id} missing integer anchor_tile")
            continue
        if x < 0 or y < 0 or x >= width or y >= height:
            errors.append(f"location {location_id} anchor out of bounds: ({x}, {y})")
        elif (x, y) not in walkable:
            warnings.append(f"location {location_id} anchor is not walkable in Tiled collision layer: ({x}, {y})")

        bounds = _bounds_tuple(item.get("bounds"))
        if bounds is None:
            errors.append(f"location {location_id} is missing valid bounds")
            continue
        if not _contains(bounds, x, y):
            errors.append(f"location {location_id} anchor not inside bounds: ({x}, {y})")

        source_address = str(item.get("source_address") or "").strip()
        if is_the_ville and not source_address:
            errors.append(f"location {location_id} missing source_address")
        elif matrix is not None:
            semantic_bounds = matrix.semantic_bbox(source_address)
            if semantic_bounds is None:
                errors.append(f"location {location_id} source_address not found in original matrix: {source_address}")
            elif bounds != semantic_bounds:
                errors.append(
                    f"location {location_id} bounds {bounds} do not match original matrix {semantic_bounds}"
                )
            source_object = str(item.get("source_object") or "").strip()
            if source_object and semantic_bounds is not None:
                object_bounds = matrix.object_bbox(source_object, semantic_bounds)
                if object_bounds is None:
                    errors.append(f"location {location_id} source_object not found: {source_object}")
                elif not _contains(object_bounds, x, y):
                    errors.append(
                        f"location {location_id} anchor ({x}, {y}) is outside source_object {source_object} {object_bounds}"
                    )

    missing = REQUIRED_ORIGINAL_LOCATIONS - location_ids
    if is_the_ville and missing:
        errors.append(f"missing original The Ville locations: {', '.join(sorted(missing))}")

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

    return [f"ERROR {message}" for message in errors] + [f"WARN {message}" for message in warnings]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifest",
        nargs="?",
        default="custom/maps/the_ville/map.yaml",
        help="Path to a PixelTownSocialEnv YAML/JSON manifest.",
    )
    parser.add_argument(
        "--generative-matrix-root",
        default=DEFAULT_GENERATIVE_MATRIX_ROOT,
        help=(
            "Path to generative_agents The Ville matrix directory. Defaults to "
            "GOD_GENERATIVE_MATRIX_ROOT; if unset, semantic-source validation is skipped."
        ),
    )
    args = parser.parse_args()
    messages = validate_manifest(
        Path(args.manifest),
        matrix_root=(
            Path(args.generative_matrix_root).expanduser()
            if args.generative_matrix_root
            else None
        ),
    )
    if messages:
        print("\n".join(messages))
    else:
        print(f"OK {Path(args.manifest).resolve()}")
    return 1 if any(message.startswith("ERROR ") for message in messages) else 0


if __name__ == "__main__":
    raise SystemExit(main())
