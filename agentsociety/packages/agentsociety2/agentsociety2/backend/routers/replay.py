"""
Replay data query API for simulation playback.

关联文件：
- @extension/src/replayWebviewProvider.ts - VSCode Replay Webview provider
- @extension/src/webview/replay/ - VSCode Replay Webview React app
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import func, select
import yaml

from ...backend.services.replay_catalog import (
    fetch_dataset_rows,
    get_dataset_by_id,
    load_dataset_catalog,
    query_dataset_rows,
    reflect_dataset_table,
)
from ...backend.services.map_packages import (
    DEFAULT_MAP_ID,
    character_sprite_path,
    character_sprites,
    load_map_package,
    load_map_package_by_manifest,
    load_tiled_map,
    location_asset_path,
    localized_metadata,
    tileset_image_path,
)
from ...storage.replay_metadata import AGENT_PROFILE_DATASET_CAPABILITY

router = APIRouter(prefix="/replay", tags=["replay"])
_DB_CACHE_LOCK = asyncio.Lock()
_DB_SESSIONMAKER_CACHE: dict[str, tuple[int, AsyncEngine, sessionmaker]] = {}


class ExperimentInfo(BaseModel):
    hypothesis_id: str
    experiment_id: str
    total_steps: int
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    agent_count: int


class TimelinePoint(BaseModel):
    step: int
    t: datetime


class AgentProfile(BaseModel):
    id: int
    name: str
    profile: Dict[str, Any] = Field(default_factory=dict)


class ReplayDatasetColumn(BaseModel):
    column_name: str
    sqlite_type: str
    logical_type: Optional[str] = None
    analysis_role: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    nullable: bool
    enum_values: Optional[Any] = None
    example: Optional[Any] = None
    tags: List[str] = Field(default_factory=list)


class ReplayDatasetInfo(BaseModel):
    dataset_id: str
    table_name: str
    module_name: str
    kind: str
    title: str = ""
    description: str = ""
    entity_key: Optional[str] = None
    step_key: Optional[str] = None
    time_key: Optional[str] = None
    default_order: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    version: int
    created_at: datetime
    columns: List[ReplayDatasetColumn] = Field(default_factory=list)


class ReplayDatasetList(BaseModel):
    datasets: List[ReplayDatasetInfo]


class ReplayDatasetRows(BaseModel):
    dataset_id: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    total: int


class ReplayPanelSchema(BaseModel):
    agent_profile_dataset: Optional[ReplayDatasetInfo] = None
    agent_state_datasets: List[ReplayDatasetInfo] = Field(default_factory=list)
    env_state_datasets: List[ReplayDatasetInfo] = Field(default_factory=list)
    geo_dataset: Optional[ReplayDatasetInfo] = None
    primary_agent_state_dataset_id: Optional[str] = None
    layout_hint: Literal["map", "random"] = "random"
    supports_map: bool = False


class ReplayMapTileset(BaseModel):
    name: str
    image_url: str


class ReplayMapCharacter(BaseModel):
    name: str
    image_url: str
    frame_width: int = 32
    frame_height: int = 32


class ReplayMapLocation(BaseModel):
    id: str
    name: str
    aliases: List[str] = Field(default_factory=list)
    localized: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    anchor_tile: Dict[str, int]
    scene_type: str = ""
    bounds: Optional[Dict[str, int]] = None
    interaction_ids: List[str] = Field(default_factory=list)
    visual_asset_url: Optional[str] = None
    visual_note: str = ""


class ReplayMapInteraction(BaseModel):
    id: str
    name: str
    description: str = ""
    localized: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    allowed_location_ids: List[str] = Field(default_factory=list)


class ReplayMapInfo(BaseModel):
    map_id: str
    display_name: str
    localized: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    tile_size: int = 32
    width: int
    height: int
    tiled_map_url: str
    preview_url: Optional[str] = None
    tilesets: List[ReplayMapTileset] = Field(default_factory=list)
    character_root_url: Optional[str] = None
    character_sprites: List[ReplayMapCharacter] = Field(default_factory=list)
    locations: List[ReplayMapLocation] = Field(default_factory=list)
    interactions: List[ReplayMapInteraction] = Field(default_factory=list)


class ReplayDatasetPanelRef(BaseModel):
    dataset_id: str
    module_name: str
    title: str = ""


class ReplayPosition(BaseModel):
    agent_id: int
    lng: Optional[float] = None
    lat: Optional[float] = None


class ReplayAgentStateAtStep(BaseModel):
    dataset: ReplayDatasetPanelRef
    rows_by_agent_id: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class ReplayEnvStateAtStep(BaseModel):
    dataset: ReplayDatasetPanelRef
    row: Optional[Dict[str, Any]] = None


class ReplayStepBundle(BaseModel):
    step: int
    t: Optional[datetime] = None
    layout_hint: Literal["map", "random"] = "random"
    positions: List[ReplayPosition] = Field(default_factory=list)
    agent_state_rows: Dict[str, ReplayAgentStateAtStep] = Field(default_factory=dict)
    env_state_rows: Dict[str, ReplayEnvStateAtStep] = Field(default_factory=dict)


class ReplayTokenUsage(BaseModel):
    call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class ReplayAgentRuntimeState(BaseModel):
    agent_id: int
    work_dir: Optional[str] = None
    agent_config: Dict[str, Any] = Field(default_factory=dict)
    session_state: Dict[str, Any] = Field(default_factory=dict)
    agent_state_snapshot: Dict[str, Any] = Field(default_factory=dict)
    token_usage: Dict[str, ReplayTokenUsage] = Field(default_factory=dict)
    state_files: Dict[str, Any] = Field(default_factory=dict)
    recent_messages: List[Dict[str, Any]] = Field(default_factory=list)
    recent_tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    recent_step_replays: List[Dict[str, Any]] = Field(default_factory=list)
    compact_state: Dict[str, Any] = Field(default_factory=dict)
    agent_markdown: Optional[str] = None


def get_db_path(workspace_path: str, hypothesis_id: str, experiment_id: str) -> Path:
    return (
        Path(workspace_path)
        / f"hypothesis_{hypothesis_id}"
        / f"experiment_{experiment_id}"
        / "run"
        / "sqlite.db"
    )


def get_run_dir(workspace_path: str, hypothesis_id: str, experiment_id: str) -> Path:
    return get_db_path(workspace_path, hypothesis_id, experiment_id).parent


def get_init_config_path(workspace_path: str, hypothesis_id: str, experiment_id: str) -> Path:
    return (
        Path(workspace_path)
        / f"hypothesis_{hypothesis_id}"
        / f"experiment_{experiment_id}"
        / "init"
        / "init_config.json"
    )


def _read_text(path: Path, *, max_chars: Optional[int] = 12000) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if max_chars is None or len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


def _read_json_file(
    path: Path,
    default: Any,
    *,
    max_chars: Optional[int] = 50000,
) -> Any:
    text = _read_text(path, max_chars=max_chars)
    if text is None or text.strip() == "":
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def _read_jsonl(path: Path, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    text = _read_text(path, max_chars=None)
    if text is None:
        return []
    rows: List[Dict[str, Any]] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if limit is not None:
        lines = lines[-limit:]
    for line in lines:
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            parsed = {"raw": line}
        if isinstance(parsed, dict):
            rows.append(parsed)
        else:
            rows.append({"value": parsed})
    return rows


def _resolve_agent_work_dir(run_dir: Path, agent_id: int) -> Optional[Path]:
    agents_dir = run_dir / "agents"
    candidates = [
        agents_dir / f"agent_{agent_id:04d}",
        agents_dir / f"agent_{agent_id}",
        agents_dir / str(agent_id),
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    if not agents_dir.exists():
        return None
    suffix = str(agent_id)
    for candidate in sorted(agents_dir.glob("agent_*")):
        if candidate.is_dir() and candidate.name.lstrip("agent_").lstrip("0") == suffix:
            return candidate
    return None


def _token_usage_from_session(state: Dict[str, Any]) -> Dict[str, ReplayTokenUsage]:
    raw_usage = state.get("token_usage")
    if not isinstance(raw_usage, dict):
        return {}
    usage: Dict[str, ReplayTokenUsage] = {}
    for model_name, raw_stats in raw_usage.items():
        if not isinstance(raw_stats, dict):
            continue
        usage[str(model_name)] = ReplayTokenUsage(
            call_count=int(raw_stats.get("call_count") or raw_stats.get("calls") or 0),
            input_tokens=int(
                raw_stats.get("input_tokens") or raw_stats.get("prompt_tokens") or 0
            ),
            output_tokens=int(
                raw_stats.get("output_tokens")
                or raw_stats.get("completion_tokens")
                or 0
            ),
        )
    return usage


def _token_usage_from_log(run_dir: Path, agent_id: int) -> Dict[str, ReplayTokenUsage]:
    pattern = re.compile(
        rf"Agent\s+{agent_id}\s+token usage - model=(?P<model>\S+) "
        rf"calls=(?P<calls>\d+) input=(?P<input>\d+) output=(?P<output>\d+)"
    )
    usage: Dict[str, ReplayTokenUsage] = {}
    for log_path in sorted(run_dir.glob("*.log")):
        text = _read_text(log_path, max_chars=None)
        if text is None:
            continue
        for match in pattern.finditer(text):
            usage[match.group("model")] = ReplayTokenUsage(
                call_count=int(match.group("calls")),
                input_tokens=int(match.group("input")),
                output_tokens=int(match.group("output")),
            )
    return usage


async def _get_cached_sessionmaker(db_path: Path) -> tuple[sessionmaker, int]:
    resolved_path = db_path.resolve()
    if not resolved_path.exists():
        raise HTTPException(status_code=404, detail=f"Database not found: {db_path}")

    cache_key = str(resolved_path)
    mtime_ns = resolved_path.stat().st_mtime_ns

    async with _DB_CACHE_LOCK:
        cached = _DB_SESSIONMAKER_CACHE.get(cache_key)
        if cached is not None:
            cached_mtime_ns, engine, cached_sessionmaker = cached
            if cached_mtime_ns == mtime_ns:
                return cached_sessionmaker, mtime_ns
            await engine.dispose()

        engine = create_async_engine(
            f"sqlite+aiosqlite:///{resolved_path}",
            echo=False,
        )
        async_session = sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        _DB_SESSIONMAKER_CACHE[cache_key] = (mtime_ns, engine, async_session)
        return async_session, mtime_ns


async def get_db_session(db_path: Path):
    async_session, mtime_ns = await _get_cached_sessionmaker(db_path)
    async with async_session() as session:
        session.info["replay_db_path"] = str(db_path.resolve())
        session.info["replay_db_mtime_ns"] = mtime_ns
        yield session


def _dataset_to_response(dataset: Dict[str, Any]) -> ReplayDatasetInfo:
    return ReplayDatasetInfo.model_validate(dataset)


def _dataset_ref(dataset: Dict[str, Any]) -> ReplayDatasetPanelRef:
    return ReplayDatasetPanelRef(
        dataset_id=dataset["dataset_id"],
        module_name=dataset.get("module_name") or "",
        title=dataset.get("title") or "",
    )


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _load_structured_file(path: Path) -> Dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() in {".yaml", ".yml"}:
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail=f"Expected object in {path}")
    return data


def _repo_root_from_workspace(workspace_path: str) -> Path:
    workspace = Path(workspace_path).resolve()
    return workspace.parent if workspace.name == "quick_experiments" else workspace


def _resolve_experiment_map_package(
    workspace_path: str,
    hypothesis_id: str,
    experiment_id: str,
) -> Any:
    config_path = get_init_config_path(workspace_path, hypothesis_id, experiment_id)
    config = _load_structured_file(config_path)
    env_modules = config.get("env_modules") or []
    manifest_path: Optional[Path] = None
    map_id: Optional[str] = None
    if isinstance(env_modules, list):
        for item in env_modules:
            if not isinstance(item, dict) or item.get("module_type") != "PixelTownSocialEnv":
                continue
            kwargs = item.get("kwargs") if isinstance(item.get("kwargs"), dict) else {}
            if kwargs.get("map_id"):
                map_id = str(kwargs.get("map_id"))
            raw_path = kwargs.get("map_manifest_path")
            if raw_path:
                path = Path(str(raw_path)).expanduser()
                manifest_path = path if path.is_absolute() else (_repo_root_from_workspace(workspace_path) / path).resolve()
                break
    try:
        if manifest_path is not None and manifest_path.exists():
            return load_map_package_by_manifest(manifest_path)
        return load_map_package(map_id or DEFAULT_MAP_ID, _repo_root_from_workspace(workspace_path))
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Map package not found: {exc}") from exc


def _resolve_experiment_map_manifest(
    workspace_path: str,
    hypothesis_id: str,
    experiment_id: str,
) -> tuple[Path, Dict[str, Any]]:
    package = _resolve_experiment_map_package(workspace_path, hypothesis_id, experiment_id)
    return package.manifest_path, package.manifest


def _map_base_url(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str,
    suffix: str,
) -> str:
    return (
        f"/api/v1/replay/{quote(hypothesis_id)}/{quote(experiment_id)}{suffix}"
        f"?workspace_path={quote(str(Path(workspace_path).resolve()))}"
    )


def _map_info_response(
    workspace_path: str,
    hypothesis_id: str,
    experiment_id: str,
) -> ReplayMapInfo:
    package = _resolve_experiment_map_package(
        workspace_path,
        hypothesis_id,
        experiment_id,
    )
    manifest_path = package.manifest_path
    manifest = package.manifest
    tiled_map_path, tiled_map = load_tiled_map(package)
    preview_path = package.package_path / "visuals" / "preview.png"
    tilesets: list[ReplayMapTileset] = []
    for index, tileset in enumerate(tiled_map.get("tilesets", []) or []):
        if not isinstance(tileset, dict):
            continue
        name = str(tileset.get("name") or "").strip()
        image = str(tileset.get("image") or "").strip()
        if not name or not image:
            continue
        try:
            image_path = tileset_image_path(package, index)
        except Exception:
            continue
        tilesets.append(
            ReplayMapTileset(
                name=name,
                image_url=_map_base_url(
                    hypothesis_id,
                    experiment_id,
                    workspace_path,
                    f"/map/assets/{index}",
                ),
            )
        )

    sprites = [
        ReplayMapCharacter(
            name=str(sprite["name"]),
            image_url=_map_base_url(
                hypothesis_id,
                experiment_id,
                workspace_path,
                f"/map/characters/{quote(str(sprite['filename']))}",
            ),
            frame_width=int(sprite.get("frame_width") or package.tile_size),
            frame_height=int(sprite.get("frame_height") or package.tile_size),
        )
        for sprite in character_sprites(package)
    ]

    locations: list[ReplayMapLocation] = []
    for item in manifest.get("locations", []) or []:
        if not isinstance(item, dict):
            continue
        anchor = item.get("anchor_tile") or {}
        if "x" not in anchor or "y" not in anchor:
            continue
        location_id = str(item.get("id") or "")
        visual_asset_url: Optional[str] = None
        visual_asset = str(item.get("visual_asset") or "").strip()
        if visual_asset:
            try:
                visual_path = location_asset_path(package, location_id)
            except Exception:
                visual_path = None
            if visual_path is not None and visual_path.exists() and visual_path.is_file():
                visual_asset_url = _map_base_url(
                    hypothesis_id,
                    experiment_id,
                    workspace_path,
                    f"/map/location-assets/{quote(location_id)}",
                )
        locations.append(
            ReplayMapLocation(
                id=location_id,
                name=str(item.get("name") or item.get("id") or ""),
                aliases=[str(alias) for alias in item.get("aliases", []) or []],
                localized=localized_metadata(item.get("localized")),
                anchor_tile={"x": int(anchor["x"]), "y": int(anchor["y"])},
                scene_type=str(item.get("scene_type") or ""),
                bounds=(
                    {
                        "x": int(item["bounds"]["x"]),
                        "y": int(item["bounds"]["y"]),
                        "w": int(item["bounds"]["w"]),
                        "h": int(item["bounds"]["h"]),
                    }
                    if isinstance(item.get("bounds"), dict)
                    and all(key in item["bounds"] for key in ("x", "y", "w", "h"))
                    else None
                ),
                interaction_ids=[str(value) for value in item.get("interaction_ids", []) or []],
                visual_asset_url=visual_asset_url,
                visual_note=str(item.get("visual_note") or ""),
            )
        )

    interactions: list[ReplayMapInteraction] = []
    for item in manifest.get("interactions", []) or []:
        if not isinstance(item, dict):
            continue
        interactions.append(
            ReplayMapInteraction(
                id=str(item.get("id") or ""),
                name=str(item.get("name") or item.get("id") or ""),
                description=str(item.get("description") or ""),
                localized=localized_metadata(item.get("localized")),
                allowed_location_ids=[
                    str(value) for value in item.get("allowed_location_ids", []) or []
                ],
            )
        )

    return ReplayMapInfo(
        map_id=str(manifest.get("map_id") or manifest_path.parent.name),
        display_name=str(manifest.get("display_name") or manifest.get("map_id") or "Pixel Town"),
        localized=localized_metadata(manifest.get("localized")),
        tile_size=int(manifest.get("tile_size") or tiled_map.get("tilewidth") or 32),
        width=int(tiled_map.get("width") or 0),
        height=int(tiled_map.get("height") or 0),
        tiled_map_url=_map_base_url(
            hypothesis_id,
            experiment_id,
            workspace_path,
            "/map/tiled",
        ),
        preview_url=(
            _map_base_url(
                hypothesis_id,
                experiment_id,
                workspace_path,
                "/map/preview",
            )
            if preview_path.exists() and preview_path.is_file()
            else None
        ),
        tilesets=tilesets,
        character_root_url=_map_base_url(
            hypothesis_id,
            experiment_id,
            workspace_path,
            "/map/characters",
        ),
        character_sprites=sprites,
        locations=locations,
        interactions=interactions,
    )


def _dataset_has_columns(dataset: Dict[str, Any], *column_names: str) -> bool:
    available = {column["column_name"] for column in dataset.get("columns", [])}
    return all(column_name in available for column_name in column_names)


def _split_columns_param(raw_columns: Optional[str]) -> Optional[List[str]]:
    if raw_columns is None:
        return None
    columns = [column.strip() for column in raw_columns.split(",") if column.strip()]
    return columns or None


def _list_agent_state_datasets(datasets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = [
        dataset
        for dataset in datasets
        if dataset.get("kind") == "entity_snapshot"
        and "agent_snapshot" in dataset.get("capabilities", [])
        and dataset.get("entity_key")
        and dataset.get("step_key")
    ]
    items.sort(key=lambda item: item["dataset_id"])
    return items


def _list_env_state_datasets(datasets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = [
        dataset
        for dataset in datasets
        if dataset.get("kind") == "env_snapshot"
        and "env_snapshot" in dataset.get("capabilities", [])
        and dataset.get("step_key")
    ]
    items.sort(key=lambda item: item["dataset_id"])
    return items


def _select_geo_dataset(datasets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    candidates = [
        dataset
        for dataset in _list_agent_state_datasets(datasets)
        if "geo_point" in dataset.get("capabilities", [])
        and _dataset_has_columns(dataset, "lng", "lat")
    ]
    candidates.sort(key=lambda item: item["dataset_id"])
    return candidates[0] if candidates else None


def _select_tile_dataset(datasets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    candidates = [
        dataset
        for dataset in _list_agent_state_datasets(datasets)
        if "tile_point" in dataset.get("capabilities", [])
        and _dataset_has_columns(dataset, "tile_x", "tile_y")
    ]
    candidates.sort(key=lambda item: item["dataset_id"])
    return candidates[0] if candidates else None


def _select_primary_agent_state_dataset(
    datasets: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    agent_state_datasets = _list_agent_state_datasets(datasets)
    if not agent_state_datasets:
        return None

    non_geo_candidates = [
        dataset
        for dataset in agent_state_datasets
        if "geo_point" not in dataset.get("capabilities", [])
    ]
    candidates = non_geo_candidates or agent_state_datasets
    candidates.sort(key=lambda item: item["dataset_id"])
    return candidates[0]


def _select_timeline_dataset(
    datasets: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    primary_agent_state = _select_primary_agent_state_dataset(datasets)
    if (
        primary_agent_state is not None
        and primary_agent_state.get("step_key")
        and primary_agent_state.get("time_key")
    ):
        return primary_agent_state

    agent_candidates = [
        dataset
        for dataset in _list_agent_state_datasets(datasets)
        if dataset.get("step_key") and dataset.get("time_key")
    ]
    agent_candidates.sort(
        key=lambda item: (
            0 if "geo_point" not in item.get("capabilities", []) else 1,
            item["dataset_id"],
        )
    )
    if agent_candidates:
        return agent_candidates[0]

    env_candidates = [
        dataset
        for dataset in _list_env_state_datasets(datasets)
        if dataset.get("step_key") and dataset.get("time_key")
    ]
    env_candidates.sort(key=lambda item: item["dataset_id"])
    return env_candidates[0] if env_candidates else None


def _find_time_value(
    rows: List[Dict[str, Any]],
    time_key: Optional[str],
) -> Optional[datetime]:
    if not time_key:
        return None
    for row in rows:
        timestamp = _coerce_datetime(row.get(time_key))
        if timestamp is not None:
            return timestamp
    return None


def _build_positions_from_step_rows(
    geo_dataset: Optional[Dict[str, Any]],
    agent_state_groups: Dict[str, ReplayAgentStateAtStep],
) -> List[ReplayPosition]:
    agent_ids: set[int] = set()
    for group in agent_state_groups.values():
        for raw_agent_id in group.rows_by_agent_id.keys():
            try:
                agent_ids.add(int(raw_agent_id))
            except (TypeError, ValueError):
                continue

    positions_by_agent_id: Dict[int, ReplayPosition] = {
        agent_id: ReplayPosition(agent_id=agent_id, lng=None, lat=None)
        for agent_id in sorted(agent_ids)
    }
    if geo_dataset is None:
        return list(positions_by_agent_id.values())

    geo_group = agent_state_groups.get(geo_dataset["dataset_id"])
    if geo_group is None:
        return list(positions_by_agent_id.values())

    for raw_agent_id, row in geo_group.rows_by_agent_id.items():
        try:
            agent_id = int(raw_agent_id)
        except (TypeError, ValueError):
            continue
        positions_by_agent_id[agent_id] = ReplayPosition(
            agent_id=agent_id,
            lng=row.get("lng"),
            lat=row.get("lat"),
        )
    return list(positions_by_agent_id.values())


async def _get_agent_profile_dataset(
    session: AsyncSession,
    datasets: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    catalog = datasets or await load_dataset_catalog(session)
    candidates = [
        dataset
        for dataset in catalog
        if AGENT_PROFILE_DATASET_CAPABILITY in dataset.get("capabilities", [])
        and dataset.get("entity_key")
    ]
    candidates.sort(key=lambda item: item["dataset_id"])
    return candidates[0] if candidates else None


def _parse_profile_payload(raw_profile: Any) -> Dict[str, Any]:
    if isinstance(raw_profile, dict):
        return raw_profile
    if isinstance(raw_profile, str):
        try:
            decoded = json.loads(raw_profile)
        except json.JSONDecodeError:
            return {"raw": raw_profile}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _resolve_agent_name(agent_id: int, row: Dict[str, Any], profile: Dict[str, Any]) -> str:
    name = row.get("name")
    if isinstance(name, str) and name.strip():
        return name
    profile_name = profile.get("name")
    if isinstance(profile_name, str) and profile_name.strip():
        return profile_name
    return f"Agent_{agent_id}"


async def _load_agent_profiles(
    session: AsyncSession,
    datasets: Optional[List[Dict[str, Any]]] = None,
) -> Dict[int, AgentProfile]:
    catalog = datasets or await load_dataset_catalog(session)
    profile_dataset = await _get_agent_profile_dataset(session, catalog)
    if profile_dataset is not None:
        table = await reflect_dataset_table(session, profile_dataset)
        entity_key = profile_dataset["entity_key"]
        if entity_key in table.c:
            query = select(table).order_by(table.c[entity_key])
            result = await session.execute(query)
            profiles: Dict[int, AgentProfile] = {}
            for row in result.mappings().all():
                raw_id = row.get(entity_key)
                if raw_id is None:
                    continue
                agent_id = int(raw_id)
                profile_payload = _parse_profile_payload(row.get("profile"))
                profiles[agent_id] = AgentProfile(
                    id=agent_id,
                    name=_resolve_agent_name(agent_id, dict(row), profile_payload),
                    profile=profile_payload,
                )
            if profiles:
                return profiles

    identity_dataset = _select_primary_agent_state_dataset(catalog)
    if identity_dataset is None:
        return {}

    table = await reflect_dataset_table(session, identity_dataset)
    entity_key = identity_dataset["entity_key"]
    if entity_key not in table.c:
        return {}

    result = await session.execute(
        select(table.c[entity_key]).distinct().order_by(table.c[entity_key])
    )
    return {
        int(agent_id): AgentProfile(
            id=int(agent_id),
            name=f"Agent_{int(agent_id)}",
            profile={},
        )
        for (agent_id,) in result.all()
        if agent_id is not None
    }


async def _get_experiment_summary(
    session: AsyncSession,
    datasets: List[Dict[str, Any]],
) -> tuple[int, Optional[datetime], Optional[datetime], int]:
    timeline_dataset = _select_timeline_dataset(datasets)
    total_steps = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    if timeline_dataset is not None:
        table = await reflect_dataset_table(session, timeline_dataset)
        step_key = timeline_dataset["step_key"]
        time_key = timeline_dataset["time_key"]
        if step_key in table.c and time_key in table.c:
            total_steps = (
                await session.execute(
                    select(func.count(func.distinct(table.c[step_key])))
                )
            ).scalar() or 0
            start_time = _coerce_datetime(
                (await session.execute(select(func.min(table.c[time_key])))).scalar()
            )
            end_time = _coerce_datetime(
                (await session.execute(select(func.max(table.c[time_key])))).scalar()
            )

    profiles = await _load_agent_profiles(session, datasets)
    return int(total_steps), start_time, end_time, len(profiles)


@router.get("/{hypothesis_id}/{experiment_id}/info", response_model=ExperimentInfo)
async def get_experiment_info(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ExperimentInfo:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        datasets = await load_dataset_catalog(session)
        total_steps, start_time, end_time, agent_count = await _get_experiment_summary(
            session, datasets
        )
        return ExperimentInfo(
            hypothesis_id=hypothesis_id,
            experiment_id=experiment_id,
            total_steps=total_steps,
            start_time=start_time,
            end_time=end_time,
            agent_count=agent_count,
        )


@router.get("/{hypothesis_id}/{experiment_id}/datasets", response_model=ReplayDatasetList)
async def get_replay_datasets(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ReplayDatasetList:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        datasets = await load_dataset_catalog(session)
        return ReplayDatasetList(
            datasets=[_dataset_to_response(dataset) for dataset in datasets]
        )


@router.get("/{hypothesis_id}/{experiment_id}/map", response_model=ReplayMapInfo)
async def get_replay_map(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ReplayMapInfo:
    return _map_info_response(workspace_path, hypothesis_id, experiment_id)


@router.get("/{hypothesis_id}/{experiment_id}/map/tiled")
async def get_replay_tiled_map(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> Dict[str, Any]:
    package = _resolve_experiment_map_package(
        workspace_path,
        hypothesis_id,
        experiment_id,
    )
    _, tiled_map = load_tiled_map(package)
    return tiled_map


@router.get("/{hypothesis_id}/{experiment_id}/map/assets/{tileset_index}")
async def get_replay_map_asset(
    hypothesis_id: str,
    experiment_id: str,
    tileset_index: int,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> FileResponse:
    package = _resolve_experiment_map_package(
        workspace_path,
        hypothesis_id,
        experiment_id,
    )
    try:
        image_path = tileset_image_path(package, tileset_index)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Tileset image not found: {exc}") from exc
    return FileResponse(image_path)


@router.get("/{hypothesis_id}/{experiment_id}/map/preview")
async def get_replay_map_preview(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> FileResponse:
    package = _resolve_experiment_map_package(
        workspace_path,
        hypothesis_id,
        experiment_id,
    )
    image_path = package.package_path / "visuals" / "preview.png"
    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(status_code=404, detail=f"Map preview not found: {image_path}")
    return FileResponse(image_path)


@router.get("/{hypothesis_id}/{experiment_id}/map/characters/{character_name}")
async def get_replay_map_character_asset(
    hypothesis_id: str,
    experiment_id: str,
    character_name: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> FileResponse:
    package = _resolve_experiment_map_package(
        workspace_path,
        hypothesis_id,
        experiment_id,
    )
    try:
        image_path = character_sprite_path(package, character_name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Character sprite not found: {exc}") from exc
    return FileResponse(image_path)


@router.get("/{hypothesis_id}/{experiment_id}/map/location-assets/{location_id}")
async def get_replay_map_location_asset(
    hypothesis_id: str,
    experiment_id: str,
    location_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> FileResponse:
    package = _resolve_experiment_map_package(
        workspace_path,
        hypothesis_id,
        experiment_id,
    )
    try:
        image_path = location_asset_path(package, location_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Location visual asset not found: {exc}") from exc
    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(status_code=404, detail=f"Location visual asset not found: {image_path}")
    return FileResponse(image_path)


@router.get(
    "/{hypothesis_id}/{experiment_id}/datasets/{dataset_id}",
    response_model=ReplayDatasetInfo,
)
async def get_replay_dataset(
    hypothesis_id: str,
    experiment_id: str,
    dataset_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ReplayDatasetInfo:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        dataset = await get_dataset_by_id(session, dataset_id)
        return _dataset_to_response(dataset)


@router.get(
    "/{hypothesis_id}/{experiment_id}/datasets/{dataset_id}/rows",
    response_model=ReplayDatasetRows,
)
async def get_replay_dataset_rows(
    hypothesis_id: str,
    experiment_id: str,
    dataset_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    order_by: Optional[str] = Query(None),
    desc_order: bool = Query(False),
    step: Optional[int] = Query(None, description="Exact step filter"),
    entity_id: Optional[int] = Query(None, description="Exact entity filter"),
    start_step: Optional[int] = Query(None, description="Start step (inclusive)"),
    end_step: Optional[int] = Query(None, description="End step (inclusive)"),
    max_step: Optional[int] = Query(None, description="Maximum step (inclusive)"),
    columns: Optional[str] = Query(None, description="Comma-separated column whitelist"),
    latest_per_entity: bool = Query(
        False,
        description="Return only the latest row per entity",
    ),
) -> ReplayDatasetRows:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        dataset = await get_dataset_by_id(session, dataset_id)
        rows = await query_dataset_rows(
            session,
            dataset,
            page=page,
            page_size=page_size,
            order_by=order_by,
            desc=desc_order,
            step=step,
            entity_id=entity_id,
            start_step=start_step,
            end_step=end_step,
            max_step=max_step,
            columns=_split_columns_param(columns),
            latest_per_entity=latest_per_entity,
        )
        return ReplayDatasetRows(
            dataset_id=dataset_id,
            columns=rows["columns"],
            rows=rows["rows"],
            total=rows["total"],
        )


@router.get(
    "/{hypothesis_id}/{experiment_id}/panel-schema",
    response_model=ReplayPanelSchema,
)
async def get_replay_panel_schema(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ReplayPanelSchema:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        datasets = await load_dataset_catalog(session)
        agent_profile_dataset = await _get_agent_profile_dataset(session, datasets)
        agent_state_datasets = _list_agent_state_datasets(datasets)
        env_state_datasets = _list_env_state_datasets(datasets)
        geo_dataset = _select_geo_dataset(datasets)
        tile_dataset = _select_tile_dataset(datasets)
        primary_agent_state_dataset = _select_primary_agent_state_dataset(datasets)
        return ReplayPanelSchema(
            agent_profile_dataset=(
                _dataset_to_response(agent_profile_dataset)
                if agent_profile_dataset is not None
                else None
            ),
            agent_state_datasets=[
                _dataset_to_response(dataset) for dataset in agent_state_datasets
            ],
            env_state_datasets=[
                _dataset_to_response(dataset) for dataset in env_state_datasets
            ],
            geo_dataset=(
                _dataset_to_response(geo_dataset) if geo_dataset is not None else None
            ),
            primary_agent_state_dataset_id=(
                primary_agent_state_dataset["dataset_id"]
                if primary_agent_state_dataset is not None
                else None
            ),
            layout_hint="map" if geo_dataset is not None or tile_dataset is not None else "random",
            supports_map=geo_dataset is not None or tile_dataset is not None,
        )


@router.get(
    "/{hypothesis_id}/{experiment_id}/steps/{step}/bundle",
    response_model=ReplayStepBundle,
)
async def get_replay_step_bundle(
    hypothesis_id: str,
    experiment_id: str,
    step: int,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ReplayStepBundle:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        datasets = await load_dataset_catalog(session)
        agent_state_datasets = _list_agent_state_datasets(datasets)
        env_state_datasets = _list_env_state_datasets(datasets)
        geo_dataset = _select_geo_dataset(datasets)
        tile_dataset = _select_tile_dataset(datasets)
        layout_hint: Literal["map", "random"] = (
            "map" if geo_dataset is not None or tile_dataset is not None else "random"
        )

        step_timestamp: Optional[datetime] = None
        agent_state_rows: Dict[str, ReplayAgentStateAtStep] = {}
        for dataset in agent_state_datasets:
            rows_result = await fetch_dataset_rows(session, dataset, step=step)
            entity_key = dataset.get("entity_key")
            if not entity_key:
                continue
            rows_by_agent_id: Dict[str, Dict[str, Any]] = {}
            for row in rows_result["rows"]:
                raw_agent_id = row.get(entity_key)
                if raw_agent_id is None:
                    continue
                rows_by_agent_id[str(raw_agent_id)] = row
            agent_state_rows[dataset["dataset_id"]] = ReplayAgentStateAtStep(
                dataset=_dataset_ref(dataset),
                rows_by_agent_id=rows_by_agent_id,
            )
            if step_timestamp is None:
                step_timestamp = _find_time_value(
                    rows_result["rows"], dataset.get("time_key")
                )

        env_state_rows: Dict[str, ReplayEnvStateAtStep] = {}
        for dataset in env_state_datasets:
            rows_result = await fetch_dataset_rows(session, dataset, step=step, limit=1)
            row = rows_result["rows"][0] if rows_result["rows"] else None
            env_state_rows[dataset["dataset_id"]] = ReplayEnvStateAtStep(
                dataset=_dataset_ref(dataset),
                row=row,
            )
            if step_timestamp is None:
                step_timestamp = _find_time_value(
                    rows_result["rows"], dataset.get("time_key")
                )

        positions = _build_positions_from_step_rows(geo_dataset, agent_state_rows)
        return ReplayStepBundle(
            step=step,
            t=step_timestamp,
            layout_hint=layout_hint,
            positions=positions,
            agent_state_rows=agent_state_rows,
            env_state_rows=env_state_rows,
        )


@router.get("/{hypothesis_id}/{experiment_id}/timeline", response_model=List[TimelinePoint])
async def get_timeline(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> List[TimelinePoint]:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        datasets = await load_dataset_catalog(session)
        timeline_dataset = _select_timeline_dataset(datasets)
        if timeline_dataset is None:
            return []

        table = await reflect_dataset_table(session, timeline_dataset)
        step_key = timeline_dataset["step_key"]
        time_key = timeline_dataset["time_key"]
        if step_key not in table.c or time_key not in table.c:
            return []

        result = await session.execute(
            select(table.c[step_key], func.min(table.c[time_key]))
            .group_by(table.c[step_key])
            .order_by(table.c[step_key])
        )
        timeline: List[TimelinePoint] = []
        for step_value, time_value in result.all():
            timestamp = _coerce_datetime(time_value)
            if timestamp is None:
                continue
            timeline.append(TimelinePoint(step=int(step_value), t=timestamp))
        return timeline


@router.get(
    "/{hypothesis_id}/{experiment_id}/agents/profiles",
    response_model=List[AgentProfile],
)
async def get_agent_profiles(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> List[AgentProfile]:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        datasets = await load_dataset_catalog(session)
        profiles = await _load_agent_profiles(session, datasets)
        return sorted(profiles.values(), key=lambda profile: profile.id)


@router.get(
    "/{hypothesis_id}/{experiment_id}/agents/{agent_id}/runtime-state",
    response_model=ReplayAgentRuntimeState,
)
async def get_agent_runtime_state(
    hypothesis_id: str,
    experiment_id: str,
    agent_id: int,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ReplayAgentRuntimeState:
    run_dir = get_run_dir(workspace_path, hypothesis_id, experiment_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run directory not found: {run_dir}")

    agent_work_dir = _resolve_agent_work_dir(run_dir, agent_id)
    if agent_work_dir is None:
        return ReplayAgentRuntimeState(
            agent_id=agent_id,
            token_usage=_token_usage_from_log(run_dir, agent_id),
        )

    log_dir = agent_work_dir / ".runtime" / "logs"
    session_state = _read_json_file(log_dir / "session_state.json", {}, max_chars=None)
    if not isinstance(session_state, dict):
        session_state = {}

    agent_state_snapshot = _read_json_file(
        log_dir / "agent_state_snapshot.json",
        {},
        max_chars=None,
    )
    if not isinstance(agent_state_snapshot, dict):
        agent_state_snapshot = {}

    agent_config = _read_json_file(agent_work_dir / "agent_config.json", {}, max_chars=None)
    if not isinstance(agent_config, dict):
        agent_config = {}

    state_files: Dict[str, Any] = {}
    for relative_path in [
        "state/observation.txt",
        "state/observation_ctx.json",
        "state/thought.txt",
        "state/current_need.txt",
        "state/emotion.json",
        "state/intention.json",
        "state/plan_state.json",
        "state/needs.json",
    ]:
        path = agent_work_dir / relative_path
        if not path.exists():
            continue
        if path.suffix == ".json":
            state_files[relative_path] = _read_json_file(path, {}, max_chars=None)
        else:
            state_files[relative_path] = _read_text(path, max_chars=None)

    token_usage = _token_usage_from_session(agent_state_snapshot)
    if not token_usage:
        token_usage = _token_usage_from_session(session_state)
    if not token_usage:
        token_usage = _token_usage_from_log(run_dir, agent_id)

    compact_state = _read_json_file(
        log_dir / "thread_compact_state.json",
        {},
        max_chars=None,
    )
    if not isinstance(compact_state, dict):
        compact_state = {}

    return ReplayAgentRuntimeState(
        agent_id=agent_id,
        work_dir=str(agent_work_dir),
        agent_config=agent_config,
        session_state=session_state,
        agent_state_snapshot=agent_state_snapshot,
        token_usage=token_usage,
        state_files=state_files,
        recent_messages=_read_jsonl(log_dir / "thread_messages.jsonl"),
        recent_tool_calls=_read_jsonl(log_dir / "tool_calls.jsonl"),
        recent_step_replays=_read_jsonl(log_dir / "step_replay.jsonl"),
        compact_state=compact_state,
        agent_markdown=_read_text(agent_work_dir / "AGENT.md", max_chars=None),
    )
