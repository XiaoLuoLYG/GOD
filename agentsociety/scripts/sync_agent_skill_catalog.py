#!/usr/bin/env python3
"""Scaffold GOD executable skills and migrate agent configs.

This script is intentionally conservative: it creates missing `SKILL.md`,
`skill.json`, and `scripts/run_skill.py` files, but it does not overwrite an
existing skill's local implementation. Existing skill behavior belongs inside
that skill directory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "custom" / "skills"
CONFIG_PATH = (
    REPO_ROOT
    / "quick_experiments"
    / "hypothesis_god_town"
    / "experiment_1"
    / "init"
    / "init_config.json"
)

COMMON_SKILL_IDS = [
    "routine.daily",
    "social.reply",
    "memory.record",
    "map.navigate",
    "safety.respond",
]

PERSONA_SKILL_IDS = [
    "community.coordinate",
    "conflict.mediate",
    "first_aid.basic",
    "notice.write",
    "messaging.group",
    "tools.repair",
    "inventory.count",
    "route.localmap",
    "ledger.basic",
    "neighbor.support",
    "class.organize",
    "youth.communicate",
    "writing.feedback",
    "history.localtelling",
    "library.curate",
    "care.basic",
    "chronic.followup",
    "emotion.calm",
    "health.educate",
    "record.shortnote",
    "cooking.lightmeal",
    "listen.relay",
    "shop.run",
    "social.matchmake",
    "community.observe",
    "class.learn",
    "sketch.draw",
    "phone.photolog",
    "computer.basic",
    "peer.communicate",
    "route.recall",
    "garden.basic",
    "story.localpast",
    "writing.hand",
    "neighbor.greet",
    "computer.repair",
    "script.automate",
    "info.research",
    "remote.communicate",
    "privacy.protect",
    "patrol.plan",
    "roster.verify",
    "repair.basic",
    "crowd.guide",
    "radio.comms",
    "vegetable.source",
    "stall.run",
    "price.negotiate",
    "ingredient.advise",
    "gossip.filter",
]


def safe_dir(skill_id: str) -> str:
    return skill_id.strip().replace("/", "_").replace("\\", "_").replace("..", "_")


def title(skill_id: str) -> str:
    return " ".join(part.capitalize() for part in skill_id.replace(".", " ").split())


def output_name(skill_id: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in skill_id).strip("_")


def default_effects(shared: bool) -> list[str]:
    return (
        ["move", "interact", "set_state", "direct_message", "group_message", "remember"]
        if not shared
        else ["move", "interact", "set_state", "remember"]
    )


def default_spec(skill_id: str, *, shared: bool) -> dict[str, Any]:
    return {
        "skill_id": skill_id,
        "name": title(skill_id),
        "description": f"Use {skill_id} as a real executable GOD skill.",
        "shared": shared,
        "effects": default_effects(shared),
        "target_locations": ["park", "cafe", "home"],
        "target_interactions": ["take_walk", "chat_over_coffee", "relax_at_home"],
        "status": "active",
        "emotion": "calm",
        "speech": "我会根据当前场景执行这个能力。",
        "memory_template": f"Used {skill_id}: {{summary}} at {{location_id}}.",
        "failure_strategy": "set_state",
        "strategy": "configured_action",
        "trigger_examples": [f"the agent needs to use {skill_id}"],
        "args_schema": {"type": "object", "additionalProperties": True},
    }


def skill_md(spec: dict[str, Any]) -> str:
    effects = "\n".join(f"  - {effect}" for effect in spec["effects"])
    triggers = "\n".join(f"  - {item}" for item in spec["trigger_examples"])
    return f"""---
name: {spec["skill_id"]}
description: {spec["description"]}
script: scripts/run_skill.py
shared: {str(bool(spec["shared"])).lower()}
effects:
{effects}
args_schema: {json.dumps(spec["args_schema"], ensure_ascii=False, separators=(",", ":"))}
trigger_examples:
{triggers}
outputs:
  - state/skill_results/{output_name(spec["skill_id"])}.json
---

# {spec["name"]}

