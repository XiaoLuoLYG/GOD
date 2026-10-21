"""Resolve and construct agent decision backends.

Priority is per-agent ``brain``, then experiment ``agent_backend``, then
``GOD_AGENT_BACKEND``, then ``jiuwenclaw``.
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from agentsociety2.agent.brains.base import AgentBrain, AskRequest, SkillChoiceRequest, SkillDecision

logger = logging.getLogger(__name__)

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
_BRAINS: dict[str, type[AgentBrain]] | None = None
_SCANNED_WORKSPACES: set[str] = set()


@dataclass(frozen=True)
class ResolvedBrain:
    """A backend name plus non-secret overrides."""

    name: str
    overrides: dict[str, Any]
    source: str


class UnavailableBrain(AgentBrain):
    """Backend that fails closed so the agent can use its skill fallback."""

    name = "unavailable"
    capabilities = frozenset({"choose_skill", "ask"})

    def __init__(self, requested_name: str, reason: str) -> None:
        self.name = requested_name or self.__class__.name
        self.reason = reason

    async def choose_skill(self, req: SkillChoiceRequest) -> SkillDecision:
        raise RuntimeError(self.reason)

    async def ask(self, req: AskRequest) -> str:
        raise RuntimeError(self.reason)


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


def register_brain(name: str, brain_cls: type[AgentBrain]) -> None:
    """Register a backend class. Explicit registration may replace a builtin."""

    canonical = canonical_brain_name(name)
    if not canonical:
        raise ValueError("brain name is required")
    _builtin_brains()[canonical] = brain_cls


def brains() -> dict[str, type[AgentBrain]]:
    """Return the registered backend classes."""

    return dict(_builtin_brains())


def scan_custom_brains(workspace: Path | None) -> None:
    """Load ``custom/brains/*.py`` once. Builtin names are left in place."""

    if workspace is None:
        return
    key = str(Path(workspace).resolve())
    if key in _SCANNED_WORKSPACES:
        return
    _SCANNED_WORKSPACES.add(key)
    directory = Path(workspace) / "custom" / "brains"
    if not directory.is_dir():
        return
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        _load_custom_brain_module(path)


def create_agent_brain(
    host: Any,
    *,
    brain: Any = None,
    agent_backend: Any = None,
    workspace: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> AgentBrain:
    """Build a backend. Construction failure becomes an unavailable backend."""

    try:
        resolved = resolve_brain_spec(
            brain=brain,
            agent_backend=agent_backend,
            environ=environ,
        )
    except Exception as exc:
        logger.warning("agent backend config failed: %s", type(exc).__name__)
        return UnavailableBrain("invalid", f"invalid agent backend config: {type(exc).__name__}")
    try:
        return instantiate_brain(resolved, host=host, workspace=workspace)
    except Exception as exc:
        logger.warning("agent backend %s failed to load: %s", resolved.name, type(exc).__name__)
        return UnavailableBrain(resolved.name, f"agent backend {resolved.name} failed to load")


def instantiate_brain(
    resolved: ResolvedBrain,
    *,
    host: Any,
    workspace: Path | None = None,
) -> AgentBrain:
    """Construct a resolved backend, scanning custom modules only if needed."""

    registry = _builtin_brains()
    brain_cls = registry.get(resolved.name)
    if brain_cls is None:
        scan_custom_brains(workspace)
        brain_cls = registry.get(resolved.name)
    if brain_cls is None:
        return UnavailableBrain(resolved.name, f"unknown agent backend: {resolved.name}")
    return brain_cls(host=host, config=dict(resolved.overrides))


def inject_experiment_backend(
    agent_class: type,
    init_kwargs: dict[str, Any],
    agent_backend: Any,
) -> dict[str, Any]:
    """Pass an experiment backend only to agents that accept it."""

    if not agent_backend or "agent_backend" in init_kwargs:
        return init_kwargs
    try:
        parameters = inspect.signature(agent_class.__init__).parameters
    except (TypeError, ValueError):
        return init_kwargs
    accepts = "agent_backend" in parameters or any(
        item.kind is inspect.Parameter.VAR_KEYWORD for item in parameters.values()
    )
    if not accepts:
        return init_kwargs
    updated = dict(init_kwargs)
    updated["agent_backend"] = agent_backend
    return updated


def _builtin_brains() -> dict[str, type[AgentBrain]]:
    global _BRAINS
    if _BRAINS is None:
        from agentsociety2.agent.brains.jiuwenclaw import JiuwenClawBrain
        from agentsociety2.agent.brains.openai_compat import OpenAICompatBrain

        _BRAINS = {
            JiuwenClawBrain.name: JiuwenClawBrain,
            OpenAICompatBrain.name: OpenAICompatBrain,
        }
    return _BRAINS


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


def _load_custom_brain_module(path: Path) -> None:
    module_name = f"god_custom_brain_{path.stem}_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        logger.warning("custom brain import failed: %s %s", path.name, type(exc).__name__)
        return
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ != module.__name__:
            continue
        if not issubclass(obj, AgentBrain) or obj is AgentBrain:
            continue
        raw_name = getattr(obj, "name", "")
        if not isinstance(raw_name, str):
            continue
        canonical = canonical_brain_name(raw_name)
        if not canonical or canonical in _builtin_brains():
            continue
        _builtin_brains()[canonical] = obj
