"""Choice-only backends for System One and OpenAI Decisions."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from agentsociety2.agent.brains.base import AgentBrain, BrainContext, SkillChoiceRequest, SkillDecision
from agentsociety2.agent.brains.http import post_json

JEV_URL = "https://api.typesafe.ai/v1/systemone"
OPENAI_DECISIONS_URL = "https://api.openai.com/v1/decisions"
QUESTION = "Choose the mounted skill that best fits the agent's current situation and instructions."


class DecisionAPIBrain(AgentBrain):
    """Use a locally configured System One-compatible endpoint."""

    name = "decision_api"
    capabilities = frozenset({"choose_skill"})
    context: BrainContext | None = None

    async def start(self, ctx: BrainContext) -> None:
        self.context = ctx

    def _connection(self) -> tuple[str, str, str]:
        return (
            os.getenv("GOD_DECISION_API_URL", "").strip(),
            os.getenv("GOD_DECISION_API_KEY", "").strip(),
            str(self.config.get("model") or os.getenv("GOD_DECISION_MODEL", "")).strip(),
        )

    async def choose_skill(self, req: SkillChoiceRequest) -> SkillDecision:
        url, key, model = self._connection()
        if not (url and key and model):
            raise RuntimeError(f"{self.name} requires a locally configured URL, API key and model")
        choices = _eligible_choices(req)
        state = {
            "agent_id": self.context.agent_id if self.context else None,
            "profile": req.profile,
            "experiment_context": self.context.experiment_context if self.context else None,
            "observation": req.observation,
            "time": req.time.isoformat(),
            "tick": req.tick,
            "pending_interventions": req.pending_interventions,
            "broadcast_result": req.broadcast_result,
        }
        started = time.perf_counter()
        answer, usage = await self._choose(url, key, model, state, choices)
        skill = answer.get("choice")
        confidence = answer.get("confidence")
        if answer.get("type") != "choice" or not isinstance(skill, str) or skill not in choices:
            raise RuntimeError(f"{self.name} returned an invalid skill choice")
        if confidence is not None and (type(confidence) not in (int, float) or not 0 <= confidence <= 1):
            raise RuntimeError(f"{self.name} returned invalid confidence")
        return SkillDecision(
            selected_skill_id=skill,
            confidence=confidence,
            usage=usage if isinstance(usage, dict) else None,
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    async def _choose(
        self, url: str, key: str, model: str, state: dict[str, Any], choices: dict[str, str]
    ) -> tuple[dict[str, Any], Any]:
        data = await post_json(url, key, {
            "model": model,
            "state": state,
            "questions": {"skill": {"type": "choice", "instructions": QUESTION, "criteria": choices}},
        }, timeout_s=5)
        result = data.get("result", data)
        if not isinstance(result, dict) or not isinstance(result.get("answers"), dict):
            raise RuntimeError(f"{self.name} response is missing answers")
        answer = result["answers"].get("skill")
        return answer if isinstance(answer, dict) else {}, result.get("usage")


class JevBrain(DecisionAPIBrain):
    name = "jev"

    def _connection(self) -> tuple[str, str, str]:
        return (
            JEV_URL,
            os.getenv("TYPESAFE_API_KEY", "").strip(),
            str(self.config.get("model") or os.getenv("GOD_JEV_MODEL") or "jev-latest").strip(),
        )


class OpenAIDecisionsBrain(DecisionAPIBrain):
    name = "openai_decisions"

    def _connection(self) -> tuple[str, str, str]:
        local_url = os.getenv("GOD_OPENAI_DECISIONS_URL", "").strip()
        key = os.getenv("GOD_OPENAI_DECISIONS_API_KEY", "").strip()
        if not local_url and not key:
            key = os.getenv("OPENAI_API_KEY", "").strip()
        return local_url or OPENAI_DECISIONS_URL, key, "gpt-6-luna"

    async def _choose(
        self, url: str, key: str, model: str, state: dict[str, Any], choices: dict[str, str]
    ) -> tuple[dict[str, Any], Any]:
        data = await post_json(url, key, {
            "model": model,
            "input": json.dumps(state, ensure_ascii=False),
            "questions": [{
                "name": "skill",
                "type": "choice",
                "instructions": QUESTION,
                "choices": [{"value": value, "description": description} for value, description in choices.items()],
            }],
        }, timeout_s=10)
        answers = data.get("answers")
        if not isinstance(answers, list):
            raise RuntimeError("OpenAI Decisions response is missing answers")
        answer = next((item for item in answers if isinstance(item, dict) and item.get("name") == "skill"), {})
        return answer, data.get("usage")


def _eligible_choices(req: SkillChoiceRequest) -> dict[str, str]:
    mounted = set(req.mounted_skill_ids)
    choices = {}
    for item in req.catalog:
        name = item.get("name")
        schema = item.get("args_schema")
        if name in mounted and not (isinstance(schema, dict) and schema.get("required")):
            choices[name] = str(item.get("description") or name)
    if not 1 <= len(choices) <= 255:
        raise RuntimeError("choice API requires 1–255 mounted skills with no required arguments")
    return choices