This skill is an executable GOD skill. Edit `skill.json` for local targets and
templates, and edit `scripts/run_skill.py` when the skill needs custom behavior.
The script returns a standard `SkillResult`; the agent runtime validates and
applies the effects.
"""


def scaffold_script(skill_id: str) -> str:
    return f'''#!/usr/bin/env python3
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

SKILL_ID = {skill_id!r}


def choose_world_effect(observation: dict, spec: dict) -> dict:
    current = str(observation.get("location_id") or "")
    location_id = choose_available_location(observation, list(spec.get("target_locations") or []))
    if location_id and location_id != current:
        return {{"type": "move", "location_id": location_id, "reason": f"{{SKILL_ID}}: move toward local skill target"}}
    interaction_id = choose_available_interaction(
        observation,
        list(spec.get("target_interactions") or []),
        location_id=current or location_id,
    )
    if interaction_id:
        return {{"type": "interact", "interaction_id": interaction_id, "params": {{"message": spec.get("description", SKILL_ID)}}, "reason": f"{{SKILL_ID}}: perform local skill interaction"}}
    return {{"type": "set_state", "action": str(spec.get("description") or SKILL_ID), "status": str(spec.get("status") or "active"), "emotion": str(spec.get("emotion") or "calm"), "reason": f"{{SKILL_ID}}: no configured target is reachable"}}


def main() -> int:
    args = parse_args()
    observation = observation_from(args)
    spec = load_local_skill_spec(SKILL_DIR)
    summary = str(spec.get("description") or SKILL_ID)
    location_id = str(observation.get("location_id") or "unknown")
    template = str(spec.get("memory_template") or "Used {{skill_id}}: {{summary}} at {{location_id}}.")
    world_effect = choose_world_effect(observation, spec)
    result = build_skill_result(
        skill_id=SKILL_ID,
        summary=summary,
        reason=f"{{SKILL_ID}} uses only its local skill.json plus this local script.",
        world_effect=world_effect,
        memory_effects=[
            memory_effect(
                SKILL_ID,
                template.format(skill_id=SKILL_ID, summary=summary, location_id=location_id),
                location_id=location_id,
            )
        ],
        confidence=0.72,
    )
    return emit_result(args, SKILL_ID, result)


if __name__ == "__main__":
    raise SystemExit(main())
'''


def write_if_missing(path: Path, text: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if path.name == "run_skill.py":
        path.chmod(0o755)
    return True


def scaffold_skill(skill_id: str, *, shared: bool) -> list[str]:
    dest = SKILLS_ROOT / safe_dir(skill_id)
    spec = default_spec(skill_id, shared=shared)
    created: list[str] = []
    if write_if_missing(dest / "skill.json", json.dumps(spec, ensure_ascii=False, indent=2) + "\n"):
        created.append(str(dest / "skill.json"))
    if write_if_missing(dest / "SKILL.md", skill_md(spec)):
        created.append(str(dest / "SKILL.md"))
    if write_if_missing(dest / "scripts" / "run_skill.py", scaffold_script(skill_id)):
        created.append(str(dest / "scripts" / "run_skill.py"))
    return created


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def default_skill_ids(agent_id: int, count: int = 5) -> list[str]:
    start = ((agent_id - 1) * count) % len(PERSONA_SKILL_IDS)
    rotated = PERSONA_SKILL_IDS[start:] + PERSONA_SKILL_IDS[:start]
    return rotated[:count]


def normalize_personal_skill_ids(raw: Any, agent_id: int) -> list[str]:
    source = raw if isinstance(raw, list) else []
    known = set(PERSONA_SKILL_IDS)
    result: list[str] = []
    seen: set[str] = set()
    for item in source:
        skill_id = str(item).strip()
        if skill_id in known and skill_id not in seen:
            seen.add(skill_id)
            result.append(skill_id)
    return result or default_skill_ids(agent_id)


def collect_profile_skill_ids(data: dict[str, Any]) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for agent in data.get("agents", []):
        if not isinstance(agent, dict):
            continue
        agent_id = int(agent.get("agent_id") or agent.get("kwargs", {}).get("id") or 0)
        kwargs = agent.get("kwargs") or {}
        profile = kwargs.get("profile") or {}
        existing = kwargs.get("skill_ids")
        source = existing if isinstance(existing, list) else profile.get("skills")
        result[agent_id] = normalize_personal_skill_ids(source, agent_id)
    return result


def migrate_config(path: Path, profile_skill_ids: dict[int, list[str]]) -> None:
    data = load_config(path)
    for agent in data.get("agents", []):
        if not isinstance(agent, dict):
            continue
        agent_id = int(agent.get("agent_id") or agent.get("kwargs", {}).get("id") or 0)
        kwargs = agent.setdefault("kwargs", {})
        profile = kwargs.setdefault("profile", {})
        profile.pop("skills", None)
        kwargs["enable_skill_runtime"] = True
        kwargs["common_skill_ids"] = list(COMMON_SKILL_IDS)
        kwargs["skill_ids"] = profile_skill_ids.get(agent_id, default_skill_ids(agent_id))
        kwargs.pop("enable_daily_life", None)
        kwargs.pop("daily_life_skill_path", None)
        kwargs.pop("skill_runtime_skill_names", None)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--all-configs", action="store_true")
    parser.add_argument("--skip-config", action="store_true")
    args = parser.parse_args()

    config_paths = (
        sorted((REPO_ROOT / "quick_experiments").glob("hypothesis_*/experiment_*/init/init_config.json"))
        if args.all_configs
        else [Path(args.config)]
    )
    per_config: dict[str, dict[int, list[str]]] = {}
    for config_path in config_paths:
        config_data = load_config(config_path) if config_path.exists() else {"agents": []}
        per_config[str(config_path)] = collect_profile_skill_ids(config_data)

    created: list[str] = []
    for skill_id in COMMON_SKILL_IDS:
        created.extend(scaffold_skill(skill_id, shared=True))
    for skill_id in PERSONA_SKILL_IDS:
        created.extend(scaffold_skill(skill_id, shared=False))

    migrated_configs: list[str] = []
    if not args.skip_config:
        for raw_path, per_agent in per_config.items():
            config_path = Path(raw_path)
            if config_path.exists():
                migrate_config(config_path, per_agent)
                migrated_configs.append(str(config_path))

    print(
        json.dumps(
            {
                "skills_checked": len(COMMON_SKILL_IDS) + len(PERSONA_SKILL_IDS),
                "created_files": created,
                "configs": migrated_configs,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
