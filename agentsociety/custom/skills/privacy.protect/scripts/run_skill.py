#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR.parent / "_shared"))

from agent_skill_runtime import (  # noqa: E402
    build_skill_result,
    choose_available_interaction,
    choose_available_location,
    emit_result,
    load_local_skill_spec,
    memory_effect,
    observation_from,
    parse_args,
)

SKILL_ID = 'privacy.protect'
SUMMARY = 'Protect private information before sharing or recording.'
TARGET_LOCATIONS = ['home', 'library']
TARGET_INTERACTIONS = ['work_from_home', 'quiet_work']
STATUS = 'protecting_privacy'
EMOTION = 'careful'
SPEECH = '我先确认哪些信息不能随便说出去。'
MEMORY_TEMPLATE = 'Used privacy.protect: {summary} at {location_id}.'


def choose_world_effect(observation: dict, spec: dict) -> dict:
    current = str(observation.get("location_id") or "")
    target_locations = list(spec.get("target_locations") or TARGET_LOCATIONS)
    target_interactions = list(spec.get("target_interactions") or TARGET_INTERACTIONS)
    location_id = choose_available_location(observation, target_locations)
    if location_id and location_id != current:
        return {"type": "move", "location_id": location_id, "reason": f"{SKILL_ID}: move toward {SUMMARY}"}
    interaction_id = choose_available_interaction(observation, target_interactions, location_id=current or location_id)
    if interaction_id:
        return {"type": "interact", "interaction_id": interaction_id, "params": {"message": SUMMARY}, "reason": f"{SKILL_ID}: perform {SUMMARY}"}
    return {"type": "set_state", "action": SUMMARY, "status": str(spec.get("status") or STATUS), "emotion": str(spec.get("emotion") or EMOTION), "reason": f"{SKILL_ID}: no configured map target is reachable"}


def maybe_speech(world_effect: dict) -> dict | None:
    if not SPEECH or world_effect.get("type") == "move":
        return None
    return {"type": "group_message", "group_id": 1, "content": SPEECH}


def build_memory(observation: dict, spec: dict) -> dict:
    location_id = str(observation.get("location_id") or "unknown")
    template = str(spec.get("memory_template") or MEMORY_TEMPLATE)
    return memory_effect(SKILL_ID, template.format(summary=SUMMARY, location_id=location_id), location_id=location_id)


def main() -> int:
    args = parse_args()
    observation = observation_from(args)
    spec = load_local_skill_spec(SKILL_DIR)
    world_effect = choose_world_effect(observation, spec)
    result = build_skill_result(
        skill_id=SKILL_ID,
        summary=SUMMARY,
        reason=f"{SKILL_ID} uses its own local skill.json targets and script constants; no central keyword rule selected this behavior.",
        world_effect=world_effect,
        speech_effect=maybe_speech(world_effect),
        memory_effects=[build_memory(observation, spec)],
        confidence=0.76,
    )
    return emit_result(args, SKILL_ID, result)


if __name__ == "__main__":
    raise SystemExit(main())
