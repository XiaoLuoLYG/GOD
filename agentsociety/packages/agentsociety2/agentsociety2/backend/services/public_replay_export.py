"""Static export helpers for publishing finished replay runs to GitHub Pages."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import sqlite3
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import yaml

from agentsociety2.backend.services.experiment_packs import sanitize_experiment_pack_config
from agentsociety2.backend.services import experiment_registry
from agentsociety2.backend.services.map_packages import (
    DEFAULT_MAP_ID,
    character_sprite_path,
    character_sprites,
    load_map_package,
    load_map_package_by_manifest,
    load_tiled_map,
    localized_metadata,
    location_asset_path,
    tileset_image_path,
)
from agentsociety2.storage.replay_metadata import (
    AGENT_PROFILE_DATASET_CAPABILITY,
    COLUMN_CATALOG_TABLE,
    DATASET_CATALOG_TABLE,
    OPERATOR_COMMAND_TABLE_NAME,
)


PUBLIC_REPLAY_SPECS: tuple[dict[str, Any], ...] = (
    {
        "slug": "god-town",
        "hypothesis_id": "god_town",
        "experiment_id": "1",
        "title": "GOD Town",
        "summary": "A compact town where daily routines, messages, movement, ask, and intervention can be replayed step by step.",
        "image": "assets/screenshots/map-the-ville.png",
        "map_pack": "the_ville",
        "agent_pack": "jiuwen-town-residents",
        "experiment_pack": "god-town-daily-life",
        "tags": ["daily life", "baseline", "operator replay"],
    },
    {
        "slug": "pku-public-situation",
        "hypothesis_id": "pku_trump_visit",
        "experiment_id": "1",
        "title": "PKU Public Situation",
        "summary": "A campus-scale public event replay for watching attention, gathering, targeted questions, and live interventions.",
        "image": "assets/screenshots/map-pku.png",
        "map_pack": "pku",
        "agent_pack": "pku-campus-cast",
        "experiment_pack": "pku-public-situation",
        "tags": ["campus", "public event", "operator replay"],
    },
)

_ARTIFACT_RE = re.compile(
    r"^(?P<type>ask|intervene)_live_step_(?P<step>\d+)_(?P<date>\d{8})_(?P<time>\d{6})(?:_\d+)?\.md$"
)


def load_operator_commands(run_dir: Path) -> list[dict[str, Any]]:
    """Load recorded operator commands, falling back to legacy Markdown artifacts."""

    db_path = run_dir / "sqlite.db"
    if db_path.exists():
        commands = _load_operator_commands_from_sqlite(db_path)
        if commands:
            return commands
    return _load_operator_commands_from_artifacts(run_dir / "artifacts")


def export_public_replay(
    *,
    workspace_path: Path,
    hypothesis_id: str,
    experiment_id: str,
    slug: str,
    output_root: Path,
    title: str,
    summary: str,
    image: str | None = None,
    map_pack: str | None = None,
    agent_pack: str | None = None,
    experiment_pack: str | None = None,
    tags: Iterable[str] = (),
    download_base_url: str | None = None,
) -> dict[str, Any]:
    """Export one local replay run into static JSON/assets under ``output_root``."""

    workspace_path = Path(workspace_path).resolve()
    replay_root = Path(output_root) / "replays" / slug
    if replay_root.exists():
        shutil.rmtree(replay_root)
    (replay_root / "agents").mkdir(parents=True)
    (replay_root / "steps").mkdir()
    (replay_root / "downloads").mkdir()

    experiment_root = (
        workspace_path / f"hypothesis_{hypothesis_id}" / f"experiment_{experiment_id}"
    )
    run_dir = experiment_root / "run"
    db_path = run_dir / "sqlite.db"
    if not db_path.exists():
        raise FileNotFoundError(f"Replay database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        catalog = _load_dataset_catalog(conn)
        timeline = _load_timeline(conn, catalog)
        profiles = _load_agent_profiles(conn, catalog)
        _write_json(replay_root / "timeline.json", timeline)
        _write_json(replay_root / "agents" / "profiles.json", list(profiles.values()))

        commands = load_operator_commands(run_dir)
        _write_json(replay_root / "commands.json", commands)

        for index, point in enumerate(timeline):
            frame = _load_step_frame(conn, catalog, int(point["step"]), profiles)
            frame_name = f"{int(point['step']):06d}.json"
            _write_json(replay_root / "steps" / frame_name, frame)
            timeline[index]["frame_url"] = f"steps/{frame_name}"
        _write_json(replay_root / "timeline.json", timeline)
    finally:
        conn.close()

    map_info = _export_map_package(
        workspace_path=workspace_path,
        hypothesis_id=hypothesis_id,
        experiment_id=experiment_id,
        replay_root=replay_root,
    )
    map_pack_id = map_pack or str(map_info.get("map_id") or "map")
    map_pack_info = _publish_map_pack(
        output_root=Path(output_root),
        replay_root=replay_root,
        pack_id=map_pack_id,
        map_info=map_info,
        original_package_path=Path(str(map_info["_package_path"])),
        download_base_url=download_base_url,
    )
    agent_pack_id = agent_pack or f"{slug}-agents"
    agent_pack_info = _export_agent_pack(
        output_root=Path(output_root),
        replay_root=replay_root,
        pack_id=agent_pack_id,
        display_name=agent_pack_id,
        profiles=list(profiles.values()),
        map_info=map_info,
        download_base_url=download_base_url,
    )
    experiment_pack_id = experiment_pack or f"{slug}-experiment"
    experiment_pack_info = _export_experiment_pack(
        output_root=Path(output_root),
        experiment_root=experiment_root,
        pack_id=experiment_pack_id,
        display_name=title,
        replay_slug=slug,
        map_pack_id=map_pack_id,
        agent_pack_id=agent_pack_id,
        summary=summary,
        tags=list(tags),
        total_steps=len(timeline),
        agent_count=len(profiles),
        command_count=len(commands),
        download_base_url=download_base_url,
    )
    manifest = {
        "schema_version": 1,
        "slug": slug,
        "title": title,
        "summary": summary,
        "image": image,
        "hypothesis_id": hypothesis_id,
        "experiment_id": experiment_id,
        "map_pack": map_pack_id,
        "agent_pack": agent_pack_id,
        "experiment_pack": experiment_pack_id,
        "tags": list(tags),
        "total_steps": len(timeline),
        "agent_count": len(profiles),
        "command_count": len(commands),
        "start_time": timeline[0]["t"] if timeline else None,
        "end_time": timeline[-1]["t"] if timeline else None,
        "urls": {
            "timeline": "timeline.json",
            "commands": "commands.json",
            "profiles": "agents/profiles.json",
            "map": "map/map.json",
            "map_pack": f"../../map-packs/{map_pack_id}/map_pack.json",
            "agent_pack": f"../../agent-packs/{agent_pack_id}/agent_pack.json",
            "experiment_pack": f"../../experiments/{experiment_pack_id}/experiment.json",
        },
        "downloads": _create_downloads(
            replay_root=replay_root,
            experiment_root=experiment_root,
            map_package_path=Path(str(map_pack_info["_original_package_path"])),
            agent_pack_root=Path(str(agent_pack_info["_package_path"])),
            slug=slug,
            map_id=str(map_info.get("map_id") or "map"),
            download_base_url=download_base_url,
        ),
    }
    _write_json(replay_root / "manifest.json", manifest)
    return manifest


def export_known_public_replays(
    *,
    workspace_path: Path,
    output_root: Path,
    specs: Iterable[dict[str, Any]] = PUBLIC_REPLAY_SPECS,
    download_base_url: str | None = None,
) -> list[dict[str, Any]]:
    manifests = []
    workspace_path = Path(workspace_path)
    output_root = Path(output_root)
    for spec in specs:
        manifests.append(
            export_public_replay(
                workspace_path=workspace_path,
                output_root=output_root,
                slug=str(spec["slug"]),
                hypothesis_id=str(spec["hypothesis_id"]),
                experiment_id=str(spec["experiment_id"]),
                title=str(spec["title"]),
                summary=str(spec["summary"]),
                image=str(spec.get("image") or ""),
                map_pack=str(spec.get("map_pack") or ""),
                agent_pack=str(spec.get("agent_pack") or ""),
                experiment_pack=str(spec.get("experiment_pack") or ""),
                tags=spec.get("tags") or (),
                download_base_url=download_base_url,
            )
        )
    replay_experiment_pack_ids = {str(item.get("experiment_pack") or "") for item in manifests}
    curated_entries = [
        entry
        for entry in experiment_registry.load_registry_entries(workspace_path)
        if experiment_registry.public_slug(entry) not in replay_experiment_pack_ids
    ]
    if curated_entries:
        export_curated_experiment_packs(
            workspace_path=workspace_path,
            output_root=output_root,
            registry_entries=curated_entries,
            download_base_url=download_base_url,
        )
    _write_json(Path(output_root) / "replays" / "index.json", manifests)
    _write_collection_index(Path(output_root), "map-packs", "map_pack.json")
    _write_collection_index(Path(output_root), "agent-packs", "agent_pack.json")
    _write_collection_index(Path(output_root), "experiments", "experiment.json")
    return manifests


def export_curated_experiment_packs(
    *,
    workspace_path: Path,
    output_root: Path,
    registry_entries: Iterable[dict[str, Any]] | None = None,
    download_base_url: str | None = None,
) -> list[dict[str, Any]]:
    """Export curated playable ExperimentPacks, including entries without public replays."""

    workspace_path = Path(workspace_path).resolve()
    output_root = Path(output_root)
    entries = list(
        registry_entries
        if registry_entries is not None
        else experiment_registry.load_registry_entries(workspace_path)
    )
    manifests: list[dict[str, Any]] = []
    for entry in entries:
        if not entry.get("enabled", True):
            continue
        experiment_root = (
            workspace_path
            / f"hypothesis_{entry['hypothesis_id']}"
            / f"experiment_{entry.get('experiment_id') or '1'}"
        )
        if not experiment_root.exists():
            continue
        stats = _experiment_pack_stats(experiment_root)
        replay_slug = str(entry.get("replay_slug") or "").strip() or None
        summary = str(entry.get("description") or f"Playable setup seed for {entry.get('label') or entry['key']}.")
        manifests.append(
            _export_experiment_pack(
                output_root=output_root,
                experiment_root=experiment_root,
                pack_id=experiment_registry.public_slug(entry),
                display_name=str(entry.get("label") or entry["key"]),
                replay_slug=replay_slug,
                map_pack_id=str(entry.get("map_id") or ""),
                agent_pack_id=str(entry.get("agent_pack") or ""),
                summary=summary,
                tags=[str(item) for item in entry.get("tags", [])],
                total_steps=stats["total_steps"],
                agent_count=stats["agent_count"],
                command_count=0,
                image=str(entry.get("image") or ""),
                download_base_url=download_base_url,
            )
        )
    _write_collection_index(output_root, "experiments", "experiment.json")
    return manifests


def _write_collection_index(output_root: Path, collection: str, manifest_name: str) -> None:
    collection_root = output_root / collection
    items = []
    if collection_root.exists():
        for manifest_path in sorted(collection_root.glob(f"*/{manifest_name}")):
            try:
                item = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                items.append(item)
    _write_json(collection_root / "index.json", items)


def _experiment_pack_stats(experiment_root: Path) -> dict[str, int]:
    init_config = _load_structured_file(experiment_root / "init" / "init_config.json")
    steps_config = _load_structured_file(experiment_root / "init" / "steps.yaml")
    agents = init_config.get("agents") if isinstance(init_config.get("agents"), list) else []
    total_steps = 0
    raw_steps = steps_config.get("steps") if isinstance(steps_config.get("steps"), list) else []
    for step in raw_steps:
        if not isinstance(step, dict):
            continue
        if step.get("type") == "run":
            total_steps += int(step.get("num_steps") or 0)
        else:
            total_steps += 1
    return {"agent_count": len(agents), "total_steps": total_steps}


def _load_operator_commands_from_sqlite(db_path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if OPERATOR_COMMAND_TABLE_NAME not in _table_names(conn):
            return []
        rows = conn.execute(
            f"""
            SELECT command_id, type, step, simulation_time, prompt, target_json, result,
                   artifact_name, status
            FROM {_quote_identifier(OPERATOR_COMMAND_TABLE_NAME)}
            ORDER BY step, created_at, command_id
            """
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "command_id": str(row["command_id"]),
            "type": str(row["type"]),
            "step": int(row["step"]),
            "simulation_time": _timestamp_to_public(row["simulation_time"]),
            "prompt": str(row["prompt"] or ""),
            "target": _loads_json(row["target_json"], {}),
            "result": str(row["result"] or ""),
            "artifact_name": row["artifact_name"],
            "status": str(row["status"] or "completed"),
        }
        for row in rows
    ]


def _load_operator_commands_from_artifacts(artifacts_dir: Path) -> list[dict[str, Any]]:
    if not artifacts_dir.exists():
        return []

    commands: list[dict[str, Any]] = []
    for path in sorted(artifacts_dir.glob("*.md")):
        match = _ARTIFACT_RE.match(path.name)
        if match is None:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        metadata, body = _split_frontmatter(text)
        command_type = match.group("type")
        prompt_key = "question" if command_type == "ask" else "instruction"
        timestamp = datetime.strptime(
            match.group("date") + match.group("time"),
            "%Y%m%d%H%M%S",
        )
        target = metadata.get("target") if isinstance(metadata.get("target"), dict) else {}
        commands.append(
            {
                "command_id": path.stem,
                "type": command_type,
                "step": int(match.group("step")),
                "simulation_time": timestamp.isoformat(timespec="seconds"),
                "prompt": str(metadata.get(prompt_key) or ""),
                "target": target,
                "result": body.strip(),
                "artifact_name": path.name,
                "status": "completed",
            }
        )
    commands.sort(key=lambda item: (item["step"], item["simulation_time"], item["command_id"]))
    return commands


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        metadata = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return metadata, parts[2].lstrip()


def _load_dataset_catalog(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if DATASET_CATALOG_TABLE not in _table_names(conn):
        raise RuntimeError("Replay dataset catalog is missing from sqlite.db")

    dataset_rows = conn.execute(
        f"""
        SELECT dataset_id, table_name, module_name, kind, title, description,
               entity_key, step_key, time_key, default_order_json,
               capabilities_json, version, created_at
        FROM {_quote_identifier(DATASET_CATALOG_TABLE)}
        ORDER BY dataset_id
        """
    ).fetchall()
    datasets: dict[str, dict[str, Any]] = {}
    for row in dataset_rows:
        item = dict(row)
        item["default_order"] = _loads_json(item.pop("default_order_json"), [])
        item["capabilities"] = _loads_json(item.pop("capabilities_json"), [])
        item["columns"] = []
        datasets[item["dataset_id"]] = item

    if COLUMN_CATALOG_TABLE in _table_names(conn):
        column_rows = conn.execute(
            f"""
            SELECT dataset_id, column_name, sqlite_type, logical_type, analysis_role,
                   title, description, unit, enum_json, example_json, nullable, tags_json
            FROM {_quote_identifier(COLUMN_CATALOG_TABLE)}
            ORDER BY dataset_id, column_name
            """
        ).fetchall()
        for row in column_rows:
            item = dict(row)
            dataset_id = item.pop("dataset_id")
            item["enum_values"] = _loads_json(item.pop("enum_json"), None)
            item["example"] = _loads_json(item.pop("example_json"), None)
            item["tags"] = _loads_json(item.pop("tags_json"), [])
            item["nullable"] = bool(item["nullable"])
            if dataset_id in datasets:
                datasets[dataset_id]["columns"].append(item)

    return list(datasets.values())


def _load_timeline(conn: sqlite3.Connection, catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dataset = _select_timeline_dataset(catalog)
    if dataset is None:
        return []
    step_key = dataset.get("step_key")
    time_key = dataset.get("time_key")
    if not step_key or not time_key:
        return []

    rows = conn.execute(
        f"""
        SELECT {_quote_identifier(step_key)} AS step, MIN({_quote_identifier(time_key)}) AS t
        FROM {_quote_identifier(dataset["table_name"])}
        GROUP BY {_quote_identifier(step_key)}
        ORDER BY {_quote_identifier(step_key)}
        """
    ).fetchall()
    return [
        {"step": int(row["step"]), "t": _timestamp_to_public(row["t"])}
        for row in rows
        if row["step"] is not None and row["t"] is not None
    ]


def _load_agent_profiles(
    conn: sqlite3.Connection,
    catalog: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    profile_dataset = _select_dataset(
        catalog,
        capability=AGENT_PROFILE_DATASET_CAPABILITY,
        kind="entity_static",
    )
    if profile_dataset is not None:
        entity_key = profile_dataset.get("entity_key") or "id"
        rows = conn.execute(
            f"SELECT * FROM {_quote_identifier(profile_dataset['table_name'])} "
            f"ORDER BY {_quote_identifier(entity_key)}"
        ).fetchall()
        profiles: dict[int, dict[str, Any]] = {}
        for row in _normalize_rows(profile_dataset, rows):
            agent_id = int(row.get(entity_key))
            profile = _loads_json(row.get("profile"), {})
            name = str(row.get("name") or profile.get("name") or f"Agent_{agent_id}")
            profiles[agent_id] = {
                "id": agent_id,
                "name": name,
                "profile": profile if isinstance(profile, dict) else {},
            }
        if profiles:
            return profiles

    agent_dataset = _select_primary_agent_state_dataset(catalog)
    if agent_dataset is None:
        return {}
    entity_key = agent_dataset.get("entity_key") or "agent_id"
    rows = conn.execute(
        f"SELECT DISTINCT {_quote_identifier(entity_key)} AS id "
        f"FROM {_quote_identifier(agent_dataset['table_name'])} "
        f"ORDER BY {_quote_identifier(entity_key)}"
    ).fetchall()
    return {
        int(row["id"]): {"id": int(row["id"]), "name": f"Agent_{int(row['id'])}", "profile": {}}
        for row in rows
        if row["id"] is not None
    }


def _load_step_frame(
    conn: sqlite3.Connection,
    catalog: list[dict[str, Any]],
    step: int,
    profiles: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    agent_dataset = _select_primary_agent_state_dataset(catalog)
    env_dataset = _select_env_state_dataset(catalog)
    agents: list[dict[str, Any]] = []
    t: str | None = None
    if agent_dataset is not None:
        agent_rows = _fetch_step_rows(conn, agent_dataset, step)
        for row in agent_rows:
            if t is None and row.get(agent_dataset.get("time_key")) is not None:
                t = _timestamp_to_public(row.get(agent_dataset.get("time_key")))
            agents.append(_agent_frame(row, profiles))

    env: dict[str, Any] = {}
    if env_dataset is not None:
        env_rows = _fetch_step_rows(conn, env_dataset, step, limit=1)
        if env_rows:
            env = env_rows[0]
            if t is None and env.get(env_dataset.get("time_key")) is not None:
                t = _timestamp_to_public(env.get(env_dataset.get("time_key")))
            if isinstance(env.get("latest_communications"), str):
                env["latest_communications"] = _loads_json(env["latest_communications"], [])

    return {
        "step": step,
        "t": t,
        "agents": sorted(agents, key=lambda item: item["id"]),
        "env": env,
    }


def _agent_frame(row: dict[str, Any], profiles: dict[int, dict[str, Any]]) -> dict[str, Any]:
    agent_id = int(row.get("agent_id") or row.get("id"))
    profile = profiles.get(agent_id, {})
    return {
        "id": agent_id,
        "name": str(row.get("name") or profile.get("name") or f"Agent_{agent_id}"),
        "profile": profile.get("profile", {}),
        "location": row.get("location"),
        "location_id": row.get("location_id"),
        "tile_x": _optional_int(row.get("tile_x")),
        "tile_y": _optional_int(row.get("tile_y")),
        "action": row.get("action"),
        "status": row.get("status"),
        "emotion": row.get("emotion"),
        "message_count": _optional_int(row.get("message_count")) or 0,
        "last_message": row.get("last_message") or "",
        "recent_messages": _loads_json(row.get("recent_messages"), []),
        "nearby_agents": _loads_json(row.get("nearby_agents"), []),
        "current_phase": row.get("current_phase"),
        "latest_event": row.get("latest_event"),
        "movement_status": row.get("movement_status"),
        "target_location_id": row.get("target_location_id"),
        "path": _loads_json(row.get("path_json"), []),
        "movement_segment": _loads_json(row.get("movement_segment_json"), []),
        "movement_path_index": _optional_int(row.get("movement_path_index")),
        "movement_path_length": _optional_int(row.get("movement_path_length")),
        "available_interactions": _loads_json(row.get("available_interactions_json"), []),
    }


def _export_map_package(
    *,
    workspace_path: Path,
    hypothesis_id: str,
    experiment_id: str,
    replay_root: Path,
) -> dict[str, Any]:
    package = _resolve_experiment_map_package(
        workspace_path,
        hypothesis_id,
        experiment_id,
    )
    map_dir = replay_root / "map"
    assets_dir = map_dir / "assets"
    characters_dir = map_dir / "characters"
    location_assets_dir = map_dir / "location-assets"
    assets_dir.mkdir(parents=True)
    characters_dir.mkdir()
    location_assets_dir.mkdir()

    _, tiled_map = load_tiled_map(package)
    exported_tiled = json.loads(json.dumps(tiled_map))
    tilesets = []
    for index, tileset in enumerate(exported_tiled.get("tilesets", []) or []):
        if not isinstance(tileset, dict) or not tileset.get("image"):
            continue
        source = tileset_image_path(package, index)
        filename = f"tileset-{index}{source.suffix or '.png'}"
        shutil.copy2(source, assets_dir / filename)
        tileset["image"] = f"assets/{filename}"
        tilesets.append(
            {
                "name": str(tileset.get("name") or f"tileset-{index}"),
                "image_url": f"assets/{filename}",
            }
        )
    _write_json(map_dir / "tiled-map.json", exported_tiled)

    sprites = []
    for sprite in character_sprites(package):
        filename = Path(str(sprite["filename"])).name
        source = character_sprite_path(package, filename)
        shutil.copy2(source, characters_dir / filename)
        sprites.append(
            {
                "name": str(sprite["name"]),
                "image_url": f"characters/{filename}",
                "frame_width": int(sprite.get("frame_width") or package.tile_size),
                "frame_height": int(sprite.get("frame_height") or package.tile_size),
            }
        )

    locations = []
    for item in package.locations:
        location_id = str(item.get("id") or "")
        anchor = item.get("anchor_tile") or {}
        if not location_id or "x" not in anchor or "y" not in anchor:
            continue
        visual_asset_url = None
        if str(item.get("visual_asset") or "").strip():
            try:
                source = location_asset_path(package, location_id)
            except FileNotFoundError:
                source = None
            if source is not None and source.exists():
                filename = f"{location_id}{source.suffix or '.png'}"
                shutil.copy2(source, location_assets_dir / filename)
                visual_asset_url = f"location-assets/{filename}"
        locations.append(
            {
                "id": location_id,
                "name": str(item.get("name") or location_id),
                "aliases": [str(alias) for alias in item.get("aliases", []) or []],
                "localized": localized_metadata(item.get("localized")),
                "anchor_tile": {"x": int(anchor["x"]), "y": int(anchor["y"])},
                "scene_type": str(item.get("scene_type") or ""),
                "bounds": item.get("bounds") if isinstance(item.get("bounds"), dict) else None,
                "interaction_ids": [
                    str(value) for value in item.get("interaction_ids", []) or []
                ],
                "visual_asset_url": visual_asset_url,
            }
        )

    interactions = [
        {
            "id": str(item.get("id") or ""),
            "name": str(item.get("name") or item.get("id") or ""),
            "description": str(item.get("description") or ""),
            "localized": localized_metadata(item.get("localized")),
            "allowed_location_ids": [
                str(value) for value in item.get("allowed_location_ids", []) or []
            ],
        }
        for item in package.interactions
    ]

    preview_url = None
    preview_path = package.package_path / "visuals" / "preview.png"
    if preview_path.exists() and preview_path.is_file():
        shutil.copy2(preview_path, map_dir / "preview.png")
        preview_url = "preview.png"

    map_info = {
        "map_id": package.map_id,
        "display_name": package.display_name,
        "localized": localized_metadata(package.manifest.get("localized")),
        "tile_size": package.tile_size,
        "width": int(tiled_map.get("width") or 0),
        "height": int(tiled_map.get("height") or 0),
        "tiled_map_url": "tiled-map.json",
        "preview_url": preview_url,
        "tilesets": tilesets,
        "character_root_url": "characters/",
        "character_sprites": sprites,
        "locations": locations,
        "interactions": interactions,
    }
    _write_json(map_dir / "map.json", map_info)
    return {**map_info, "_package_path": str(package.package_path)}


def _publish_map_pack(
    *,
    output_root: Path,
    replay_root: Path,
    pack_id: str,
    map_info: dict[str, Any],
    original_package_path: Path,
    download_base_url: str | None = None,
) -> dict[str, Any]:
    pack_root = output_root / "map-packs" / pack_id
    if pack_root.exists():
        shutil.rmtree(pack_root)
    shutil.copytree(replay_root / "map", pack_root)

    manifest = {
        "schema_version": 1,
        "pack_id": pack_id,
        "map_id": map_info.get("map_id"),
        "display_name": map_info.get("display_name") or pack_id,
        "localized": map_info.get("localized") or {},
        "tile_size": map_info.get("tile_size"),
        "width": map_info.get("width"),
        "height": map_info.get("height"),
        "tiled_map_url": "tiled-map.json",
        "preview_url": map_info.get("preview_url"),
        "map_url": "map.json",
        "locations": map_info.get("locations") or [],
        "interactions": map_info.get("interactions") or [],
        "downloads": [
            {
                "type": "map",
                "label": "Map pack",
                "href": _download_href(download_base_url, f"{pack_id}-map-pack.zip"),
            }
        ],
    }
    _write_json(pack_root / "map_pack.json", manifest)
    downloads_dir = pack_root / "downloads"
    downloads_dir.mkdir()
    _zip_directory(original_package_path, downloads_dir / f"{pack_id}-map-pack.zip")
    return {
        **manifest,
        "_package_path": str(pack_root),
        "_original_package_path": str(original_package_path),
    }


def _export_agent_pack(
    *,
    output_root: Path,
    replay_root: Path,
    pack_id: str,
    display_name: str,
    profiles: list[dict[str, Any]],
    map_info: dict[str, Any],
    download_base_url: str | None = None,
) -> dict[str, Any]:
    pack_root = output_root / "agent-packs" / pack_id
    if pack_root.exists():
        shutil.rmtree(pack_root)
    agents_dir = pack_root / "agents"
    characters_dir = pack_root / "characters"
    agents_dir.mkdir(parents=True)
    characters_dir.mkdir()

    source_sprites = [
        sprite
        for sprite in map_info.get("character_sprites", []) or []
        if isinstance(sprite, dict) and str(sprite.get("image_url") or "").strip()
    ]
    sprite_entries: dict[str, dict[str, Any]] = {}
    for sprite in source_sprites:
        filename = Path(str(sprite["image_url"])).name
        source = replay_root / "map" / str(sprite["image_url"])
        if source.exists() and source.is_file():
            shutil.copy2(source, characters_dir / filename)
            sprite_entries[str(sprite.get("name") or Path(filename).stem)] = {
                "path": f"characters/{filename}",
                "frame_width": int(sprite.get("frame_width") or map_info.get("tile_size") or 32),
                "frame_height": int(sprite.get("frame_height") or map_info.get("tile_size") or 32),
            }

    agents = []
    for index, item in enumerate(profiles):
        agent_id = str(item.get("id") or index + 1)
        agent_name = str(item.get("name") or f"Agent {agent_id}")
        profile = item.get("profile") if isinstance(item.get("profile"), dict) else {}
        public_profile = {
            **profile,
            "id": int(agent_id) if agent_id.isdigit() else agent_id,
            "name": agent_name,
        }
        appearance = public_profile.get("appearance") if isinstance(public_profile.get("appearance"), dict) else {}
        requested_sprite = str(appearance.get("character_sprite") or "").strip()
        sprite_entry = sprite_entries.get(requested_sprite)
        if sprite_entry is None and source_sprites:
            fallback = source_sprites[index % len(source_sprites)]
            requested_sprite = str(fallback.get("name") or Path(str(fallback.get("image_url"))).stem)
            sprite_entry = sprite_entries.get(requested_sprite)
            public_profile["appearance"] = {
                **appearance,
                "character_sprite": requested_sprite,
                "character_sprite_filename": Path(str(fallback.get("image_url"))).name,
            }
        agent_dir = agents_dir / agent_id
        agent_dir.mkdir()
        _write_json(agent_dir / "profile.json", public_profile)
        runtime = {"agent_type": "JiuwenClawAgent", "kwargs": {}}
        _write_json(agent_dir / "runtime.json", runtime)
        manifest_agent = {
            "id": agent_id,
            "name": agent_name,
            "profile_path": f"agents/{agent_id}/profile.json",
            "runtime_path": f"agents/{agent_id}/runtime.json",
        }
        if sprite_entry is not None:
            manifest_agent["sprite"] = sprite_entry
        agents.append(manifest_agent)

    manifest = {
        "schema_version": 1,
        "pack_id": pack_id,
        "display_name": display_name,
        "agents": agents,
        "downloads": [
            {
                "type": "agent",
                "label": "Agent pack",
                "href": _download_href(download_base_url, f"{pack_id}-agent-pack.zip"),
            }
        ],
    }
    _write_json(pack_root / "agent_pack.json", manifest)
    (pack_root / "agent_pack.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    downloads_dir = pack_root / "downloads"
    downloads_dir.mkdir()
    _zip_directory(
        pack_root,
        downloads_dir / f"{pack_id}-agent-pack.zip",
        include=lambda path: _include_pack_file(path, pack_root),
    )
    return {**manifest, "_package_path": str(pack_root)}


def _export_experiment_pack(
    *,
    output_root: Path,
    experiment_root: Path,
    pack_id: str,
    display_name: str,
    replay_slug: str | None,
    map_pack_id: str,
    agent_pack_id: str,
    summary: str,
    tags: list[str],
    total_steps: int,
    agent_count: int,
    command_count: int,
    image: str | None = None,
    download_base_url: str | None = None,
) -> dict[str, Any]:
    pack_root = output_root / "experiments" / pack_id
    if pack_root.exists():
        shutil.rmtree(pack_root)
    pack_root.mkdir(parents=True)
    setup_summary = (
        f"Playable setup seed for {display_name}. "
        "Example replays are published separately as watchable results."
    ) if replay_slug else (summary or f"Playable setup seed for {display_name}.")
    manifest = {
        "schema_version": 1,
        "kind": "experiment",
        "pack_id": pack_id,
        "display_name": display_name,
        "summary": setup_summary,
        "tags": tags,
        "total_steps": total_steps,
        "agent_count": agent_count,
        "command_count": command_count,
        "urls": {},
        "downloads": [
            {
                "type": "experiment",
                "label": "Playable Experiment Pack",
                "description": "Scenario setup only; excludes replay history and local runtime state.",
                "href": _download_href(download_base_url, f"{pack_id}-experiment-pack.zip"),
            }
        ],
    }
    if map_pack_id:
        manifest["map_pack"] = map_pack_id
        manifest["urls"]["map_pack"] = f"../map-packs/{map_pack_id}/map_pack.json"
    if agent_pack_id:
        manifest["agent_pack"] = agent_pack_id
        manifest["urls"]["agent_pack"] = f"../agent-packs/{agent_pack_id}/agent_pack.json"
    if image:
        manifest["image"] = image
    if replay_slug:
        manifest["replay_slug"] = replay_slug
        manifest["example_replay"] = {
            "slug": replay_slug,
            "summary": summary,
            "total_steps": total_steps,
            "agent_count": agent_count,
            "command_count": command_count,
        }
        manifest["urls"]["replay"] = f"../replays/{replay_slug}/manifest.json"
    _write_json(pack_root / "experiment.json", manifest)
    downloads_dir = pack_root / "downloads"
    downloads_dir.mkdir()
    _zip_experiment_pack(
        experiment_root,
        downloads_dir / f"{pack_id}-experiment-pack.zip",
        map_id=map_pack_id or None,
    )
    return {**manifest, "_package_path": str(pack_root)}


def _resolve_experiment_map_package(
    workspace_path: Path,
    hypothesis_id: str,
    experiment_id: str,
) -> Any:
    config_path = (
        workspace_path
        / f"hypothesis_{hypothesis_id}"
        / f"experiment_{experiment_id}"
        / "init"
        / "init_config.json"
    )
    config = _load_structured_file(config_path)
    env_modules = config.get("env_modules") or []
    manifest_path: Path | None = None
    map_id: str | None = None
    if isinstance(env_modules, list):
        for item in env_modules:
            if not isinstance(item, dict) or item.get("module_type") != "PixelTownSocialEnv":
                continue
            kwargs = item.get("kwargs") if isinstance(item.get("kwargs"), dict) else {}
            if kwargs.get("map_id"):
                map_id = str(kwargs["map_id"])
            raw_path = kwargs.get("map_manifest_path")
            if raw_path:
                path = Path(str(raw_path)).expanduser()
                manifest_path = path if path.is_absolute() else (_repo_root_from_workspace(workspace_path) / path).resolve()
                break
    if manifest_path is not None and manifest_path.exists():
        return load_map_package_by_manifest(manifest_path)
    return load_map_package(map_id or DEFAULT_MAP_ID, _repo_root_from_workspace(workspace_path))


def _repo_root_from_workspace(workspace_path: Path) -> Path:
    workspace = workspace_path.resolve()
    return workspace.parent if workspace.name == "quick_experiments" else workspace


def _load_structured_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in {path}")
    return data


def _create_downloads(
    *,
    replay_root: Path,
    experiment_root: Path,
    map_package_path: Path,
    agent_pack_root: Path,
    slug: str,
    map_id: str,
    download_base_url: str | None = None,
) -> list[dict[str, str]]:
    downloads = [
        {
            "type": "replay",
            "label": "Replay archive",
            "description": "Static timeline, step frames, commands, profiles, and replay manifest.",
            "hidden": True,
            "href": _download_href(download_base_url, f"{slug}-replay-data.zip"),
        },
        {
            "type": "map",
            "label": "Map pack",
            "href": _download_href(download_base_url, f"{map_id}-map-pack.zip"),
        },
        {
            "type": "agent",
            "label": "Agent pack",
            "href": _download_href(download_base_url, f"{slug}-agent-pack.zip"),
        },
        {
            "type": "experiment",
            "label": "Playable Experiment Pack",
            "description": "Scenario setup only; excludes replay history and local runtime state.",
            "href": _download_href(download_base_url, f"{slug}-experiment-pack.zip"),
        },
    ]
    downloads_dir = replay_root / "downloads"
    _zip_directory(
        replay_root,
        downloads_dir / f"{slug}-replay-data.zip",
        include=lambda path: _include_replay_data_file(path, replay_root),
    )
    _zip_directory(map_package_path, downloads_dir / f"{map_id}-map-pack.zip")
    _zip_directory(
        agent_pack_root,
        downloads_dir / f"{slug}-agent-pack.zip",
        include=lambda path: _include_pack_file(path, agent_pack_root),
    )
    _zip_experiment_pack(
        experiment_root,
        downloads_dir / f"{slug}-experiment-pack.zip",
        map_id=map_id,
    )
    return downloads


def _include_experiment_pack_file(path: Path, experiment_root: Path) -> bool:
    rel = path.relative_to(experiment_root)
    parts = rel.parts
    if not parts:
        return True
    if _is_runtime_state_path(parts):
        return False
    if ".runtime" in parts:
        return False
    if path.suffix in {".db", ".sqlite", ".sqlite3", ".log"}:
        return False
    return (
        path.is_dir()
        or path.name in {"README.md", "README.zh-CN.md", "OPERATOR_SCRIPT.md", "run.sh"}
        or parts[:1] == ("init",)
    )


def _is_runtime_state_path(parts: tuple[str, ...]) -> bool:
    if not parts:
        return False
    name = parts[0]
    return (
        name == "run"
        or name.startswith("run_")
        or name.startswith("run_failed")
        or name.startswith("run_stuck")
    )


def _include_replay_data_file(path: Path, replay_root: Path) -> bool:
    rel = path.relative_to(replay_root)
    parts = rel.parts
    if "downloads" in parts:
        return False
    if len(parts) >= 2 and parts[0] == "map" and parts[1] in {
        "assets",
        "characters",
        "location-assets",
    }:
        return False
    if parts == ("map", "preview.png"):
        return False
    return True


def _include_pack_file(path: Path, pack_root: Path) -> bool:
    parts = path.relative_to(pack_root).parts
    return "downloads" not in parts


def _download_href(download_base_url: str | None, filename: str) -> str:
    if not download_base_url:
        return f"downloads/{filename}"
    return download_base_url.rstrip("/") + "/" + filename


def _zip_experiment_pack(source_dir: Path, zip_path: Path, *, map_id: str | None = None) -> None:
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path == zip_path:
                continue
            if path.name.startswith("."):
                continue
            if not _include_experiment_pack_file(path, source_dir):
                continue
            if path.is_dir():
                continue
            rel = path.relative_to(source_dir)
            if rel.parts == ("init", "init_config.json"):
                config = _load_structured_file(path)
                safe_config = sanitize_experiment_pack_config(config, map_id=map_id)
                archive.writestr(
                    rel.as_posix(),
                    json.dumps(safe_config, ensure_ascii=False, indent=2) + "\n",
                )
                continue
            archive.write(path, rel)


def _zip_directory(
    source_dir: Path,
    zip_path: Path,
    *,
    include: Any | None = None,
) -> None:
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path == zip_path:
                continue
            if path.name.startswith("."):
                continue
            if "downloads" in path.relative_to(source_dir).parts:
                continue
            if include is not None and not include(path):
                continue
            if path.is_dir():
                continue
            archive.write(path, path.relative_to(source_dir))


def _fetch_step_rows(
    conn: sqlite3.Connection,
    dataset: dict[str, Any],
    step: int,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    step_key = dataset.get("step_key")
    if not step_key:
        return []
    order_columns = [
        column for column in dataset.get("default_order", []) if column in _column_names(dataset)
    ] or [step_key]
    sql = (
        f"SELECT * FROM {_quote_identifier(dataset['table_name'])} "
        f"WHERE {_quote_identifier(step_key)} = ? "
        f"ORDER BY {', '.join(_quote_identifier(column) for column in order_columns)}"
    )
    params: tuple[Any, ...] = (step,)
    if limit is not None:
        sql += " LIMIT ?"
        params = (step, limit)
    rows = conn.execute(sql, params).fetchall()
    return _normalize_rows(dataset, rows)


def _normalize_rows(dataset: dict[str, Any], rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    column_types = {
        str(column["column_name"]): str(column.get("sqlite_type") or "").upper()
        for column in dataset.get("columns", [])
    }
    normalized = []
    for row in rows:
        item = dict(row)
        for key, value in list(item.items()):
            if column_types.get(key) == "JSON":
                item[key] = _loads_json(value, value)
            elif isinstance(value, bytes):
                item[key] = value.decode("utf-8", errors="replace")
        normalized.append(item)
    return normalized


def _select_dataset(
    catalog: list[dict[str, Any]],
    *,
    capability: str,
    kind: str | None = None,
) -> dict[str, Any] | None:
    matches = [
        dataset
        for dataset in catalog
        if capability in dataset.get("capabilities", [])
        and (kind is None or dataset.get("kind") == kind)
    ]
    matches.sort(key=lambda dataset: str(dataset.get("dataset_id") or ""))
    return matches[0] if matches else None


def _select_primary_agent_state_dataset(catalog: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [
        dataset
        for dataset in catalog
        if dataset.get("kind") == "entity_snapshot"
        and "agent_snapshot" in dataset.get("capabilities", [])
        and dataset.get("entity_key")
        and dataset.get("step_key")
    ]
    matches.sort(key=lambda dataset: str(dataset.get("dataset_id") or ""))
    return matches[0] if matches else None


def _select_env_state_dataset(catalog: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [
        dataset
        for dataset in catalog
        if dataset.get("kind") == "env_snapshot"
        and "env_snapshot" in dataset.get("capabilities", [])
        and dataset.get("step_key")
    ]
    matches.sort(key=lambda dataset: str(dataset.get("dataset_id") or ""))
    return matches[0] if matches else None


def _select_timeline_dataset(catalog: list[dict[str, Any]]) -> dict[str, Any] | None:
    primary = _select_primary_agent_state_dataset(catalog)
    if primary is not None and primary.get("step_key") and primary.get("time_key"):
        return primary
    env = _select_env_state_dataset(catalog)
    if env is not None and env.get("step_key") and env.get("time_key"):
        return env
    return None


def _column_names(dataset: dict[str, Any]) -> set[str]:
    return {str(column["column_name"]) for column in dataset.get("columns", [])}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row["name"]) for row in rows}


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _loads_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def _timestamp_to_public(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value).replace(" ", "T", 1)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
