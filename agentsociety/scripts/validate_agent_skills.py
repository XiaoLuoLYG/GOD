#!/usr/bin/env python3
"""Validate GOD executable agent skills end to end.

This script scans ``custom/skills``, verifies the default agent config mounts
only catalog-backed skills, executes every custom skill subprocess, and checks
that returned SkillResult effects follow the runtime protocol.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "packages" / "agentsociety2"
DEFAULT_INIT_CONFIG = (
    REPO_ROOT
    / "quick_experiments"
    / "hypothesis_god_town"
    / "experiment_1"
    / "init"
    / "init_config.json"
)
INIT_CONFIG_GLOB = REPO_ROOT / "quick_experiments"
COMMON_SKILL_IDS = [
    "routine.daily",
    "social.reply",
    "memory.record",
    "map.navigate",
    "safety.respond",
]
SCHEMA_VERSION = "agent_skill_result.v1"
SHARED_RUNTIME = REPO_ROOT / "custom" / "skills" / "_shared" / "agent_skill_runtime.py"
REQUIRED_SKILL_JSON_FIELDS = {
    "skill_id",
    "description",
    "effects",
    "target_locations",
    "target_interactions",
    "status",
    "emotion",
    "memory_template",
    "failure_strategy",
    "strategy",
}
BANNED_SHARED_RUNTIME_TOKENS = (
    "PROFILE_RULES",
    "choose_profile_rule",
    "run_profile_skill",
    "run_common_skill",
    "COMMON_SKILL_IDS =",
)
BANNED_SKILL_SCRIPT_PATTERNS = (
    r"from\s+agent_skill_runtime\s+import\s+main\b",
    r"\bPROFILE_RULES\b",
    r"\bchoose_profile_rule\b",
    r"\brun_profile_skill\b",
    r"\brun_common_skill\b",
)


if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from agentsociety2.agent.skills import SkillRegistry  # noqa: E402


def sample_observation(*, current_location: str = "home", with_message: bool = False) -> dict[str, Any]:
    locations = [
        "home",
        "park",
        "cafe",
        "school",
        "pharmacy",
        "supply_store",
        "market",
        "library",
        "dorm",
    ]
    interaction_locations = {
        "sleep_at_home": ["home"],
        "eat_at_home": ["home"],
        "cook_meal": ["home"],
        "relax_at_home": ["home"],
        "work_from_home": ["home"],
        "video_call_family": ["home"],
        "take_walk": ["park"],
        "meet_friend": ["park", "cafe"],
        "coordinate_group": ["park", "supply_store", "market"],
        "public_announcement": ["park", "supply_store", "market"],
        "casual_meetup": ["park", "cafe", "school"],
        "bird_watch": ["park"],
        "water_plants": ["park", "home"],
        "chat_over_coffee": ["cafe"],
        "chat_with_regular": ["cafe", "market"],
        "eat_light_meal": ["cafe", "home"],
        "buy_food": ["market", "cafe"],
        "attend_class": ["school"],
        "teach_class": ["school"],
        "study_after_class": ["school", "library"],
        "prepare_lesson": ["school", "library"],
        "pharmacy_consultation": ["pharmacy"],
        "blood_pressure_check": ["pharmacy", "home"],
        "home_visit_prep": ["pharmacy", "home"],
        "buy_medicine": ["pharmacy"],
        "inspect_supplies": ["supply_store", "market"],
        "prepare_kit": ["supply_store"],
        "repair_tools": ["supply_store", "home"],
        "quiet_work": ["library", "home", "school"],
        "research_topic": ["library"],
        "read_book": ["library"],
        "work_shop_shift": ["market"],
        "restock_vegetables": ["market"],
        "haggle_price": ["market"],
    }
    recent_messages = []
    if with_message:
        recent_messages = [
            {
                "sender_id": 2,
                "receiver_id": 1,
                "content": "Can you check the situation near the market?",
            }
        ]
    return {
        "agent_id": 1,
        "name": "Validation Agent",
        "location_id": current_location,
        "location": current_location,
        "latest_event": "ordinary morning validation tick",
        "recent_messages": recent_messages,
        "known_locations": [
            {
                "id": location,
                "name": location.replace("_", " ").title(),
                "aliases": [location],
                "anchor_tile": {"x": index + 1, "y": 1},
                "interaction_ids": [
                    interaction
                    for interaction, allowed in interaction_locations.items()
                    if location in allowed
                ],
                "scene_type": "validation",
            }
            for index, location in enumerate(locations)
        ],
        "known_interactions": [
            {
                "id": interaction,
                "name": interaction.replace("_", " ").title(),
                "allowed_location_ids": allowed,
            }
            for interaction, allowed in interaction_locations.items()
        ],
    }


def mounted_skill_ids_from_config(config_path: Path) -> tuple[list[list[str]], list[str]]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    agents = config.get("agents") or []
    mounted_per_agent: list[list[str]] = []
    errors: list[str] = []
    for agent in agents:
        kwargs = agent.get("kwargs") if isinstance(agent, dict) else {}
        kwargs = kwargs if isinstance(kwargs, dict) else {}
        profile = kwargs.get("profile") if isinstance(kwargs.get("profile"), dict) else {}
        agent_id = agent.get("agent_id") or kwargs.get("id") or "unknown"
        common = kwargs.get("common_skill_ids")
        personal = kwargs.get("skill_ids")
        if profile.get("skills"):
            errors.append(f"agent {agent_id}: profile.skills must not be used")
        if kwargs.get("skill_runtime_skill_names"):
            errors.append(f"agent {agent_id}: skill_runtime_skill_names must not be used")
        if kwargs.get("enable_skill_runtime") is not True:
            errors.append(f"agent {agent_id}: enable_skill_runtime must be true")
        if common != COMMON_SKILL_IDS:
            errors.append(f"agent {agent_id}: common_skill_ids does not match required common set")
        if not isinstance(personal, list) or not personal:
            errors.append(f"agent {agent_id}: skill_ids must be a non-empty list")
            personal = []
        mounted_per_agent.append([*(common if isinstance(common, list) else []), *personal])
    if len({tuple(items) for items in mounted_per_agent}) <= 1:
        errors.append("mounted skills are identical for every agent")
    return mounted_per_agent, errors


def load_skill_json(skill_root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    target = skill_root / "skill.json"
    errors: list[str] = []
    if not target.is_file():
        return None, ["missing skill.json"]
    try:
        parsed = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"skill.json is not valid JSON: {exc}"]
    if not isinstance(parsed, dict):
        return None, ["skill.json must contain a JSON object"]
    missing = sorted(REQUIRED_SKILL_JSON_FIELDS - set(parsed))
    if missing:
        errors.append(f"skill.json missing fields: {', '.join(missing)}")
    if not isinstance(parsed.get("effects"), list) or not parsed.get("effects"):
        errors.append("skill.json effects must be a non-empty list")
    return parsed, errors


def normalize_script_source(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("import ", "from ", "sys.path.", "SKILL_DIR =")):
            continue
        lines.append(line)
    return "\n".join(lines)


def validate_source_independence(custom_skills: list[Any]) -> list[str]:
    errors: list[str] = []
    if not SHARED_RUNTIME.is_file():
        return ["shared runtime helper is missing"]
    shared_source = SHARED_RUNTIME.read_text(encoding="utf-8")
    for token in BANNED_SHARED_RUNTIME_TOKENS:
        if token in shared_source:
            errors.append(f"_shared/agent_skill_runtime.py contains banned centralized behavior token: {token}")

    normalized_hashes: dict[str, list[str]] = {}
    for skill in custom_skills:
        skill_root = Path(skill.path)
        spec, spec_errors = load_skill_json(skill_root)
        errors.extend(f"{skill.name}: {message}" for message in spec_errors)
        if spec is not None:
            if spec.get("skill_id") != skill.name:
                errors.append(f"{skill.name}: skill.json skill_id does not match directory/catalog name")
            spec_effects = set(str(item) for item in spec.get("effects", []))
            declared_effects = set(skill.effects)
            if spec_effects != declared_effects:
                errors.append(f"{skill.name}: skill.json effects do not match SKILL.md effects")
            if bool(spec.get("shared")) != bool(skill.shared):
                errors.append(f"{skill.name}: skill.json shared does not match SKILL.md shared")

        script_path = skill_root / skill.script
        if not script_path.is_file():
            continue
        source = script_path.read_text(encoding="utf-8")
        for pattern in BANNED_SKILL_SCRIPT_PATTERNS:
            if re.search(pattern, source):
                errors.append(f"{skill.name}: script uses banned old shared runtime pattern {pattern!r}")
        normalized = normalize_script_source(source)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        normalized_hashes.setdefault(digest, []).append(skill.name)

    if len(custom_skills) >= 10 and len(normalized_hashes) < 10:
        errors.append(
            "skill scripts are not independent enough after normalization "
            f"({len(normalized_hashes)} unique implementations for {len(custom_skills)} skills)"
        )
    biggest_group = max((names for names in normalized_hashes.values()), key=len, default=[])
    if len(biggest_group) == len(custom_skills):
        errors.append("all skill scripts normalize to the same wrapper implementation")
    return errors


def parse_skill_result(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("stdout did not contain a JSON object")


def validate_skill_result(
    *,
    skill_id: str,
    result: dict[str, Any],
    allowed_effects: set[str],
    observation: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        errors.append("invalid schema_version")
    if result.get("skill_id") != skill_id:
        errors.append("skill_id does not match executed skill")
    known_locations = {
        str(item.get("id") or "")
        for item in observation.get("known_locations", [])
        if isinstance(item, dict)
    }
    known_interactions = {
        str(item.get("id") or ""): item
        for item in observation.get("known_interactions", [])
        if isinstance(item, dict)
    }
    current_location = str(observation.get("location_id") or "")
    world = result.get("world_effect")
    if world is not None:
        if not isinstance(world, dict):
            errors.append("world_effect must be an object or null")
        else:
            effect_type = str(world.get("type") or "")
            if effect_type not in allowed_effects:
                errors.append(f"world effect {effect_type!r} is not declared in SKILL.md")
            elif effect_type == "move":
                location_id = str(world.get("location_id") or world.get("location") or "")
                if location_id not in known_locations:
                    errors.append(f"unknown move location_id: {location_id}")
            elif effect_type == "interact":
                interaction_id = str(world.get("interaction_id") or "")
                interaction = known_interactions.get(interaction_id)
                allowed_locations = interaction.get("allowed_location_ids") if isinstance(interaction, dict) else []
                if not interaction:
                    errors.append(f"unknown interaction_id: {interaction_id}")
                elif allowed_locations and current_location not in allowed_locations:
                    errors.append(f"interaction {interaction_id!r} unavailable at {current_location}")
            elif effect_type != "set_state":
                errors.append(f"unsupported world effect: {effect_type}")
    speech = result.get("speech_effect")
    if speech is not None:
        if not isinstance(speech, dict):
            errors.append("speech_effect must be an object or null")
        else:
            effect_type = str(speech.get("type") or "")
            if effect_type not in allowed_effects:
                errors.append(f"speech effect {effect_type!r} is not declared in SKILL.md")
            elif effect_type == "direct_message" and int(speech.get("receiver_id") or 0) <= 0:
                errors.append("direct_message requires receiver_id")
            elif effect_type == "group_message" and int(speech.get("group_id") or 0) <= 0:
                errors.append("group_message requires group_id")
            elif effect_type not in {"direct_message", "group_message"}:
                errors.append(f"unsupported speech effect: {effect_type}")
    memories = result.get("memory_effects")
    if memories is None:
        errors.append("memory_effects must be present")
    elif not isinstance(memories, list):
        errors.append("memory_effects must be a list")
    elif memories and "remember" not in allowed_effects:
        errors.append("memory_effects returned without declaring remember")
    return errors


def args_for(skill_id: str, work_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    observation = sample_observation(with_message=(skill_id == "social.reply"))
    skill_args: dict[str, Any] = {}
    if skill_id == "map.navigate":
        skill_args = {"location_id": "park"}
    return {
        "agent_id": 1,
        "agent_name": "Validation Agent",
        "profile": {"name": "Validation Agent", "role": "student"},
        "tick": 60,
        "time": "2026-05-11T09:00:00+08:00",
        "observation": observation,
        "agent_work_dir": str(work_dir),
        "pending_interventions": [],
        "broadcast_result": "",
        "selected_skill_id": skill_id,
        "skill_args": skill_args,
        "skill_decision": {
            "selected_skill_id": skill_id,
            "args": skill_args,
            "reason": "validator execution",
            "public_summary": "validator execution",
        },
    }, observation


async def execute_skill(registry: SkillRegistry, skill_id: str, work_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    args, observation = args_for(skill_id, work_dir)
    raw = await registry.execute(skill_id, args, work_dir, timeout_sec=10)
    if not raw.get("ok"):
        raise RuntimeError(raw.get("stderr") or raw.get("error_type") or "skill execution failed")
    return parse_skill_result(str(raw.get("stdout") or "")), observation


async def execute_with_observation(
    registry: SkillRegistry,
    skill_id: str,
    work_dir: Path,
    observation: dict[str, Any],
    skill_args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    args = {
        "agent_id": 1,
        "agent_name": "Validation Agent",
        "profile": {"name": "Validation Agent", "role": "student"},
        "tick": 60,
        "time": "2026-05-11T09:00:00+08:00",
        "observation": observation,
        "agent_work_dir": str(work_dir),
        "pending_interventions": [],
        "broadcast_result": "",
        "selected_skill_id": skill_id,
        "skill_args": skill_args or {},
    }
    raw = await registry.execute(skill_id, args, work_dir, timeout_sec=10)
    if not raw.get("ok"):
        raise RuntimeError(raw.get("stderr") or raw.get("error_type") or "skill execution failed")
    return parse_skill_result(str(raw.get("stdout") or ""))


async def verify_effect_coverage(registry: SkillRegistry, work_dir: Path) -> list[str]:
    coverage_cases = [
        ("move", "routine.daily", {}, sample_observation(current_location="home")),
        (
            "interact",
            "map.navigate",
            {"location_id": "home", "interaction_id": "cook_meal"},
            sample_observation(current_location="home"),
        ),
        ("speech", "social.reply", {}, sample_observation(current_location="home", with_message=True)),
        ("memory", "memory.record", {"content": "coverage memory"}, sample_observation(current_location="home")),
    ]
    errors: list[str] = []
    for label, skill_id, skill_args, observation in coverage_cases:
        args = {
            "agent_id": 1,
            "agent_name": "Validation Agent",
            "profile": {"name": "Validation Agent", "role": "student"},
            "tick": 60,
            "time": "2026-05-11T09:00:00+08:00",
            "observation": observation,
            "agent_work_dir": str(work_dir),
            "pending_interventions": [],
            "broadcast_result": "",
            "selected_skill_id": skill_id,
            "skill_args": skill_args,
        }
        raw = await registry.execute(skill_id, args, work_dir / f"coverage_{label}", timeout_sec=10)
        if not raw.get("ok"):
            errors.append(f"{label}: {skill_id} execution failed: {raw.get('stderr') or raw.get('error_type')}")
            continue
        result = parse_skill_result(str(raw.get("stdout") or ""))
        info = registry.get_skill_info(skill_id, load_content=False)
        allowed = set(info.effects if info else [])
        errors.extend(
            f"{label}: {message}"
            for message in validate_skill_result(
                skill_id=skill_id,
                result=result,
                allowed_effects=allowed,
                observation=observation,
            )
        )
        if label == "move" and (result.get("world_effect") or {}).get("type") != "move":
            errors.append("move coverage did not produce a move world_effect")
        if label == "interact" and (result.get("world_effect") or {}).get("type") != "interact":
            errors.append("interact coverage did not produce an interact world_effect")
        if label == "speech" and not result.get("speech_effect"):
            errors.append("speech coverage did not produce a speech_effect")
        if label == "memory" and not result.get("memory_effects"):
            errors.append("memory coverage did not produce memory_effects")
    return errors


async def verify_personal_skill_divergence(registry: SkillRegistry, work_dir: Path) -> list[str]:
    observation = sample_observation(current_location="home")
    errors: list[str] = []
    try:
        repair = await execute_with_observation(registry, "tools.repair", work_dir / "tools_repair", observation)
        learn = await execute_with_observation(registry, "class.learn", work_dir / "class_learn", observation)
    except Exception as exc:
        return [f"personal divergence execution failed: {exc}"]
    if repair.get("summary") == learn.get("summary"):
        errors.append("tools.repair and class.learn produced the same summary")
    if repair.get("world_effect") == learn.get("world_effect"):
        errors.append("tools.repair and class.learn produced the same world_effect")
    repair_memory = json.dumps(repair.get("memory_effects"), ensure_ascii=False, sort_keys=True)
    learn_memory = json.dumps(learn.get("memory_effects"), ensure_ascii=False, sort_keys=True)
    if repair_memory == learn_memory:
        errors.append("tools.repair and class.learn produced the same memory effects")
    if "repair" not in json.dumps(repair, ensure_ascii=False).lower():
        errors.append("tools.repair result does not contain repair-specific behavior")
    if "class" not in json.dumps(learn, ensure_ascii=False).lower() and "study" not in json.dumps(learn, ensure_ascii=False).lower():
        errors.append("class.learn result does not contain class/study-specific behavior")
    return errors


async def main() -> int:
    registry = SkillRegistry()
    registry.scan_custom(REPO_ROOT)
    custom_skills = [skill for skill in registry.list_all() if skill.source == "custom"]
    skill_by_id = {skill.name: skill for skill in custom_skills}
    errors: list[str] = []
    if len(custom_skills) < 55:
        errors.append(f"expected at least 55 custom executable skills, found {len(custom_skills)}")
    errors.extend(validate_source_independence(custom_skills))

    all_config_paths = sorted(INIT_CONFIG_GLOB.glob("hypothesis_*/experiment_*/init/init_config.json"))
    mounted_per_agent: list[list[str]] = []
    for config_path in all_config_paths or [DEFAULT_INIT_CONFIG]:
        config_mounted, config_errors = mounted_skill_ids_from_config(config_path)
        errors.extend(f"{config_path}: {error}" for error in config_errors)
        mounted_per_agent.extend(config_mounted)
    mounted = sorted({skill_id for mounted_ids in mounted_per_agent for skill_id in mounted_ids})
    for skill_id in mounted:
        if skill_id not in skill_by_id:
            errors.append(f"mounted skill not found in catalog: {skill_id}")
    for skill in custom_skills:
        if not skill.script:
            errors.append(f"{skill.name}: missing script")
        if not skill.effects:
            errors.append(f"{skill.name}: missing effects")
        script_path = Path(skill.path) / skill.script
        if not script_path.is_file():
            errors.append(f"{skill.name}: script not found: {skill.script}")

    with tempfile.TemporaryDirectory(prefix="god-skill-validation-") as temp_dir:
        work_root = Path(temp_dir)
        for index, skill in enumerate(custom_skills, start=1):
            work_dir = work_root / skill.name.replace(".", "_")
            try:
                result, observation = await execute_skill(registry, skill.name, work_dir)
            except Exception as exc:
                errors.append(f"{skill.name}: execution failed: {exc}")
                continue
            errors.extend(
                f"{skill.name}: {message}"
                for message in validate_skill_result(
                    skill_id=skill.name,
                    result=result,
                    allowed_effects=set(skill.effects),
                    observation=observation,
                )
            )
            print(f"[{index:02d}/{len(custom_skills):02d}] ok {skill.name}")
        errors.extend(await verify_effect_coverage(registry, work_root / "coverage"))
        errors.extend(await verify_personal_skill_divergence(registry, work_root / "divergence"))

    if errors:
        print("\nValidation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "\nValidation passed: "
        f"{len(custom_skills)} executable skills, "
        f"{len(mounted_per_agent)} agents, "
        f"{len(mounted)} mounted skill ids."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
