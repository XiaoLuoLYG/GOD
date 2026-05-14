#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR.parent / "_shared"))

from agent_skill_runtime import (  # noqa: E402
    build_skill_result,
    emit_result,
    load_local_skill_spec,
    memory_effect,
    observation_from,
    parse_args,
    skill_args_from,
)

SKILL_ID = "memory.record"


def memory_content(args: dict, observation: dict) -> str:
    skill_args = skill_args_from(args)
    explicit = str(skill_args.get("content") or "").strip()
    if explicit:
        return explicit
    event = str(observation.get("latest_event") or "").strip()
    if event:
        return event
    location_id = str(observation.get("location_id") or "unknown")
    return f"Quiet step at {location_id}; no special external event was present."


def main() -> int:
    args = parse_args()
    observation = observation_from(args)
    spec = load_local_skill_spec(SKILL_DIR)
    content = memory_content(args, observation)
    location_id = str(observation.get("location_id") or "unknown")
    explicit_content = bool(str(skill_args_from(args).get("content") or "").strip())
    memory_text = content if explicit_content else spec["memory_template"].format(location_id=location_id, content=content)
    result = build_skill_result(
        skill_id=SKILL_ID,
        summary="record current context in memory",
        reason="This skill only writes durable context; it does not fabricate movement or speech.",
        memory_effects=[memory_effect(SKILL_ID, memory_text, location_id=location_id)],
        confidence=0.82,
    )
    return emit_result(args, SKILL_ID, result)


if __name__ == "__main__":
    raise SystemExit(main())
