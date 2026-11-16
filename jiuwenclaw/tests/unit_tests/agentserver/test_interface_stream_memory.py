# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Regression tests for bounded stream buffering."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from jiuwenswarm.common.schema.agent import AgentRequest, AgentResponseChunk
from jiuwenswarm.server.runtime.agent_adapter import interface as interface_module
from jiuwenswarm.server.runtime.session import session_history


@pytest.mark.asyncio
async def test_auto_memory_uses_live_session_adapter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    child_adapter = object()
    extraction_started = asyncio.Event()
    captured: dict[str, object] = {}

    class RootAdapter:
        @staticmethod
        def _get_cached_session_adapter(session_id: str):
            assert session_id == "sess-auto-memory"
            return child_adapter

    async def fake_execute_auto_memory_extraction(**kwargs) -> None:
        captured.update(kwargs)
        extraction_started.set()

    monkeypatch.setattr(
        session_history,
        "read_session_history_records",
        lambda _session_id: [{"role": "user", "content": "remember this"}],
    )
    monkeypatch.setattr(
        interface_module,
        "_execute_auto_memory_extraction",
        fake_execute_auto_memory_extraction,
    )

    request = AgentRequest(
        request_id="req-auto-memory",
        channel_id="tui",
        session_id="sess-auto-memory",
        params={"project_dir": str(tmp_path), "mode": "code.normal"},
    )

    interface_module._trigger_auto_memory_extraction(
        RootAdapter(),
        request,
        "sess-auto-memory",
    )
    await asyncio.wait_for(extraction_started.wait(), timeout=1.0)

    assert captured["parent_agent"] is child_adapter


@pytest.mark.asyncio
async def test_auto_memory_keeps_adapter_without_session_cache_accessor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    adapter = object()
    extraction_started = asyncio.Event()
    captured: dict[str, object] = {}

    async def fake_execute_auto_memory_extraction(**kwargs) -> None:
        captured.update(kwargs)
        extraction_started.set()

    monkeypatch.setattr(
        session_history,
        "read_session_history_records",
        lambda _session_id: [{"role": "user", "content": "remember this"}],
    )
    monkeypatch.setattr(
        interface_module,
        "_execute_auto_memory_extraction",
        fake_execute_auto_memory_extraction,
    )

    request = AgentRequest(
        request_id="req-auto-memory-fallback",
        channel_id="tui",
        session_id="sess-auto-memory-fallback",
        params={"project_dir": str(tmp_path), "mode": "code.normal"},
    )

    interface_module._trigger_auto_memory_extraction(
        adapter,
        request,
        "sess-auto-memory-fallback",
    )
    await asyncio.wait_for(extraction_started.wait(), timeout=1.0)

    assert captured["parent_agent"] is adapter


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event_type", "payload_kind"),
    [
        ("chat.final", "chunk"),
        ("chat.error", "chunk"),
        ("chat.error", "dict"),
    ],
)
async def test_process_message_stream_uses_bounded_handoff_queue(
    monkeypatch: pytest.MonkeyPatch,
    event_type: str,
    payload_kind: str,
) -> None:
    real_queue = asyncio.Queue
    created_queues: list[asyncio.Queue] = []

    def queue_factory(*args, **kwargs):
        queue = real_queue(*args, **kwargs)
        created_queues.append(queue)
        return queue

    class FakeAdapter:
        @staticmethod
        async def process_message_stream_impl(*_args, **_kwargs):
            payload = {"event_type": event_type, "content": "done"}
            if payload_kind == "chunk":
                yield AgentResponseChunk(
                    request_id="req-bounded-stream",
                    channel_id="tui",
                    payload=payload,
                    is_complete=False,
                )
            else:
                yield payload

    monkeypatch.setattr(interface_module.asyncio, "Queue", queue_factory)
    monkeypatch.setattr(
        interface_module.JiuWenSwarm,
        "_ensure_adapter",
        lambda *_args, **_kwargs: FakeAdapter(),
    )
    monkeypatch.setattr(
        interface_module,
        "get_config",
        lambda: {"preferred_language": "zh", "memory": {"mode": "disabled"}},
    )
    monkeypatch.setattr(interface_module, "get_memory_mode", lambda _config: "disabled")
    monkeypatch.setattr(interface_module, "append_history_record", lambda **_kwargs: None)

    swarm = interface_module.JiuWenSwarm()
    request = AgentRequest(
        request_id="req-bounded-stream",
        channel_id="tui",
        session_id="sess-bounded-stream",
        params={"query": "hello", "mode": "agent"},
        is_stream=True,
    )

    stream = swarm.process_message_stream(request)
    final_chunk = await anext(stream)
    await stream.aclose()

    assert final_chunk.payload["event_type"] == event_type
    assert created_queues
    assert created_queues[0].maxsize == swarm.STREAM_QUEUE_MAXSIZE
    assert created_queues[0].maxsize > 0


