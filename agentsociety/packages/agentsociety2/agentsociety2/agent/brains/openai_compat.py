"""OpenAI-compatible decision backend.

Uses the existing ``GOD_LLM_*`` settings. It is not the default and is only
constructed when a config or ``GOD_AGENT_BACKEND`` selects it.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from agentsociety2.agent.brains.base import AgentBrain, AskRequest, SkillChoiceRequest, SkillDecision
from agentsociety2.agent.brains.jiuwenclaw import _decision_from_text

logger = logging.getLogger(__name__)
_DEFAULT_TIMEOUT_S = 60.0


@dataclass(frozen=True)
class LLMSettings:
    api_key: str
    api_base: str
    model: str
    timeout_s: float


class OpenAICompatBrain(AgentBrain):
    """Text backend that reuses the current skill and ask prompts."""

    name = "openai_compat"
    capabilities = frozenset({"choose_skill", "ask"})

    def __init__(self, host: Any = None, config: dict[str, Any] | None = None) -> None:
        self.host = host
        self.config = dict(config or {})

    async def choose_skill(self, req: SkillChoiceRequest) -> SkillDecision:
        prompt = self.host._build_skill_selection_prompt(
            tick=req.tick,
            t=req.time,
            observation=req.observation,
            catalog=req.catalog,
            pending_interventions=req.pending_interventions,
            broadcast_result=req.broadcast_result,
        )
        started = time.perf_counter()
        raw, usage = await self._complete(prompt)
        decision = _decision_from_text(self.host, prompt, raw)
        decision.usage = usage
        decision.latency_ms = (time.perf_counter() - started) * 1000
        _log_timing("choose_skill", decision.latency_ms, self._settings().model)
        return decision

    async def ask(self, req: AskRequest) -> str:
        prompt = self.host._build_ask_prompt(message=req.message, readonly=req.readonly)
        started = time.perf_counter()
        raw, _usage = await self._complete(prompt)
        _log_timing("ask", (time.perf_counter() - started) * 1000, self._settings().model)
        return raw

    def dump(self) -> dict[str, Any]:
        settings = self._settings()
        return {
            "type": self.name,
            "model": settings.model,
            "api_base": settings.api_base,
        }

    def _settings(self) -> LLMSettings:
        return resolve_llm_settings(self.config)

    async def _complete(self, prompt: str) -> tuple[str, dict[str, Any] | None]:
        settings = self._settings()
        if not settings.api_key or not settings.model:
            raise RuntimeError("openai_compat requires GOD_LLM_API_KEY and GOD_LLM_MODEL")
        body = await _post_json(
            _chat_url(settings.api_base),
            settings.api_key,
            {
                "model": settings.model,
                "messages": [{"role": "user", "content": prompt}],
            },
            settings.timeout_s,
        )
        return _message_content(body), _compact_usage(body.get("usage"))


def resolve_llm_settings(config: dict[str, Any] | None = None) -> LLMSettings:
    """Read GOD LLM settings. Overrides may name an env var, not the secret."""

    values = config or {}
    key_env = str(values.get("api_key_env") or "GOD_LLM_API_KEY")
    api_key = os.getenv(key_env, "").strip()
    if not api_key and key_env == "GOD_LLM_API_KEY":
        api_key = os.getenv("AGENTSOCIETY_LLM_API_KEY", "").strip()
    api_base = str(
        values.get("api_base")
        or os.getenv("GOD_LLM_API_BASE")
        or os.getenv("AGENTSOCIETY_LLM_API_BASE")
        or "https://api.openai.com/v1"
    ).strip()
    model = str(
        values.get("model")
        or os.getenv("GOD_LLM_MODEL")
        or os.getenv("AGENTSOCIETY_LLM_MODEL")
        or ""
    ).strip()
    timeout_s = _timeout_s(values.get("timeout_s", values.get("request_timeout", _DEFAULT_TIMEOUT_S)))
    return LLMSettings(api_key=api_key, api_base=api_base, model=model, timeout_s=timeout_s)


def _chat_url(api_base: str) -> str:
    base = api_base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _timeout_s(value: Any) -> float:
    try:
        timeout_s = float(value)
    except (TypeError, ValueError):
        timeout_s = _DEFAULT_TIMEOUT_S
    return max(1.0, timeout_s)


def _message_content(body: dict[str, Any]) -> str:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise RuntimeError("openai_compat response missing choices")
    message = choices[0].get("message")
    if not isinstance(message, dict) or message.get("content") is None:
        raise RuntimeError("openai_compat response missing message content")
    content = message["content"]
    if isinstance(content, str):
        return content
    return str(content)


def _compact_usage(usage: Any) -> dict[str, Any] | None:
    if not isinstance(usage, dict):
        return None
    compact: dict[str, Any] = {}
    if "prompt_tokens" in usage:
        compact["input_tokens"] = usage.get("prompt_tokens")
    if "completion_tokens" in usage:
        compact["output_tokens"] = usage.get("completion_tokens")
    return compact or None


def _log_timing(kind: str, latency_ms: float, model: str) -> None:
    logger.info(
        "[OpenAICompatBrain] request timing: kind=%s total_ms=%.1f model=%s",
        kind,
        latency_ms,
        model,
    )


async def _post_json(
    url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_s: float,
) -> dict[str, Any]:
    """POST a chat completion. Errors omit the response body."""

    import aiohttp

    timeout = aiohttp.ClientTimeout(total=timeout_s)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload, headers=headers) as response:
            status = int(response.status)
            if status < 200 or status >= 300:
                raise RuntimeError(f"openai_compat HTTP {status}")
            data = await response.json(content_type=None)
    if not isinstance(data, dict):
        raise RuntimeError("openai_compat response is not a JSON object")
    return data
