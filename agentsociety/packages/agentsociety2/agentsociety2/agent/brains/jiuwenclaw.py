"""JiuwenClaw decision backend.

The websocket client is the previous ``JiuwenClawAgent`` transport, moved here
without a protocol change. The connection is still opened on the first request.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any
from urllib.parse import urlsplit

from agentsociety2.agent.brains.base import (
    AgentBrain,
    AskRequest,
    BrainContext,
    SkillChoiceRequest,
    SkillDecision,
)

_HOST_FIELDS = {
    "jiuwenclaw_ws_url": "_jiuwenclaw_ws_url",
    "session_id": "_session_id",
    "mode": "_mode",
    "channel_id": "_channel_id",
    "request_timeout": "_request_timeout",
    "trusted_dirs": "_trusted_dirs",
    "enable_memory": "_enable_memory",
}


class JiuwenClawBrain(AgentBrain):
    """Default backend. Session memory stays in the JiuwenClaw server."""

    name = "jiuwenclaw"
    capabilities = frozenset({"choose_skill", "ask", "memory"})

    def __init__(self, host: Any = None, config: dict[str, Any] | None = None) -> None:
        self.host = host
        self.config = dict(config or {})
        self.context: BrainContext | None = None
        self._apply_overrides(self.config)

    async def start(self, ctx: BrainContext) -> None:
        self.context = ctx

    async def choose_skill(self, req: SkillChoiceRequest) -> SkillDecision:
        prompt = self.host._build_skill_selection_prompt(
            tick=req.tick,
            t=req.time,
            observation=req.observation,
            catalog=req.catalog,
            pending_interventions=req.pending_interventions,
            broadcast_result=req.broadcast_result,
        )
        raw = await self.host._send_jiuwenclaw_request(prompt)
        return _decision_from_text(self.host, prompt, raw)

    async def ask(self, req: AskRequest) -> str:
        prompt = self.host._build_ask_prompt(message=req.message, readonly=req.readonly)
        return await self.host._send_jiuwenclaw_request(prompt)

    async def close(self) -> None:
        await close_websocket(self.host)

    def dump(self) -> dict[str, Any]:
        host = self.host
        if host is None:
            return {"type": self.name}
        return {
            "type": self.name,
            "jiuwenclaw_ws_url": host._jiuwenclaw_ws_url,
            "session_id": host._session_id,
            "mode": host._mode,
            "channel_id": host._channel_id,
            "request_timeout": host._request_timeout,
            "enable_memory": host._enable_memory,
        }

    def load(self, data: dict[str, Any]) -> None:
        if isinstance(data, dict):
            self._apply_overrides(data)

    def _apply_overrides(self, values: dict[str, Any]) -> None:
        host = self.host
        if host is None:
            return
        for key, attr in _HOST_FIELDS.items():
            if key not in values:
                continue
            value = values[key]
            if key == "request_timeout":
                value = float(value)
            elif key == "enable_memory":
                value = bool(value)
            elif key == "trusted_dirs" and isinstance(value, list):
                value = [str(item) for item in value if str(item)]
            setattr(host, attr, value)


def _decision_from_text(host: Any, prompt: str, raw: str) -> SkillDecision:
    parsed = host._parse_step_decision(raw)
    if isinstance(parsed, dict) and parsed.get("_parsed"):
        payload = dict(parsed)
        payload.pop("_parsed", None)
        args = payload.get("args")
        return SkillDecision(
            selected_skill_id=str(payload.get("selected_skill_id") or ""),
            args=args if isinstance(args, dict) else {},
            reason=str(payload.get("reason") or ""),
            public_summary=str(payload.get("public_summary") or ""),
            raw=raw,
            prompt=prompt,
            parsed=True,
            payload=payload,
        )
    return SkillDecision(raw=raw, prompt=prompt, parsed=False, payload=None)


async def send_request(agent: Any, prompt: str) -> str:
    """Send one JiuwenClaw chat request and return the assembled text."""

    request_id = f"agentsociety_{agent.id}_{uuid.uuid4().hex[:12]}"
    payload = {
        "request_id": request_id,
        "channel_id": agent._channel_id,
        "session_id": agent._session_id,
        "req_method": "chat.send",
        "params": {
            "query": prompt,
            "mode": agent._mode,
            "trusted_dirs": list(agent._trusted_dirs),
        },
        "is_stream": True,
        "timestamp": time.time(),
        "metadata": {
            "source": "agentsociety",
            "agent_id": agent.id,
            "agent_name": agent.name,
            "enable_memory": agent._enable_memory,
        },
    }

    request_started_at = time.perf_counter()
    queue_ms = 0.0
    status = "error"
    semaphore, concurrency_limit = agent._request_semaphore_for_current_loop()
    try:
        async with semaphore:
            queue_ms = (time.perf_counter() - request_started_at) * 1000
            async with agent._ws_lock:
                response = await _exchange_with_deadline(agent, payload, request_id)
            content = agent._extract_response_content(response)
            status = "success"
            return content
    finally:
        total_ms = (time.perf_counter() - request_started_at) * 1000
        logging.getLogger(type(agent).__module__).info(
            "[JiuwenClawAgent] request timing: agent_id=%s request_id=%s "
            "status=%s queue_ms=%.1f total_ms=%.1f prompt_chars=%s "
            "concurrency_limit=%s",
            agent.id,
            request_id,
            status,
            queue_ms,
            total_ms,
            len(prompt),
            concurrency_limit,
        )


def _connection_is_usable(ws: Any) -> bool:
    """A peer close (1001 going away) leaves the object set but not usable."""

    state = getattr(ws, "state", None)
    if state is None:
        return True
    name = getattr(state, "name", "")
    if isinstance(name, str) and name:
        return name == "OPEN"
    return True


def _is_connection_closed(exc: BaseException) -> bool:
    return type(exc).__name__ in {
        "ConnectionClosed",
        "ConnectionClosedOK",
        "ConnectionClosedError",
    }


async def _exchange_once(agent: Any, payload: dict, request_id: str) -> dict:
    await agent._ensure_connected()
    await agent._ws.send(json.dumps(payload, ensure_ascii=False))
    return await agent._receive_matching_response(request_id)


async def _exchange_with_deadline(agent: Any, payload: dict, request_id: str) -> dict:
    """Bound connect, send, and recv by the existing request timeout.

    An open socket that only delivers non-final keepalive chunks never raises.
    The deadline still ends the attempt. A socket the peer already closed fails
    in milliseconds; retry that case once on a new connection.
    """

    loop = asyncio.get_running_loop()
    timeout = agent._request_timeout
    for attempt in (1, 2):
        started = loop.time()
        try:
            return await asyncio.wait_for(
                _exchange_once(agent, payload, request_id),
                timeout=timeout,
            )
        except Exception as exc:
            await agent._reset_websocket()
            elapsed = loop.time() - started
            if attempt == 1 and _is_connection_closed(exc) and elapsed < 2:
                continue
            raise
    raise RuntimeError("JiuwenClaw request was not sent")


async def ensure_connected(agent: Any) -> None:
    if agent._ws is not None and _connection_is_usable(agent._ws):
        return
    if agent._ws is not None:
        await reset_websocket(agent)
    agent._ws = await agent._open_websocket(agent._jiuwenclaw_ws_url)
    await agent._consume_connection_ack_if_present()


async def open_websocket(uri: str) -> Any:
    origin = build_ws_origin(uri)
    try:
        from websockets.asyncio.client import connect
    except Exception:
        from websockets import connect

    # Match AgentServer defaults (ping_interval=30, ping_timeout=300).
    # Library defaults (~20s) cause keepalive ping timeout while agent.plan
    # is blocked on long multi-turn LLM+tool streams under 10-way load.
    return await connect(
        uri,
        origin=origin,
        ping_interval=30,
        ping_timeout=300,
    )


def build_ws_origin(uri: str) -> str | None:
    """Match JiuwenClaw AgentServer's localhost Origin check."""

    try:
        parsed = urlsplit(uri)
    except ValueError:
        return None
    if not parsed.netloc:
        return None
    scheme = "https" if parsed.scheme == "wss" else "http"
    return f"{scheme}://{parsed.netloc}"