@pytest.mark.asyncio
async def test_stream_input_error_returns_error_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        interface_module.JiuWenSwarm,
        "_ensure_adapter",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(interface_module, "append_history_record", lambda **_kwargs: None)
    swarm = interface_module.JiuWenSwarm()

    def reject_inputs(_request):
        raise interface_module._TeamPlanApprovalPayloadError("invalid approval")

    monkeypatch.setattr(swarm, "_build_inputs", reject_inputs)
    request = AgentRequest(
        request_id="req-invalid-input",
        channel_id="tui",
        session_id="sess-invalid-input",
        params={"query": "hello", "mode": "agent"},
        is_stream=True,
    )

    chunks = [chunk async for chunk in swarm.process_message_stream(request)]

    assert chunks[0].payload["event_type"] == "chat.error"


@pytest.mark.asyncio
async def test_empty_final_keeps_accumulated_delta_for_post_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finalized_inputs: list[str] = []

    class FakeAdapter:
        @staticmethod
        async def process_message_stream_impl(*_args, **_kwargs):
            yield AgentResponseChunk(
                request_id="req-empty-final",
                channel_id="tui",
                payload={"event_type": "chat.delta", "content": "complete answer"},
                is_complete=False,
            )
            yield AgentResponseChunk(
                request_id="req-empty-final",
                channel_id="tui",
                payload={"event_type": "chat.final", "content": ""},
                is_complete=False,
            )

    async def fake_finalize(content: str, **_kwargs) -> str:
        finalized_inputs.append(content)
        return f"{content} repaired"

    monkeypatch.setattr(
        interface_module.JiuWenSwarm,
        "_ensure_adapter",
        lambda *_args, **_kwargs: FakeAdapter(),
    )
    monkeypatch.setattr(
        interface_module,
        "get_config",
        lambda: {"preferred_language": "zh", "memory": {"mode": "disabled"}},
    )
    monkeypatch.setattr(interface_module, "get_memory_mode", lambda _config: "disabled")
    monkeypatch.setattr(interface_module, "append_history_record", lambda **_kwargs: None)
    monkeypatch.setattr(interface_module, "finalize_assistant_response_if_a2ui", fake_finalize)

    swarm = interface_module.JiuWenSwarm()
    request = AgentRequest(
        request_id="req-empty-final",
        channel_id="tui",
        session_id="sess-empty-final",
        params={"query": "hello", "mode": "agent"},
        is_stream=True,
    )

    stream = swarm.process_message_stream(request)
    await anext(stream)  # accumulated delta
    await anext(stream)  # empty producer final
    repaired_final = await anext(stream)

    assert finalized_inputs == ["complete answer"]
    assert repaired_final.payload["content"] == "complete answer repaired"
    await stream.aclose()


@pytest.mark.asyncio
async def test_later_empty_final_keeps_last_nonempty_final_for_post_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finalized_inputs: list[str] = []

    class FakeAdapter:
        @staticmethod
        async def process_message_stream_impl(*_args, **_kwargs):
            yield AgentResponseChunk(
                request_id="req-repeated-final",
                channel_id="tui",
                payload={"event_type": "chat.delta", "content": "draft answer"},
                is_complete=False,
            )
            yield AgentResponseChunk(
                request_id="req-repeated-final",
                channel_id="tui",
                payload={"event_type": "chat.final", "content": "authoritative answer"},
                is_complete=False,
            )
            yield AgentResponseChunk(
                request_id="req-repeated-final",
                channel_id="tui",
                payload={"event_type": "chat.final", "content": ""},
                is_complete=False,
            )

    async def fake_finalize(content: str, **_kwargs) -> str:
        finalized_inputs.append(content)
        return content

    monkeypatch.setattr(
        interface_module.JiuWenSwarm,
        "_ensure_adapter",
        lambda *_args, **_kwargs: FakeAdapter(),
    )
    monkeypatch.setattr(
        interface_module,
        "get_config",
        lambda: {"preferred_language": "zh", "memory": {"mode": "disabled"}},
    )
    monkeypatch.setattr(interface_module, "get_memory_mode", lambda _config: "disabled")
    monkeypatch.setattr(interface_module, "append_history_record", lambda **_kwargs: None)
    monkeypatch.setattr(interface_module, "finalize_assistant_response_if_a2ui", fake_finalize)

    swarm = interface_module.JiuWenSwarm()
    request = AgentRequest(
        request_id="req-repeated-final",
        channel_id="tui",
        session_id="sess-repeated-final",
        params={"query": "hello", "mode": "agent"},
        is_stream=True,
    )

    chunks = [chunk async for chunk in swarm.process_message_stream(request)]

    assert chunks[-1].is_complete is True
    assert finalized_inputs == ["authoritative answer"]


