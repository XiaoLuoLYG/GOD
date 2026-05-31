from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from agentsociety2.storage import ReplayWriter
from agentsociety2.storage.operator_commands import write_operator_command
from agentsociety2.storage.replay_metadata import OPERATOR_COMMAND_DATASET_ID


def test_operator_command_dataset_registration_and_write(tmp_path: Path) -> None:
    asyncio.run(_operator_command_dataset_registration_and_write(tmp_path))


async def _operator_command_dataset_registration_and_write(tmp_path: Path) -> None:
    writer = ReplayWriter(tmp_path / "sqlite.db")
    await writer.init()
    await write_operator_command(
        writer,
        command_id="cmd-1",
        command_type="ask",
        step=3,
        simulation_time=datetime(2026, 5, 31, 9, 30, tzinfo=timezone.utc),
        prompt="Where are you?",
        target={"type": "agent", "agent_id": 1},
        result="At the park.",
        artifact_name="ask_live_step_3_20260531_093000.md",
        status="completed",
        created_at=datetime(2026, 5, 31, 1, 30, tzinfo=timezone.utc),
    )
    await writer.close()

    conn = sqlite3.connect(tmp_path / "sqlite.db")
    conn.row_factory = sqlite3.Row
    try:
        dataset = conn.execute(
            "SELECT dataset_id, table_name, kind, capabilities_json "
            "FROM replay_dataset_catalog WHERE dataset_id = ?",
            (OPERATOR_COMMAND_DATASET_ID,),
        ).fetchone()
        row = conn.execute("SELECT * FROM core_operator_command").fetchone()
    finally:
        conn.close()

    assert dataset["dataset_id"] == OPERATOR_COMMAND_DATASET_ID
    assert dataset["table_name"] == "core_operator_command"
    assert dataset["kind"] == "event_stream"
    assert "operator_command" in json.loads(dataset["capabilities_json"])
    assert row["command_id"] == "cmd-1"
    assert row["type"] == "ask"
    assert row["step"] == 3
    assert json.loads(row["target_json"]) == {"type": "agent", "agent_id": 1}
    assert row["result"] == "At the park."