async def consume_connection_ack_if_present(agent: Any) -> None:
    try:
        raw = await asyncio.wait_for(agent._ws.recv(), timeout=2.0)
    except asyncio.TimeoutError:
        return
    data = decode_wire_message(raw)
    if data.get("type") == "event" and data.get("event") == "connection.ack":
        return
    agent._pending_response = data


async def receive_matching_response(agent: Any, request_id: str) -> dict:
    content_parts: list[str] = []
    final_content: str = ""
    pending = getattr(agent, "_pending_response", None)
    if isinstance(pending, dict):
        agent._pending_response = None
        if str(pending.get("request_id") or "") == request_id:
            piece = agent._extract_stream_piece(pending)
            if piece["final"]:
                final_content = piece["text"]
            elif piece["text"]:
                content_parts.append(piece["text"])
            if pending.get("is_final"):
                return agent._with_stream_content(
                    pending,
                    final_content or "".join(content_parts),
                )

    while True:
        raw = await agent._ws.recv()
        data = decode_wire_message(raw)
        if data.get("type") == "event":
            continue
        if str(data.get("request_id") or "") == request_id:
            piece = agent._extract_stream_piece(data)
            if piece["final"]:
                final_content = piece["text"]
            elif piece["text"]:
                content_parts.append(piece["text"])
            if data.get("is_final"):
                return agent._with_stream_content(
                    data,
                    final_content or "".join(content_parts),
                )


