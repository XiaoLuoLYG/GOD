"""Curated GOD ExperimentPack registry helpers."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from agentsociety2.backend.services.map_packages import DEFAULT_MAP_ID
from agentsociety2.backend.services import package_archives


DEFAULT_EXPERIMENT_KEY = "god_town"
REGISTRY_FILENAME = "experiment_registry.json"

FALLBACK_EXPERIMENTS: tuple[dict[str, Any], ...] = (
    {
        "key": "god_town",
        "label": "GOD Town",
        "description": "A normal weekday in The Ville.",
        "localized": {
            "en": {
                "label": "GOD Town",
                "description": "A normal weekday in The Ville.",
            },
            "zh": {
                "label": "GOD 小镇",
                "description": "维尔小镇里的普通工作日。",
            },
        },
        "hypothesis_id": "god_town",
        "experiment_id": "1",
        "map_id": DEFAULT_MAP_ID,
        "public_slug": "god-town-daily-life",
        "image": "assets/screenshots/map-the-ville.png",
        "tags": ["daily life", "baseline", "operator replay"],
        "agent_pack": "jiuwen-town-residents",
        "replay_slug": "god-town",
        "enabled": True,
    },
    {
        "key": "pku_trump_visit",
        "label": "PKU Trump Visit",
        "description": "A PKU campus visit and public-situation experiment.",
        "localized": {
            "en": {
                "label": "PKU Trump Visit",
                "description": "A PKU campus visit and public-situation experiment.",
            },
            "zh": {
                "label": "北大访问实验",
                "description": "北京大学校园访问与公共情境实验。",
            },
        },
        "hypothesis_id": "pku_trump_visit",
        "experiment_id": "1",
        "map_id": "pku",
        "public_slug": "pku-public-situation",
        "image": "assets/screenshots/map-pku.png",
        "tags": ["campus", "public event", "operator replay"],
        "agent_pack": "pku-campus-cast",
        "replay_slug": "pku-public-situation",
        "enabled": True,
    },
)


def registry_path(workspace_path: Path) -> Path:
    return Path(workspace_path) / REGISTRY_FILENAME


def load_registry_entries(
    workspace_path: Path,
    *,
    include_disabled: bool = False,
) -> list[dict[str, Any]]:
    path = registry_path(workspace_path)
    raw_entries: list[Any]
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw = payload.get("experiments") if isinstance(payload, dict) else payload
        raw_entries = raw if isinstance(raw, list) else []
    else:
        raw_entries = [deepcopy(item) for item in FALLBACK_EXPERIMENTS]

    entries = [_normalize_entry(item) for item in raw_entries if isinstance(item, dict)]
    return [item for item in entries if include_disabled or item["enabled"]]


def load_registry_by_key(workspace_path: Path) -> dict[str, dict[str, Any]]:
    return {item["key"]: item for item in load_registry_entries(workspace_path)}


def default_entry(workspace_path: Path) -> dict[str, Any] | None:
    for item in load_registry_entries(workspace_path):
        if item["key"] == DEFAULT_EXPERIMENT_KEY:
            return item
    entries = load_registry_entries(workspace_path)
    return entries[0] if entries else None


def experiment_path(workspace_path: Path, entry: dict[str, Any]) -> Path:
    return (
        Path(workspace_path)
        / f"hypothesis_{entry['hypothesis_id']}"
        / f"experiment_{entry['experiment_id']}"
    )


def status_entries(workspace_path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for entry in load_registry_entries(workspace_path):
        exp_path = experiment_path(workspace_path, entry)
        config_path = exp_path / "init" / "init_config.json"
        replay_db_path = exp_path / "run" / "sqlite.db"
        values.append(
            {
                **entry,
                "workspace_path": str(workspace_path),
                "config_exists": config_path.exists(),
                "replay_db_exists": replay_db_path.exists(),
            }
        )
    return values


def public_slug(entry: dict[str, Any]) -> str:
    return package_archives.sanitize_id(
        str(entry.get("public_slug") or entry.get("key") or entry.get("hypothesis_id") or "experiment").lower(),
        "experiment",
    )


def _sanitize_registry_path_id(value: str, fallback: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]+", "-", value.strip()).strip("-._")
    return safe or fallback


def _normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    key = package_archives.sanitize_id(str(entry.get("key") or entry.get("hypothesis_id") or ""), "experiment")
    hypothesis_id = _sanitize_registry_path_id(str(entry.get("hypothesis_id") or key), key)
    experiment_id = _sanitize_registry_path_id(str(entry.get("experiment_id") or "1"), "1")
    label = str(entry.get("label") or key)
    description = str(entry.get("description") or "")
    localized = entry.get("localized") if isinstance(entry.get("localized"), dict) else {}
    tags = entry.get("tags") if isinstance(entry.get("tags"), list) else []
    normalized = {
        **entry,
        "key": key,
        "label": label,
        "description": description,
        "localized": localized,
        "hypothesis_id": hypothesis_id,
        "experiment_id": experiment_id,
        "map_id": str(entry.get("map_id") or DEFAULT_MAP_ID),
        "public_slug": public_slug({**entry, "key": key, "hypothesis_id": hypothesis_id}),
        "image": str(entry.get("image") or ""),
        "tags": [str(item) for item in tags if str(item).strip()],
        "agent_pack": str(entry.get("agent_pack") or ""),
        "replay_slug": str(entry.get("replay_slug") or ""),
        "enabled": bool(entry.get("enabled", True)),
    }
    return normalized
