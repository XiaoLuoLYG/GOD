"""Replay metadata definitions for dataset-driven export and analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


ReplayDatasetKind = Literal[
    "entity_snapshot",
    "entity_static",
    "env_snapshot",
    "event_stream",
    "metric_series",
]

DATASET_CATALOG_TABLE = "replay_dataset_catalog"
COLUMN_CATALOG_TABLE = "replay_column_catalog"
AGENT_PROFILE_DATASET_ID = "core.agent_profile"
AGENT_PROFILE_TABLE_NAME = "core_agent_profile"
AGENT_PROFILE_DATASET_CAPABILITY = "agent_profile"
OPERATOR_COMMAND_DATASET_ID = "core.operator_command"
OPERATOR_COMMAND_TABLE_NAME = "core_operator_command"
OPERATOR_COMMAND_DATASET_CAPABILITY = "operator_command"


@dataclass
class ReplayDatasetSpec:
    """Semantic metadata for a replay dataset backed by a SQLite table."""

    dataset_id: str
    table_name: str
    module_name: str
    kind: ReplayDatasetKind
    title: str = ""
    description: str = ""
    entity_key: Optional[str] = None
    step_key: Optional[str] = None
    time_key: Optional[str] = None
    default_order: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    version: int = 1
