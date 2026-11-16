import asyncio

import pytest

from jiuwenswarm.agents.harness.common.memory.manager import MemoryIndexManager


@pytest.mark.asyncio
async def test_concurrent_requests_initialize_one_memory_manager(monkeypatch, tmp_path):
    initialized = []
    started = asyncio.Event()
    finish = asyncio.Event()

    async def initialize(manager):
        initialized.append(manager)
        started.set()
        await finish.wait()

    monkeypatch.setattr(MemoryIndexManager, "_initialize", initialize)
    tasks = [
        asyncio.create_task(MemoryIndexManager.get("jiuwenswarm", str(tmp_path)))
        for _ in range(22)
    ]
    await started.wait()
    finish.set()
    managers = await asyncio.gather(*tasks)

    assert len(initialized) == 1
    assert all(manager is initialized[0] for manager in managers)
    await initialized[0].close()
