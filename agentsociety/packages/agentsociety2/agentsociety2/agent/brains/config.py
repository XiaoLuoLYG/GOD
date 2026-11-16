"""Backend selection shared by the runtime and dependency-free launchers."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

DEFAULT_BRAIN_NAME = "jiuwenclaw"
BRAIN_ENV_VAR = "GOD_AGENT_BACKEND"
_ALIASES = {
    "jiuwenclaw": "jiuwenclaw",
    "jiuwen_claw": "jiuwenclaw",
    "jiuwenclawagent": "jiuwenclaw",
    "openai_compat": "openai_compat",
    "openaicompat": "openai_compat",
    "openai": "openai_compat",
}

ASK_BACKEND_ENV_VAR = "GOD_AGENT_ASK_BACKEND"


@dataclass(frozen=True)
class ResolvedBrain:
    """A backend name plus non-secret overrides."""

    name: str
    overrides: dict[str, Any]
    source: str


def canonical_brain_name(name: str) -> str:
    """Normalize a backend name. ``JiuwenClawAgent`` stays the default alias."""

    normalized = name.strip().lower().replace("-", "_").replace(" ", "")
    if not normalized:
        return ""
    return _ALIASES.get(normalized, normalized)


def resolve_brain_spec(
    *,
    brain: Any = None,
    agent_backend: Any = None,
    environ: Mapping[str, str] | None = None,
) -> ResolvedBrain:
    """Pick the backend spec. Blank values fall through to the next source."""

    env = os.environ if environ is None else environ
    candidates = (
        ("agent", brain),
        ("experiment", agent_backend),
        ("env", env.get(BRAIN_ENV_VAR)),
    )
    for source, value in candidates:
        parsed = _parse_brain_value(value)
        if parsed is None:
            continue
        name, overrides = parsed
        return ResolvedBrain(name=name, overrides=overrides, source=source)
    return ResolvedBrain(name=DEFAULT_BRAIN_NAME, overrides={}, source="default")


def _parse_brain_value(value: Any) -> tuple[str, dict[str, Any]] | None:
    if value is None:
        return None
    if isinstance(value, str):
        name = canonical_brain_name(value)
        if not name:
            return None
        return name, {}
    if isinstance(value, dict):
        raw_name = value.get("type", value.get("name", ""))
        name = canonical_brain_name(str(raw_name or ""))
        if not name:
            return None
        overrides = {
            key: item
            for key, item in value.items()
            if key not in {"type", "name"}
        }
        return name, overrides
    raise TypeError("brain config must be a string or an object with a type field")


def resolve_ask_brain_spec(
    decision: ResolvedBrain, environ: Mapping[str, str] | None = None
) -> ResolvedBrain | None:
    if decision.name == "codex":
        return None
    env = os.environ if environ is None else environ
    for source, value in (
        (decision.source, decision.overrides.get("ask_backend")),
        ("env", env.get(ASK_BACKEND_ENV_VAR)),
    ):
        parsed = _parse_brain_value(value)
        if parsed is not None:
            name, overrides = parsed
            return ResolvedBrain(name=name, overrides=overrides, source=source)
    return None


def requires_jiuwenclaw(config: dict[str, Any], environ: Mapping[str, str] | None = None) -> bool:
    agents = config.get("agents")
    if not isinstance(agents, list):
        raise ValueError("experiment config requires an agents list")
    required = False
    for agent in agents:
        if not isinstance(agent, dict) or not isinstance(agent.get("kwargs", {}), dict):
            raise ValueError("invalid agent config")
        if agent.get("agent_type") != "JiuwenClawAgent":
            continue
        kwargs = agent.get("kwargs", {})
        decision = resolve_brain_spec(
            brain=kwargs.get("brain"),
            agent_backend=kwargs.get("agent_backend", config.get("agent_backend")),
            environ=environ,
        )
        ask = resolve_ask_brain_spec(decision, environ)
        if decision.name == DEFAULT_BRAIN_NAME or (ask is not None and ask.name == DEFAULT_BRAIN_NAME):
            required = True
    return required


def main() -> None:
    parser = argparse.ArgumentParser(description="Report whether an experiment requires JiuwenClaw")
    parser.add_argument("init_config", type=Path)
    args = parser.parse_args()
    try:
        config = json.loads(args.init_config.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("experiment config must be an object")
        required = requires_jiuwenclaw(config)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(f"unable to resolve experiment backends: {exc}")
    print(int(required))


if __name__ == "__main__":
    main()
