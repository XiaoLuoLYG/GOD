#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR.parent / "_shared"))

from agent_skill_runtime import (  # noqa: E402
    build_skill_result,
    emit_result,
    load_local_skill_spec,
    memory_effect,
    observation_from,
    parse_args,
    skill_args_from,
)

SKILL_ID = "social.reply"


def recent_external_messages(args: dict, observation: dict) -> list[dict]:
    agent_id = int(args.get("agent_id") or observation.get("agent_id") or 0)
    messages = []
    for item in observation.get("recent_messages", []) or []:
        if isinstance(item, dict) and int(item.get("sender_id") or -1) != agent_id:
            messages.append(item)
    return messages


def build_reply(args: dict, message: dict, spec: dict) -> str:
    requested = str(skill_args_from(args).get("content") or "").strip()
    if requested:
        return requested
    content = str(message.get("content") or "").strip()
    if content:
        return f"我收到了：{content[:40]}。我会结合当前情况继续处理。"
    return str(spec.get("speech") or "我收到了，会继续留意。")


def main() -> int:
    args = parse_args()
    observation = observation_from(args)
    spec = load_local_skill_spec(SKILL_DIR)
    messages = recent_external_messages(args, observation)
    if messages:
        last = messages[-1]
        reply = build_reply(args, last, spec)
        if last.get("group_id") is not None:
            speech = {"type": "group_message", "group_id": int(last.get("group_id") or 1), "content": reply}
        else:
            speech = {"type": "direct_message", "receiver_id": int(last.get("sender_id") or 0), "content": reply}
        message_text = str(last.get("content") or "")[:80]
        result = build_skill_result(
            skill_id=SKILL_ID,
            summary="reply to a recent message",
            reason="A recent message from another participant needs an explicit reply.",
            speech_effect=speech,
            memory_effects=[memory_effect(SKILL_ID, spec["memory_template"].format(message=message_text))],
            confidence=0.86,
        )
    else:
        result = build_skill_result(
            skill_id=SKILL_ID,
            summary="stay socially attentive",
            reason="No direct or group message currently needs a reply.",
            world_effect={"type": "set_state", "action": "listening for nearby social cues", "status": spec["status"], "emotion": spec["emotion"], "reason": "social.reply: no pending message"},
            memory_effects=[memory_effect(SKILL_ID, "No reply was needed this step.")],
            confidence=0.55,
        )
    return emit_result(args, SKILL_ID, result)


if __name__ == "__main__":
    raise SystemExit(main())
