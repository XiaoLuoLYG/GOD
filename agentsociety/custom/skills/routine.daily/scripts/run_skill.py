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
    hour_from,
    load_local_skill_spec,
    memory_effect,
    observation_from,
    parse_args,
    profile_text,
)

SKILL_ID = "routine.daily"


def choose_daily_plan(args: dict, observation: dict, spec: dict) -> dict:
    role_text = profile_text(args.get("profile"))
    hour = hour_from(args.get("time"))
    if ("学生" in role_text or "student" in role_text) and 7.5 <= hour < 16.5:
        return {"summary": "school study routine", "locations": ["school", "library"], "interactions": ["attend_class", "study_after_class"], "status": "studying", "emotion": "focused"}
    if any(word in role_text for word in ("老师", "教师", "teacher")) and 7.5 <= hour < 17.5:
        return {"summary": "teaching routine", "locations": ["school", "library"], "interactions": ["teach_class", "prepare_lesson"], "status": "teaching", "emotion": "focused"}
    if any(word in role_text for word in ("医生", "护士", "pharmacist", "doctor", "nurse")) and 8 <= hour < 18:
        return {"summary": "health care shift", "locations": ["pharmacy", "home"], "interactions": ["pharmacy_consultation", "blood_pressure_check"], "status": "caring", "emotion": "attentive"}
    if any(word in role_text for word in ("店", "商", "shop", "vendor", "market")) and 8 <= hour < 18:
        return {"summary": "market work routine", "locations": ["market", "supply_store"], "interactions": ["work_shop_shift", "customer_service"], "status": "working", "emotion": "focused"}
    if 5.5 <= hour < 8.5:
        return {"summary": "morning home routine", "locations": ["home", "park"], "interactions": ["cook_meal", "morning_exercise"], "status": "starting_day", "emotion": "calm"}
    if 11.5 <= hour < 13.5:
        return {"summary": "lunch routine", "locations": ["cafe", "market", "home"], "interactions": ["eat_light_meal", "buy_food", "eat_at_home"], "status": "eating", "emotion": "content"}
    if 17.5 <= hour < 20.5:
        return {"summary": "evening routine", "locations": ["home", "cafe", "park"], "interactions": ["eat_at_home", "chat_over_coffee", "meet_friend"], "status": "winding_down", "emotion": "calm"}
    if hour >= 23 or hour < 5.5:
        return {"summary": "sleep routine", "locations": ["home", "dorm"], "interactions": ["sleep_at_home", "rest_at_dorm"], "status": "resting", "emotion": "tired"}
    return {"summary": "ordinary town routine", "locations": spec["target_locations"], "interactions": spec["target_interactions"], "status": spec["status"], "emotion": spec["emotion"]}


def build_world_effect(observation: dict, plan: dict) -> dict:
    current = str(observation.get("location_id") or "")
    location_id = choose_available_location(observation, plan["locations"])
    if location_id and location_id != current:
        return {"type": "move", "location_id": location_id, "reason": f"routine.daily: move for {plan['summary']}"}
    interaction_id = choose_available_interaction(observation, plan["interactions"], location_id=current or location_id)
    if interaction_id:
        return {"type": "interact", "interaction_id": interaction_id, "params": {"message": plan["summary"]}, "reason": f"routine.daily: perform {plan['summary']}"}
    return {"type": "set_state", "action": plan["summary"], "status": plan["status"], "emotion": plan["emotion"], "reason": "routine.daily: no matching map target is currently available"}


def main() -> int:
    args = parse_args()
    observation = observation_from(args)
    spec = load_local_skill_spec(SKILL_DIR)
    plan = choose_daily_plan(args, observation, spec)
    result = build_skill_result(
        skill_id=SKILL_ID,
        summary=plan["summary"],
        reason="The daily skill uses the agent role, clock time, current location, and available town actions.",
        world_effect=build_world_effect(observation, plan),
        memory_effects=[memory_effect(SKILL_ID, spec["memory_template"].format(summary=plan["summary"]))],
        confidence=0.78,
    )
    return emit_result(args, SKILL_ID, result)


if __name__ == "__main__":
    raise SystemExit(main())
