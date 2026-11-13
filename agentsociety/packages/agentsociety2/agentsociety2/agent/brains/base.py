"""Decision-backend interface.

Backends only suggest a skill or answer a question. GOD still executes skills,
validates effects, and writes them into the world.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar


@dataclass
class BrainContext:
    """Runtime facts a backend may use while a session is open."""

    agent_id: int
    work_dir: str | None
    experiment_context: Any
    name: str | None = None
    enable_memory: bool = True


@dataclass
class SkillChoiceRequest:
    """Current simulation state and the mounted skill choices."""

    tick: int
    time: datetime
    profile: Any
    observation: Any
    pending_interventions: list[str]
    broadcast_result: str
    catalog: list[dict[str, Any]]
    mounted_skill_ids: list[str] = field(default_factory=list)
    recent_thread: list[dict[str, Any]] = field(default_factory=list)
    prompt: str = ""


@dataclass
class SkillDecision:
    """A skill selection with optional provider diagnostics."""

    selected_skill_id: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    public_summary: str = ""
    confidence: float | None = None
    raw: str | None = None
    prompt: str | None = None
    usage: dict[str, Any] | None = None
    latency_ms: float | None = None

    def as_dict(self) -> dict[str, Any]:
        result = {
            "selected_skill_id": self.selected_skill_id,
            "args": self.args,
            "reason": self.reason,
            "public_summary": self.public_summary,
        }
        for name in ("confidence", "usage", "latency_ms"):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        return result


def decision_from_text(prompt: str, raw: str) -> SkillDecision:
    value = extract_json_object(raw) or {}
    skill = value.get("selected_skill_id")
    args = value.get("args")
    return SkillDecision(
        selected_skill_id=skill.strip() if isinstance(skill, str) else "",
        args=args if isinstance(args, dict) else {},
        reason=str(value.get("reason") or ""),
        public_summary=str(value.get("public_summary") or ""),
        raw=raw,
        prompt=prompt,
    )


def extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fence:
        stripped = fence.group(1).strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    start = stripped.find("{")
    while start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(stripped[start:])
            return obj
        except json.JSONDecodeError:
            start = stripped.find("{", start + 1)
    return None


@dataclass
class AskRequest:
    """Read-only or advisory question from the Ask panel."""

    message: str
    readonly: bool = True
    response_type: str = "text"
    choices: list[str] | None = None
    time: datetime | None = None
    prompt: str = ""


class AgentBrain:
    """Pluggable decision backend.

    ``start`` and ``close`` default to no work so a backend can stay lazy.
    ``dump`` and ``load`` are optional session hooks.
    """

    name: ClassVar[str]
    capabilities: ClassVar[frozenset[str]] = frozenset()

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = dict(config or {})

    async def start(self, ctx: BrainContext) -> None:
        return None

    async def choose_skill(self, req: SkillChoiceRequest) -> SkillDecision:
        raise NotImplementedError(f"{self.name} does not support skill selection")

    async def ask(self, req: AskRequest) -> str:
        raise NotImplementedError(f"{self.name} does not support Ask")

    async def close(self) -> None:
        return None

    def dump(self) -> dict[str, Any]:
        return {}

    def load(self, data: dict[str, Any]) -> None:
        return None
