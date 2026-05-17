#!/usr/bin/env python3
"""Audit A* routes between semantic locations in a GOD map package."""

from __future__ import annotations

import argparse
import heapq
import json
from pathlib import Path
from typing import Any

import yaml


Tile = tuple[int, int]

DEFAULT_ROUTES: dict[str, list[tuple[str, str]]] = {
    "the_ville": [("park", "cafe"), ("home", "market"), ("school", "library")],
    "pku": [
        ("west_gate", "centennial_hall"),
        ("dormitory", "library"),
        ("weiming_lake", "teaching_building"),
    ],
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_structured(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in {path}")
    return data


def manifest_path_for(path: Path) -> Path:
    if path.is_file():
        return path
    for filename in ("map.yaml", "map.yml", "town.yaml", "town.yml", "map.json", "town.json"):
        candidate = path / filename
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No map manifest found under {path}")


def load_map(manifest_path: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    manifest = load_structured(manifest_path)
    map_path = manifest_path.parent / str(manifest.get("tiled_map_path") or "visuals/map.json")
    return manifest, load_structured(map_path), map_path


def walkable_tiles(tiled_map: dict[str, Any]) -> tuple[set[Tile], int, int]:
    width = int(tiled_map.get("width") or 0)
    height = int(tiled_map.get("height") or 0)
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
    if not collisions or not isinstance(collisions.get("data"), list):
        raise ValueError("Map must include a tile layer named Collisions")
    return {
        (index % width, index // width)
        for index, gid in enumerate(collisions["data"])
        if int(gid or 0) == 0
    }, width, height


def nearest_walkable(tile: Tile, walkable: set[Tile]) -> Tile:
    if tile in walkable or not walkable:
        return tile
    return min(walkable, key=lambda item: abs(item[0] - tile[0]) + abs(item[1] - tile[1]))


def find_path(start: Tile, goal: Tile, walkable: set[Tile], width: int, height: int) -> list[Tile] | None:
    start = nearest_walkable(start, walkable)
    goal = nearest_walkable(goal, walkable)
    frontier: list[tuple[int, Tile]] = [(0, start)]
    came_from: dict[Tile, Tile | None] = {start: None}
    cost_so_far: dict[Tile, int] = {start: 0}

    while frontier:
        _, current = heapq.heappop(frontier)
        if current == goal:
            break
        x, y = current
        for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= neighbor[0] < width and 0 <= neighbor[1] < height and neighbor in walkable):
                continue
            next_cost = cost_so_far[current] + 1
            if neighbor not in cost_so_far or next_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = next_cost
                priority = next_cost + abs(goal[0] - neighbor[0]) + abs(goal[1] - neighbor[1])
                heapq.heappush(frontier, (priority, neighbor))
                came_from[neighbor] = current

    if goal not in came_from:
        return None
    path = [goal]
    current = goal
    while came_from[current] is not None:
        current = came_from[current]  # type: ignore[assignment]
        path.append(current)
    path.reverse()
    return path


def location_tiles(manifest: dict[str, Any], walkable: set[Tile]) -> dict[str, Tile]:
    result: dict[str, Tile] = {}
    for location in manifest.get("locations") or []:
        if not isinstance(location, dict):
            continue
        anchor = location.get("anchor_tile") or {}
        try:
            tile = (int(anchor["x"]), int(anchor["y"]))
        except Exception:
            continue
        result[str(location.get("id") or "")] = nearest_walkable(tile, walkable)
    return result


def parse_route(raw: str) -> tuple[str, str]:
    if ":" in raw:
        left, right = raw.split(":", 1)
    elif "->" in raw:
        left, right = raw.split("->", 1)
    else:
        raise argparse.ArgumentTypeError("Routes must look like from:to or from->to")
    return left.strip(), right.strip()


def write_overlay(
    target: Path,
    width: int,
    height: int,
    walkable: set[Tile],
    paths: list[tuple[str, str, list[Tile]]],
) -> None:
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:  # pragma: no cover - depends on optional local tooling
        raise RuntimeError("PNG overlay requires Pillow") from exc

    scale = 6
    image = Image.new("RGBA", (width * scale, height * scale), (247, 250, 252, 255))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        for x in range(width):
            if (x, y) not in walkable:
                draw.rectangle(
                    [x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1],
                    fill=(17, 24, 39, 180),
                )
    colors = [(239, 68, 68, 255), (37, 99, 235, 255), (22, 163, 74, 255), (217, 119, 6, 255)]
    for index, (_, _, path) in enumerate(paths):
        color = colors[index % len(colors)]
        points = [(x * scale + scale // 2, y * scale + scale // 2) for x, y in path]
        if len(points) >= 2:
            draw.line(points, fill=color, width=max(2, scale // 2))
        for x, y in (path[0], path[-1]):
            draw.ellipse(
                [x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1],
                fill=color,
            )
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map", help="Map package directory, manifest path, or map id under custom/maps.")
    parser.add_argument("--route", action="append", type=parse_route, help="Route to audit, as from:to.")
    parser.add_argument("--overlay", type=Path, help="Optional PNG path for a compact route overlay.")
    args = parser.parse_args()

    target = Path(args.map).expanduser()
    if not target.is_absolute():
        maps_candidate = repo_root() / "custom" / "maps" / str(args.map)
        target = maps_candidate if maps_candidate.exists() else (repo_root() / target)
    manifest_path = manifest_path_for(target.resolve())
    manifest, tiled_map, _ = load_map(manifest_path)
    map_id = str(manifest.get("map_id") or manifest_path.parent.name)
    routes = args.route or DEFAULT_ROUTES.get(map_id, [])
    if not routes:
        raise SystemExit(f"No default routes for map_id={map_id}; pass --route from:to")

    walkable, width, height = walkable_tiles(tiled_map)
    locations = location_tiles(manifest, walkable)
    resolved_paths: list[tuple[str, str, list[Tile]]] = []
    errors: list[str] = []
    for start_id, goal_id in routes:
        if start_id not in locations or goal_id not in locations:
            errors.append(f"{start_id}->{goal_id}: missing location id")
            continue
        path = find_path(locations[start_id], locations[goal_id], walkable, width, height)
        if path is None:
            errors.append(f"{start_id}->{goal_id}: unreachable")
            continue
        resolved_paths.append((start_id, goal_id, path))
        preview = path[:4] + ([(-1, -1)] if len(path) > 10 else []) + path[-4:]
        preview_text = " ".join("..." if item == (-1, -1) else f"({item[0]},{item[1]})" for item in preview)
        print(f"OK {start_id}->{goal_id} length={len(path)} preview={preview_text}")

    if args.overlay and resolved_paths:
        write_overlay(args.overlay.expanduser().resolve(), width, height, walkable, resolved_paths)
        print(f"overlay={args.overlay.expanduser().resolve()}")

    if errors:
        print("\n".join(f"ERROR {error}" for error in errors))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
