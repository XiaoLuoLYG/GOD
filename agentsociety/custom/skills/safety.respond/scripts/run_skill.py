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
    collect_text,
    emit_result,
    load_local_skill_spec,
    memory_effect,
    observation_from,
    parse_args,
    skill_args_from,
)

SKILL_ID = "safety.respond"
URGENCY_WORDS = ("火灾", "地震", "洪水", "撤离", "疏散", "紧急", "危险", "volcano", "earthquake", "fire", "flood", "emergency", "evacuate")


def is_urgent(args: dict, observation: dict) -> bool:
    text = collect_text(args, observation)
    return any(word.lower() in text for word in URGENCY_WORDS)


def build_safety_world(observation: dict, spec: dict) -> dict:
    current = str(observation.get("location_id") or "")
    location_id = choose_available_location(observation, spec["target_locations"])
    if location_id and location_id != current:
        return {"type": "move", "location_id": location_id, "reason": "safety.respond: move toward safety supplies or public coordination"}
    interaction_id = choose_available_interaction(observation, spec["target_interactions"], location_id=current or location_id)
    if interaction_id:
        return {"type": "interact", "interaction_id": interaction_id, "params": {"message": "safety response"}, "reason": "safety.respond: use the safest available local interaction"}
    return {"type": "set_state", "action": "hold safety posture and monitor conditions", "status": spec["status"], "emotion": spec["emotion"], "reason": "safety.respond: no reachable safety interaction is available"}


def main() -> int:
    args = parse_args()
    observation = observation_from(args)
    spec = load_local_skill_spec(SKILL_DIR)
    skill_args = skill_args_from(args)
    urgent = is_urgent(args, observation)
    announcement = str(skill_args.get("message") or spec["speech"])
    content = collect_text(args, observation)[:120] or "routine safety readiness"
    result = build_skill_result(
        skill_id=SKILL_ID,
        summary="respond to a safety-relevant event" if urgent else "maintain safety readiness",
        reason="Urgency words or intervention context require safety coordination." if urgent else "No urgent term was detected, so the skill keeps a cautious readiness posture.",
        world_effect=build_safety_world(observation, spec),
        speech_effect={"type": "group_message", "group_id": int(skill_args.get("group_id") or 1), "content": announcement},
        memory_effects=[memory_effect(SKILL_ID, spec["memory_template"].format(content=content), urgent=urgent)],
        confidence=0.92 if urgent else 0.62,
    )
    return emit_result(args, SKILL_ID, result)


if __name__ == "__main__":
    raise SystemExit(main())
