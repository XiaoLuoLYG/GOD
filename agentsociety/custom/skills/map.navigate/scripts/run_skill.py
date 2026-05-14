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
    skill_args_from,
)

SKILL_ID = "map.navigate"


def requested_targets(args: dict, spec: dict) -> tuple[list[str], list[str], str]:
    skill_args = skill_args_from(args)
    requested_location = str(skill_args.get("location_id") or skill_args.get("target_location_id") or "").strip()
    requested_interaction = str(skill_args.get("interaction_id") or "").strip()
    locations = [requested_location] if requested_location else list(spec["target_locations"])
    interactions = [requested_interaction] if requested_interaction else list(spec["target_interactions"])
    target = requested_location or requested_interaction or "default navigation target"
    return locations, interactions, target


def build_navigation_effect(observation: dict, locations: list[str], interactions: list[str]) -> dict:
    current = str(observation.get("location_id") or "")
    location_id = choose_available_location(observation, locations, fallback_current=False)
    if location_id and location_id != current:
        return {"type": "move", "location_id": location_id, "reason": f"map.navigate: move from {current or 'unknown'} to {location_id}"}
    interaction_id = choose_available_interaction(observation, interactions, location_id=current or location_id)
    if interaction_id:
        return {"type": "interact", "interaction_id": interaction_id, "params": {"message": "navigation target reached"}, "reason": "map.navigate: perform requested interaction at current location"}
    return {"type": "set_state", "action": "check map and wait for a reachable target", "status": "moving", "emotion": "focused", "reason": "map.navigate: requested target is not currently reachable"}


def main() -> int:
    args = parse_args()
    observation = observation_from(args)
    spec = load_local_skill_spec(SKILL_DIR)
    locations, interactions, target = requested_targets(args, spec)
    result = build_skill_result(
        skill_id=SKILL_ID,
        summary="navigate to a reachable town target",
        reason="The navigation skill follows explicit location or interaction args before falling back to its local map defaults.",
        world_effect=build_navigation_effect(observation, locations, interactions),
        memory_effects=[memory_effect(SKILL_ID, spec["memory_template"].format(target=target))],
        confidence=0.8,
    )
    return emit_result(args, SKILL_ID, result)


if __name__ == "__main__":
    raise SystemExit(main())