@pytest.mark.asyncio
async def test_closing_consumer_cancels_producer_blocked_on_full_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    producer_finished = asyncio.Event()

    class FakeAdapter:
        @staticmethod
        async def process_message_stream_impl(*_args, **_kwargs):
            seq = 0
            try:
                while True:
                    yield AgentResponseChunk(
                        request_id="req-disconnect",
                        channel_id="tui",
                        payload={"event_type": "chat.delta", "content": str(seq)},
                        is_complete=False,
                    )
                    seq += 1
            finally:
                producer_finished.set()

    monkeypatch.setattr(
        interface_module.JiuWenSwarm,
        "_ensure_adapter",
        lambda *_args, **_kwargs: FakeAdapter(),
    )
    monkeypatch.setattr(
        interface_module,
        "get_config",
        lambda: {"preferred_language": "zh", "memory": {"mode": "disabled"}},
    )
    monkeypatch.setattr(interface_module, "get_memory_mode", lambda _config: "disabled")
    monkeypatch.setattr(interface_module, "append_history_record", lambda **_kwargs: None)

    swarm = interface_module.JiuWenSwarm()
    swarm.STREAM_QUEUE_MAXSIZE = 1
    request = AgentRequest(
        request_id="req-disconnect",
        channel_id="tui",
        session_id="sess-disconnect",
        params={"query": "hello", "mode": "agent"},
        is_stream=True,
    )
    stream = swarm.process_message_stream(request)

    first = await anext(stream)
    assert first.payload["event_type"] == "chat.delta"
    await asyncio.wait_for(stream.aclose(), timeout=1.0)

    assert producer_finished.is_set()


@pytest.mark.asyncio
async def test_producer_close_cancellation_does_not_leave_consumer_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CloseCancellingStream:
        def __init__(self) -> None:
            self._yielded = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._yielded:
                raise StopAsyncIteration
            self._yielded = True
            return AgentResponseChunk(
                request_id="req-close-cancel",
                channel_id="tui",
                payload={"event_type": "chat.delta", "content": "partial"},
                is_complete=False,
            )

        async def aclose(self) -> None:
            raise asyncio.CancelledError

    class FakeAdapter:
        @staticmethod
        def process_message_stream_impl(*_args, **_kwargs):
            return CloseCancellingStream()

    monkeypatch.setattr(
        interface_module.JiuWenSwarm,
        "_ensure_adapter",
        lambda *_args, **_kwargs: FakeAdapter(),
    )
    monkeypatch.setattr(
        interface_module,
        "get_config",
        lambda: {"preferred_language": "zh", "memory": {"mode": "disabled"}},
    )
    monkeypatch.setattr(interface_module, "get_memory_mode", lambda _config: "disabled")
    monkeypatch.setattr(interface_module, "append_history_record", lambda **_kwargs: None)

    swarm = interface_module.JiuWenSwarm()
    request = AgentRequest(
        request_id="req-close-cancel",
        channel_id="tui",
        session_id="sess-close-cancel",
        params={"query": "hello", "mode": "agent"},
        is_stream=True,
    )

    async def consume() -> None:
        async for _ in swarm.process_message_stream(request):
            pass

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(consume(), timeout=1.0)



@pytest.mark.asyncio
async def test_first_resident_turns_share_the_sdk_memory_index(monkeypatch, tmp_path):
    from openjiuwen.core.memory.lite import manager as sdk_memory

    from jiuwenswarm.server.runtime.agent_adapter import interface_deep

    initialized = []
    started = asyncio.Event()
    finish = asyncio.Event()

    async def initialize(manager):
        initialized.append(manager)
        started.set()
        await finish.wait()

    monkeypatch.setattr(sdk_memory, "INDEX_CACHE", {})
    monkeypatch.setattr(sdk_memory.MemoryIndexManager, "initialize", initialize)
    monkeypatch.setattr(interface_deep, "get_config", lambda: {
        "embed": {
            "embed_api_key": "fixture",
            "embed_base_url": "http://127.0.0.1:1/v1",
            "embed_model": "fixture",
        },
    })
    monkeypatch.setattr(interface_deep, "is_proactive_memory", lambda *_args: True)
    adapter = object.__new__(interface_deep.JiuWenSwarmDeepAdapter)
    workspace = interface_deep.Workspace(root_path=str(tmp_path), language="en")
    ctx = SimpleNamespace(agent=SimpleNamespace(card=SimpleNamespace(id="jiuwenswarm")), inputs=None)
    rails = [adapter._build_memory_rail("agent") for _ in range(22)]
    for rail in rails:
        rail.set_workspace(workspace)

    tasks = [asyncio.create_task(rail.before_invoke(ctx)) for rail in rails]
    await asyncio.wait_for(started.wait(), timeout=2)
    finish.set()
    await asyncio.gather(*tasks)

    assert len(initialized) == 1
    assert all(rail._manager_initialized for rail in rails)
    await sdk_memory.aclose_memory_manager_cache()
