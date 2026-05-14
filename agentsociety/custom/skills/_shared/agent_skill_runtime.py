#!/usr/bin/env python3
"""Protocol helpers for executable GOD skills.

The shared layer intentionally contains no skill ids, trigger keywords, or
business behavior. A skill script owns its own strategy and uses these helpers
only to parse input, inspect the observation, build a SkillResult, and emit it.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "agent_skill_result.v1"


def parse_args() -> dict[str, Any]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--args-json", default="{}")
    parsed = json.loads(parser.parse_args().args_json)
    if not isinstance(parsed, dict):
        raise TypeError("--args-json must decode to an object")
    return parsed


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_") or "skill"


def current_skill_dir() -> Path:
    raw = os.environ.get("SKILL_DIR")
    if raw:
        return Path(raw).resolve()
    return Path(__file__).resolve().parents[1]


def load_local_skill_spec(skill_dir: Path | None = None) -> dict[str, Any]:
    target = (skill_dir or current_skill_dir()) / "skill.json"
    with target.open("r", encoding="utf-8") as handle:
        spec = json.load(handle)
    if not isinstance(spec, dict):
        raise TypeError(f"{target} must contain a JSON object")
    return spec


def observation_from(args: dict[str, Any]) -> dict[str, Any]:
    raw = args.get("observation")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {"raw": raw}
    return {}


def skill_args_from(args: dict[str, Any]) -> dict[str, Any]:
    raw = args.get("skill_args")
    return raw if isinstance(raw, dict) else {}


def as_ids(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    result: list[str] = []
    for item in items:
        value = item.get("id") if isinstance(item, dict) else item
        text = str(value or "").strip()
        if text:
            result.append(text)
    return result


def available_location_ids(observation: dict[str, Any]) -> list[str]:
    return as_ids(observation.get("known_locations"))


def available_interaction_ids(observation: dict[str, Any]) -> list[str]:
    return as_ids(observation.get("known_interactions"))


def choose_available_location(
    observation: dict[str, Any],
    candidates: list[str] | tuple[str, ...],
    *,
    fallback_current: bool = True,
) -> str:
    available = available_location_ids(observation)
    available_set = set(available)
    for candidate in candidates:
        if candidate and candidate in available_set:
            return candidate
    current = str(observation.get("location_id") or "")
    if fallback_current and current:
        return current
    return available[0] if available else current


def choose_available_interaction(
    observation: dict[str, Any],
    candidates: list[str] | tuple[str, ...],
    *,
    location_id: str = "",
) -> str:
    allowed = set(available_interaction_ids(observation))
    for item in observation.get("known_interactions", []) or []:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "")
        if not item_id or item_id not in candidates:
            continue
        allowed_locations = item.get("allowed_location_ids") or item.get("location_ids") or []
        if not location_id or not allowed_locations or location_id in allowed_locations:
            return item_id
    for candidate in candidates:
        if candidate and candidate in allowed and not location_id:
            return candidate
    return ""


def hour_from(value: Any) -> float:
    try:
        text = str(value or "")
        if not text:
            return 12.0
        parsed = datetime.fromisoformat(text)
        return parsed.hour + parsed.minute / 60.0
    except Exception:
        return 12.0


def profile_text(profile: Any) -> str:
    if isinstance(profile, dict):
        return " ".join(str(value) for value in profile.values()).lower()
    return str(profile or "").lower()


def collect_text(args: dict[str, Any], observation: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("latest_event", "last_message", "raw"):
        parts.append(str(observation.get(key) or ""))
    for item in observation.get("recent_messages", []) or []:
        if isinstance(item, dict):
            parts.append(str(item.get("content") or ""))
    for item in args.get("pending_interventions") or []:
        parts.append(str(item))
    return " ".join(parts).lower()


def build_skill_result(
    *,
    skill_id: str,
    summary: str,
    reason: str,
    world_effect: dict[str, Any] | None = None,
    speech_effect: dict[str, Any] | None = None,
    memory_effects: list[dict[str, Any]] | None = None,
    confidence: float = 0.75,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "skill_id": skill_id,
        "summary": summary,
        "reason": reason,
        "confidence": confidence,
        "world_effect": world_effect,
        "speech_effect": speech_effect,
        "memory_effects": memory_effects or [],
    }


def memory_effect(skill_id: str, content: str, **metadata: Any) -> dict[str, Any]:
    return {
        "kind": "skill_event",
        "content": content,
        "metadata": {"skill_id": skill_id, **metadata},
    }


def write_result(work_dir: Path, skill_id: str, result: dict[str, Any]) -> None:
    target = work_dir / "state" / "skill_results" / f"{safe_name(skill_id)}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def emit_result(args: dict[str, Any], skill_id: str, result: dict[str, Any]) -> int:
    work_dir = Path(args.get("agent_work_dir") or os.environ.get("AGENT_WORK_DIR") or ".").resolve()
    write_result(work_dir, skill_id, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0
