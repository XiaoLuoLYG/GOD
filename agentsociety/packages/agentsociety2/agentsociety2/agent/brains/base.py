"""Decision-backend interface.

Backends only suggest a skill or answer a question. GOD still executes skills,
validates effects, and writes them into the world.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar


@dataclass
class BrainContext:
    """Runtime facts a backend may use while a session is open."""

    agent_id: int
    work_dir: str | None
    experiment_context: Any
    config: dict[str, Any] = field(default_factory=dict)
    name: str | None = None


@dataclass
class SkillChoiceRequest:
    """Inputs that used to be passed to ``_select_next_skill``."""

    tick: int
    time: datetime
    profile: Any
    observation: Any
    pending_interventions: list[str]
    broadcast_result: str
    catalog: list[dict[str, Any]]
    mounted_skill_ids: list[str] = field(default_factory=list)
    recent_thread: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SkillDecision:
    """One skill suggestion.

    ``payload`` is the legacy decision dict returned to the skill runtime.
    Extra fields stay on this object so they do not change skill arguments.
    """

    selected_skill_id: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    public_summary: str = ""
    confidence: float | None = None
    raw: str | None = None
    prompt: str | None = None
    parsed: bool = False
    payload: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    latency_ms: float | None = None


@dataclass
class AskRequest:
    """Read-only or advisory question from the Ask panel."""

    message: str
    readonly: bool = True
    response_type: str = "text"
    choices: list[str] | None = None
    time: datetime | None = None


class AgentBrain(ABC):
    """Pluggable decision backend.

    ``start`` and ``close`` default to no work so a backend can stay lazy.
    ``dump`` and ``load`` are optional session hooks.
    """

    name: ClassVar[str]
    capabilities: ClassVar[frozenset[str]]

    async def start(self, ctx: BrainContext) -> None:
        return None

    @abstractmethod
    async def choose_skill(self, req: SkillChoiceRequest) -> SkillDecision:
        """Return a skill suggestion. Raise on transport or protocol failure."""

    @abstractmethod
    async def ask(self, req: AskRequest) -> str:
        """Answer one question. Raise when this backend cannot answer."""

    async def close(self) -> None:
        return None

    def dump(self) -> dict[str, Any]:
        return {}

    def load(self, data: dict[str, Any]) -> None:
        return None