def decode_wire_message(raw: str | bytes) -> dict:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("JiuwenClaw WebSocket response must be a JSON object")
    return data


def extract_response_content(response: dict) -> str:
    if "ok" in response:
        if not response.get("ok", True):
            payload = response.get("payload") or {}
            raise RuntimeError(str(payload.get("error") or payload))
        payload = response.get("payload") or {}
        return str(payload.get("content") or payload.get("result") or payload)

    body = response.get("body") or {}
    status = str(response.get("status") or "")
    response_kind = str(response.get("response_kind") or "")
    if status == "failed" or response_kind.endswith(".error"):
        raise RuntimeError(str(body.get("message") or body.get("error") or body))

    result = body.get("result")
    if isinstance(result, dict):
        if "content" in result:
            content = result["content"]
            if isinstance(content, dict):
                if "output" in content:
                    return str(content["output"])
                if "content" in content:
                    return str(content["content"])
            return str(content)
        return json.dumps(result, ensure_ascii=False)
    if result is not None:
        return str(result)
    if "content" in body:
        return str(body["content"])
    return json.dumps(body, ensure_ascii=False)


async def reset_websocket(agent: Any) -> None:
    if agent._ws is None:
        return
    close = getattr(agent._ws, "close", None)
    try:
        if callable(close):
            await close()
    finally:
        agent._ws = None
        agent._pending_response = None


async def close_websocket(agent: Any) -> None:
    if agent is None or agent._ws is None:
        return
    close = getattr(agent._ws, "close", None)
    if callable(close):
        await close()
    agent._ws = None


def with_stream_content(response: dict, content: str) -> dict:
    if not content:
        return response
    next_response = dict(response)
    body = dict(next_response.get("body") or {})
    body["result"] = {"content": content}
    next_response["body"] = body
    return next_response


def extract_stream_piece(response: dict) -> dict[str, Any]:
    body = response.get("body") or {}
    delta = body.get("delta")
    if isinstance(delta, dict):
        event_type = str(delta.get("event_type") or body.get("event_type") or "")
        content = delta.get("content")
        if content is None:
            content = delta.get("delta")
        if event_type == "chat.final" and content is not None:
            return {"text": str(content), "final": True}
        if event_type in {"chat.delta", "text.delta"} and content is not None:
            return {"text": str(content), "final": False}
    if body.get("delta_kind") == "text" and isinstance(delta, str):
        return {"text": delta, "final": False}
    payload = response.get("payload")
    if isinstance(payload, dict):
        event_type = str(payload.get("event_type") or "")
        content = payload.get("content")
        if event_type == "chat.final" and content is not None:
            return {"text": str(content), "final": True}
        if event_type == "chat.delta" and content is not None:
            return {"text": str(content), "final": False}
    return {"text": "", "final": False}
