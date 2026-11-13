"""Resolve and construct agent decision backends.

Priority is per-agent ``brain``, then experiment ``agent_backend``, then
``GOD_AGENT_BACKEND``, then ``jiuwenclaw``.
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Any, Mapping

from agentsociety2.agent.brains.base import AgentBrain, AskRequest, SkillChoiceRequest, SkillDecision
from agentsociety2.agent.brains.config import (
    ResolvedBrain,
    canonical_brain_name,
    resolve_ask_brain_spec,
    resolve_brain_spec,
)

logger = logging.getLogger(__name__)

_BRAINS: dict[str, type[AgentBrain]] | None = None
_SCANNED_WORKSPACES: set[str] = set()


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


def create_agent_brains(
    host: Any = None,
    *,
    brain: Any = None,
    agent_backend: Any = None,
    workspace: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> tuple[AgentBrain, AgentBrain]:
    """Construct the decision and optional Ask backends."""
    try:
        resolved = resolve_brain_spec(brain=brain, agent_backend=agent_backend, environ=environ)
        ask = resolve_ask_brain_spec(resolved, environ)
    except (TypeError, ValueError) as exc:
        invalid = UnavailableBrain("invalid", f"invalid agent backend config: {type(exc).__name__}")
        return invalid, invalid

    decision = _instantiate_brain(resolved, host=host, workspace=workspace)
    if ask is None or ask.name == resolved.name == "jiuwenclaw":
        return decision, decision
    return decision, _instantiate_brain(ask, host=host, workspace=workspace)


def _instantiate_brain(resolved: ResolvedBrain, *, host: Any, workspace: Path | None) -> AgentBrain:
    from agentsociety2.agent.brains.jiuwenclaw import JiuwenClawBrain

    try:
        registry = _builtin_brains()
        brain_cls = registry.get(resolved.name)
        if brain_cls is None:
            scan_custom_brains(workspace)
            brain_cls = registry.get(resolved.name)
        if brain_cls is None:
            return UnavailableBrain(resolved.name, f"unknown agent backend: {resolved.name}")
        config = {key: value for key, value in resolved.overrides.items() if key != "ask_backend"}
        if brain_cls is JiuwenClawBrain:
            return brain_cls(host=host, config=config)
        return brain_cls(config=config)
    except Exception as exc:
        logger.warning("agent backend %s failed to load: %s", resolved.name, type(exc).__name__)
        return UnavailableBrain(resolved.name, f"agent backend {resolved.name} failed to load")


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
        from agentsociety2.agent.brains.codex import CodexBrain
        from agentsociety2.agent.brains.command import CommandBrain
        from agentsociety2.agent.brains.decision_api import DecisionAPIBrain, JevBrain, OpenAIDecisionsBrain
        from agentsociety2.agent.brains.jiuwenclaw import JiuwenClawBrain
        from agentsociety2.agent.brains.openai_compat import OpenAICompatBrain

        backends = (
            JiuwenClawBrain, CodexBrain, OpenAICompatBrain, CommandBrain,
            DecisionAPIBrain, JevBrain, OpenAIDecisionsBrain,
        )
        _BRAINS = {backend.name: backend for backend in backends}
    return _BRAINS


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
