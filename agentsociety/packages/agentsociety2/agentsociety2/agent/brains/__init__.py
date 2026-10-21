"""Agent decision backends.

Builtin names are ``jiuwenclaw`` (default) and ``openai_compat``. Later backends
register through :func:`register_brain` or ``custom/brains/*.py``.
"""

from agentsociety2.agent.brains.base import (
    AgentBrain,
    AskRequest,
    BrainContext,
    SkillChoiceRequest,
    SkillDecision,
)
from agentsociety2.agent.brains.registry import (
    ResolvedBrain,
    canonical_brain_name,
    create_agent_brain,
    inject_experiment_backend,
    register_brain,
    resolve_brain_spec,
    scan_custom_brains,
)

__all__ = [
    "AgentBrain",
    "AskRequest",
    "BrainContext",
    "ResolvedBrain",
    "SkillChoiceRequest",
    "SkillDecision",
    "canonical_brain_name",
    "create_agent_brain",
    "inject_experiment_backend",
    "register_brain",
    "resolve_brain_spec",
    "scan_custom_brains",
]
