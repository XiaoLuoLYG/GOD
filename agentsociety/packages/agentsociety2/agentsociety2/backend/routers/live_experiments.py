"""Live experiment control API.

This router hosts in-process AgentSociety sessions so the frontend can run one
step at a time, ask questions, intervene, or switch into automatic execution.
Replay data is still written through the existing ReplayWriter and read through
the existing replay API.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import uuid4

import yaml
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from agentsociety2.env import CodeGenRouter
from agentsociety2.logger import get_logger
from agentsociety2.registry import scan_and_register_custom_modules
from agentsociety2.backend.services.replay_catalog import _quote_identifier
from agentsociety2.society.cli import ExperimentRunner
from agentsociety2.society.models import RunStep
from agentsociety2.society.society import AgentSociety
from agentsociety2.storage import ReplayWriter
from agentsociety2.storage.operator_commands import write_operator_command

logger = get_logger()

router = APIRouter(prefix="/live-experiments", tags=["live-experiments"])

LiveStatus = Literal[
    "initializing",
    "waiting",
    "running_step",
    "asking",
    "intervening",
    "auto",
    "stopped",
    "failed",
]

DEFAULT_INTERACTION_TIMEOUT_SECONDS = float(
    os.getenv("AGENTSOCIETY_LIVE_INTERACTION_TIMEOUT", "180")
)
DEFAULT_STEP_TIMEOUT_SECONDS = float(
    os.getenv("AGENTSOCIETY_LIVE_STEP_TIMEOUT", "180")
)


class LiveSessionRequest(BaseModel):
    tick: Optional[int] = Field(None, gt=0)


class RunStepRequest(BaseModel):
    tick: Optional[int] = Field(None, gt=0)


class AutoRequest(BaseModel):
    enabled: bool = True
    tick: Optional[int] = Field(None, gt=0)
    interval_ms: int = Field(0, ge=0)
    max_steps: Optional[int] = Field(None, gt=0)


AskTargetType = Literal["society", "agent", "agents", "all_agents"]


class AskTarget(BaseModel):
    type: AskTargetType = "society"
    agent_id: Optional[int] = Field(None, description="Required for type='agent'")
    agent_ids: Optional[list[int]] = Field(
        None,
        description="Required for type='agents'; ignored for all_agents/society",
    )


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    target: AskTarget = Field(default_factory=AskTarget)


def _default_intervene_target() -> AskTarget:
    return AskTarget(type="all_agents")


class InterveneRequest(BaseModel):
    instruction: str = Field(..., min_length=1)
    target: AskTarget = Field(default_factory=_default_intervene_target)


class CommandResponse(BaseModel):
    command_id: str
    type: str
    result: str
    artifact_name: Optional[str] = None
    status: LiveStatus
    step_count: int
    simulation_time: Optional[str] = None
    target: Optional[dict[str, Any]] = None


class LiveExperimentStatus(BaseModel):
    hypothesis_id: str
    experiment_id: str
    workspace_path: str
    status: LiveStatus
    step_count: int
    simulation_time: Optional[str] = None
    auto_running: bool = False
    default_tick: int
    current_command: Optional[str] = None
    error: Optional[str] = None


class SyncAgentsResponse(BaseModel):
    status: LiveExperimentStatus
    added_agent_ids: list[int]
    skipped_agent_ids: list[int]


def _get_experiment_path(
    workspace_path: Path,
    hypothesis_id: str,
    experiment_id: str,
) -> Path:
    return (
        workspace_path / f"hypothesis_{hypothesis_id}" / f"experiment_{experiment_id}"
    )


def _find_custom_root(run_dir: Path) -> Path | None:
    custom_root = run_dir.resolve()
    while custom_root.parent != custom_root:
        if (custom_root / "custom").is_dir():
            return custom_root
        custom_root = custom_root.parent
    return custom_root if (custom_root / "custom").is_dir() else None


def _event(event_type: str, **payload: Any) -> dict[str, Any]:
    return {
        "type": event_type,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }


def _parse_sqlite_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace(" ", "T", 1))
        except ValueError:
            return None


def _read_replay_tail(db_path: Path) -> tuple[int, datetime] | None:
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            datasets = conn.execute(
                """
                SELECT table_name, step_key, time_key, capabilities_json
                FROM replay_dataset_catalog
                WHERE step_key IS NOT NULL AND time_key IS NOT NULL
                """
            ).fetchall()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("Unable to inspect replay tail from %s: %s", db_path, exc)
        return None

    def priority(row: sqlite3.Row) -> int:
        capabilities = str(row["capabilities_json"] or "")
        if "agent_snapshot" in capabilities:
            return 0
        if "env_snapshot" in capabilities:
            return 1
        return 2

    for dataset in sorted(datasets, key=priority):
        table_name = str(dataset["table_name"])
        step_key = str(dataset["step_key"])
        time_key = str(dataset["time_key"])
        if not table_name or not step_key or not time_key:
            continue
        quoted_table = _quote_identifier(table_name)
        quoted_step_key = _quote_identifier(step_key)
        quoted_time_key = _quote_identifier(time_key)
        try:
            conn = sqlite3.connect(str(db_path))
            try:
                max_step_row = conn.execute(
                    f"SELECT MAX({quoted_step_key}) FROM {quoted_table}"
                ).fetchone()
                if max_step_row is None or max_step_row[0] is None:
                    continue
                latest_step = int(max_step_row[0])
                time_row = conn.execute(
                    f"SELECT MAX({quoted_time_key}) FROM {quoted_table} "
                    f"WHERE {quoted_step_key} = ?",
                    (latest_step,),
                ).fetchone()
            finally:
                conn.close()
        except Exception as exc:
            logger.debug("Unable to read replay dataset %s: %s", table_name, exc)
            continue
        latest_time = _parse_sqlite_datetime(time_row[0] if time_row else None)
        if latest_time is None:
            continue
        return latest_step, latest_time
    return None


class LiveExperimentSession:
    def __init__(
        self,
        *,
        workspace_path: Path,
        hypothesis_id: str,
        experiment_id: str,
        default_tick: Optional[int] = None,
    ) -> None:
        self.workspace_path = workspace_path.resolve()
        self.hypothesis_id = hypothesis_id
        self.experiment_id = experiment_id
        self.experiment_path = _get_experiment_path(
            self.workspace_path,
            hypothesis_id,
            experiment_id,
        )
        self.run_dir = self.experiment_path / "run"
        self.artifacts_dir = self.run_dir / "artifacts"
        self.pid_file = self.run_dir / "pid.json"
        self.runner = ExperimentRunner(self.run_dir)

        self.status: LiveStatus = "initializing"
        self.default_tick = default_tick
        self.current_command: Optional[str] = None
        self.error: Optional[str] = None
        self.society: Optional[AgentSociety] = None
        self.replay_writer: Optional[ReplayWriter] = None

        self._lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()
        self._subscribers: set[WebSocket] = set()
        self._auto_task: Optional[asyncio.Task[None]] = None
        self._pause_requested = False
        self._stopped = False
        self._interaction_timeout = DEFAULT_INTERACTION_TIMEOUT_SECONDS
        self._step_timeout = DEFAULT_STEP_TIMEOUT_SECONDS

    @property
    def auto_running(self) -> bool:
        return self._auto_task is not None and not self._auto_task.done()

    def to_status(self) -> LiveExperimentStatus:
        return LiveExperimentStatus(
            hypothesis_id=self.hypothesis_id,
            experiment_id=self.experiment_id,
            workspace_path=str(self.workspace_path),
            status=self.status,
            step_count=self.society.step_count if self.society else 0,
            simulation_time=(
                self.society.current_time.isoformat() if self.society else None
            ),
            auto_running=self.auto_running,
            default_tick=self.default_tick,
            current_command=self.current_command,
            error=self.error,
        )

    async def init(self) -> None:
        async with self._init_lock:
            if self.society is not None:
                if self.status == "initializing":
                    await self._restore_from_replay_tail()
                    self.status = "waiting"
                    self._write_pid("waiting")
                    await self.broadcast(
                        _event("session_ready", status=self.to_status().model_dump())
                    )
                return
            if not self.experiment_path.exists():
                raise HTTPException(status_code=404, detail="Experiment not found")

            self.runner._validate_environment()
            init_config_file = self.experiment_path / "init" / "init_config.json"
            steps_file = self.experiment_path / "init" / "steps.yaml"
            config = self.runner._load_config(init_config_file)
            steps_config = self.runner._load_steps(steps_file)

            if self.default_tick is None:
                for step in steps_config.steps:
                    if isinstance(step, RunStep):
                        self.default_tick = step.tick
                        break
            self.default_tick = self.default_tick or 1

            custom_root = _find_custom_root(self.run_dir)
            if custom_root is not None:
                logger.info("Scanning custom modules from %s", custom_root)
                scan_and_register_custom_modules(custom_root)

            env_module_types = [module.module_type for module in config.env_modules]
            env_kwargs = {
                module.module_type: module.kwargs for module in config.env_modules
            }
            env_modules = self.runner._create_env_modules(env_module_types, env_kwargs)

            self.replay_writer = ReplayWriter(self.run_dir / "sqlite.db")
            await self.replay_writer.init()
            env_router = CodeGenRouter(
                env_modules=env_modules,
                replay_writer=self.replay_writer,
                final_summary_enabled=config.codegen_router.final_summary_enabled,
            )
            env_router.run_dir = self.run_dir.resolve()

            agent_args = [
                {
                    "agent_id": agent.agent_id,
                    "agent_type": agent.agent_type,
                    "kwargs": agent.kwargs,
                }
                for agent in config.agents
            ]
            agents = self.runner._create_agents(agent_args)

            self.society = AgentSociety(
                agents=agents,
                env_router=env_router,
                start_t=datetime.fromisoformat(steps_config.start_t),
                run_dir=self.run_dir,
                enable_replay=True,
                replay_writer=self.replay_writer,
            )
            await self.society.init()
            await self._restore_from_replay_tail()
            self.status = "waiting"
            self._write_pid("waiting")
            await self.broadcast(
                _event("session_ready", status=self.to_status().model_dump())
            )

    async def _restore_from_replay_tail(self) -> None:
        if self.society is None:
            return
        replay_tail = _read_replay_tail(self.run_dir / "sqlite.db")
        if replay_tail is None:
            return

        latest_step, latest_time = replay_tail
        target_step_count = latest_step + 1
        if target_step_count <= self.society.step_count:
            return

        logger.info(
            "Restoring live session to replay tail: %s completed steps",
            target_step_count,
        )
        if await self._restore_env_modules_from_replay_tail(latest_step):
            tick = self.default_tick or 1
            self.society._step_count = target_step_count
            self.society._t = latest_time + timedelta(seconds=tick)
            self.society._env_router.sync_simulation_clock(self.society._t)
            logger.info(
                "Fast-restored live session from replay tail: step_count=%s current_time=%s",
                self.society.step_count,
                self.society.current_time.isoformat(),
            )
            return

        original_writer = self.replay_writer
        try:
            self.society._env_router.set_replay_writer(None)  # type: ignore[arg-type]
            await self.society.run(target_step_count - self.society.step_count, self.default_tick)
        finally:
            if original_writer is not None:
                self.society._env_router.set_replay_writer(original_writer)

    async def _restore_env_modules_from_replay_tail(self, latest_step: int) -> bool:
        if self.society is None:
            return False
        restored_any = False
        db_path = self.run_dir / "sqlite.db"
        for env_module in self.society._env_router.env_modules:
            load_replay_tail = getattr(env_module, "load_replay_tail", None)
            if not callable(load_replay_tail):
                continue
            result = load_replay_tail(db_path, latest_step)
            if asyncio.iscoroutine(result):
                result = await result
            logger.info("Restored env module from replay tail: %s", result)
            restored_any = True
        return restored_any

    def _write_pid(self, status: LiveStatus) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        pid_data: dict[str, Any] = {}
        if self.pid_file.exists():
            try:
                pid_data = json.loads(self.pid_file.read_text(encoding="utf-8"))
            except Exception:
                pid_data = {}

        pid_data.update(
            {
                "pid": os.getpid(),
                "mode": "live",
                "status": status,
                "experiment_id": self.experiment_id,
                "step_count": self.society.step_count if self.society else 0,
                "simulation_time": (
                    self.society.current_time.isoformat() if self.society else None
                ),
                "auto_running": self.auto_running,
                "start_time": pid_data.get(
                    "start_time", datetime.now(timezone.utc).isoformat()
                ),
            }
        )
        if status in ("stopped", "failed"):
            pid_data["end_time"] = datetime.now(timezone.utc).isoformat()
        self.pid_file.write_text(
            json.dumps(pid_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    async def add_subscriber(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._subscribers.add(websocket)
        await websocket.send_json(_event("status", status=self.to_status().model_dump()))

    def remove_subscriber(self, websocket: WebSocket) -> None:
        self._subscribers.discard(websocket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for websocket in list(self._subscribers):
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.remove_subscriber(websocket)

    def _ensure_ready(self) -> AgentSociety:
        if self.society is None:
            raise HTTPException(status_code=409, detail="Session is not ready")
        if self.status in ("stopped", "failed"):
            raise HTTPException(status_code=409, detail=f"Session is {self.status}")
        return self.society

    def _ensure_waiting(self) -> AgentSociety:
        society = self._ensure_ready()
        if self.status != "waiting":
            raise HTTPException(
                status_code=409,
                detail=f"Session is busy: {self.status}",
            )
        return society

    async def run_step(self, tick: Optional[int] = None) -> LiveExperimentStatus:
        async with self._lock:
            society = self._ensure_waiting()
            step_tick = tick or self.default_tick
            self.status = "running_step"
            self.current_command = "run-step"
            self._write_pid(self.status)
            await self.broadcast(
                _event(
                    "step_started",
                    step=society.step_count,
                    tick=step_tick,
                    status=self.to_status().model_dump(),
                )
            )
            try:
                await asyncio.wait_for(
                    society.step(step_tick),
                    timeout=self._step_timeout,
                )
            except asyncio.TimeoutError as exc:
                timeout_error = TimeoutError(
                    f"Live run-step timed out after {self._step_timeout:.0f}s. "
                    "The downstream agent service did not return a complete step."
                )
                await self._mark_failed(timeout_error)
                raise HTTPException(status_code=504, detail=str(timeout_error)) from exc
            except Exception as exc:
                await self._mark_failed(exc)
                raise
            self.status = "waiting"
            self.current_command = None
            self._write_pid(self.status)
            await self.broadcast(
                _event(
                    "step_completed",
                    step=society.step_count,
                    tick=step_tick,
                    replay_available=True,
                    status=self.to_status().model_dump(),
                )
            )
            return self.to_status()

    async def sync_agents_from_config(self) -> SyncAgentsResponse:
        async with self._lock:
            society = self._ensure_waiting()
            init_config_file = self.experiment_path / "init" / "init_config.json"
            config = self.runner._load_config(init_config_file)
            existing_ids = {agent.id for agent in society._agents}
            agent_args = [
                {
                    "agent_id": agent.agent_id,
                    "agent_type": agent.agent_type,
                    "kwargs": agent.kwargs,
                }
                for agent in config.agents
                if agent.agent_id not in existing_ids
            ]
            skipped_ids = [
                agent.agent_id for agent in config.agents if agent.agent_id in existing_ids
            ]
            if not agent_args:
                return SyncAgentsResponse(
                    status=self.to_status(),
                    added_agent_ids=[],
                    skipped_agent_ids=skipped_ids,
                )

            custom_root = _find_custom_root(self.run_dir)
            if custom_root is not None:
                scan_and_register_custom_modules(custom_root)
            new_agents = self.runner._create_agents(agent_args)

            initial_locations: dict[str, str] = {}
            for module in config.env_modules:
                module_locations = module.kwargs.get("initial_locations")
                if isinstance(module_locations, dict):
                    initial_locations.update(
                        {str(key): str(value) for key, value in module_locations.items()}
                    )

            for env_module in getattr(society._env_router, "env_modules", []):
                add_agent = getattr(env_module, "add_agent", None)
                if not callable(add_agent):
                    continue
                for agent in new_agents:
                    await add_agent(
                        agent_id=agent.id,
                        name=agent.name,
                        location=initial_locations.get(str(agent.id), "Town square"),
                    )

            await society.add_agents(new_agents)
            self._write_pid(self.status)
            added_ids = [agent.id for agent in new_agents]
            await self.broadcast(
                _event(
                    "agents_synced",
                    added_agent_ids=added_ids,
                    status=self.to_status().model_dump(),
                )
            )
            return SyncAgentsResponse(
                status=self.to_status(),
                added_agent_ids=added_ids,
                skipped_agent_ids=skipped_ids,
            )

    async def ask(self, request: AskRequest) -> CommandResponse:
        return await self._run_interaction(
            command_type="ask",
            busy_status="asking",
            prompt=request.question,
            runner=lambda society: self._ask_with_target(
                society,
                request.question,
                request.target,
            ),
            metadata={"target": request.target.model_dump(exclude_none=True)},
        )

    async def intervene(self, request: InterveneRequest) -> CommandResponse:
        return await self._run_interaction(
            command_type="intervene",
            busy_status="intervening",
            prompt=request.instruction,
            runner=lambda society: self._intervene_with_target(
                society,
                request.instruction,
                request.target,
            ),
            metadata={"target": request.target.model_dump(exclude_none=True)},
        )

    def _select_agents(
        self,
        society: AgentSociety,
        target: AskTarget,
    ) -> list[Any]:
        agents = list(getattr(society, "_agents", []))
        by_id = {int(agent.id): agent for agent in agents}
        if target.type == "all_agents":
            return agents
        if target.type == "agent":
            if target.agent_id is None:
                raise HTTPException(
                    status_code=400,
                    detail="agent_id is required when target.type='agent'",
                )
            agent = by_id.get(int(target.agent_id))
            if agent is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Unknown agent_id: {target.agent_id}",
                )
            return [agent]
        if target.type == "agents":
            if not target.agent_ids:
                raise HTTPException(
                    status_code=400,
                    detail="agent_ids is required when target.type='agents'",
                )
            missing = [agent_id for agent_id in target.agent_ids if int(agent_id) not in by_id]
            if missing:
                raise HTTPException(
                    status_code=404,
                    detail=f"Unknown agent_ids: {missing}",
                )
            return [by_id[int(agent_id)] for agent_id in target.agent_ids]
        return []

    async def _ask_with_target(
        self,
        society: AgentSociety,
        question: str,
        target: AskTarget,
    ) -> str:
        if target.type == "society":
            return await society.ask(question)

        agents = self._select_agents(society, target)
        if not agents:
            raise HTTPException(status_code=404, detail="No agents matched ask target")

        async def ask_one(agent: Any) -> Any:
            answer_external_question = getattr(agent, "answer_external_question", None)
            if callable(answer_external_question):
                return await answer_external_question(
                    question,
                    t=society.current_time,
                    response_type="text",
                )
            return await agent.ask(question, readonly=True)

        answers = await asyncio.gather(
            *[ask_one(agent) for agent in agents],
            return_exceptions=True,
        )
        lines = [
            f"目标: {self._describe_ask_target(target, agents)}",
            f"仿真时间: {society.current_time.isoformat()}",
            f"已执行 step: {society.step_count}",
            "",
        ]
        for agent, answer in zip(agents, answers):
            lines.append(f"### {agent.name} (agent_id={agent.id})")
            if isinstance(answer, Exception):
                lines.append(f"调用失败: {answer}")
            else:
                lines.append(str(answer).strip() or "无回复")
            lines.append("")
        return "\n".join(lines).rstrip()

    def _describe_ask_target(self, target: AskTarget, agents: list[Any]) -> str:
        if target.type == "all_agents":
            return f"所有居民（{len(agents)} 个）"
        if target.type == "agent":
            agent = agents[0]
            return f"{agent.name} (agent_id={agent.id})"
        if target.type == "agents":
            return ", ".join(f"{agent.name} (agent_id={agent.id})" for agent in agents)
        return "仿真系统"

    async def _intervene_with_target(
        self,
        society: AgentSociety,
        instruction: str,
        target: AskTarget,
    ) -> str:
        if target.type == "society":
            agents = self._select_agents(society, AskTarget(type="all_agents"))
            moved = await self._apply_targeted_movement_intervention(
                society,
                instruction,
                agents,
            )
            if moved:
                return moved
            applied = await self._apply_environment_intervention(society, instruction)
            if applied:
                return applied
            return await society.intervene(instruction)

        agents = self._select_agents(society, target)
        if not agents:
            raise HTTPException(
                status_code=404,
                detail="No agents matched intervene target",
            )

        moved = await self._apply_targeted_movement_intervention(
            society,
            instruction,
            agents,
        )
        if moved:
            return moved

        results: list[str] = []
        for agent in agents:
            queue_fn = getattr(agent, "queue_intervention", None)
            if callable(queue_fn):
                queued = queue_fn(instruction)
                if asyncio.iscoroutine(queued):
                    queued = await queued
                results.append(f"{agent.name} (agent_id={agent.id}): {queued}")
            else:
                answer = await agent.ask(instruction, readonly=False)
                results.append(f"{agent.name} (agent_id={agent.id}): {answer}")

        return (
            f"已接收干预，并投递给 {self._describe_ask_target(target, agents)}。\n"
            "手动模式下不会自动执行下一步；请点击 Run Step 或开启 Auto 后，"
            "该干预会进入后续 step 并写入 replay。\n\n"
            + "\n".join(results)
        )

    async def _apply_targeted_movement_intervention(
        self,
        society: AgentSociety,
        instruction: str,
        agents: list[Any],
    ) -> str:
        location = self._extract_movement_location(instruction)
        if not location or not agents:
            return ""

        env_router = getattr(society, "_env_router", None)
        env_modules = getattr(env_router, "env_modules", None)
        if not isinstance(env_modules, list):
            return ""

        move_env = next(
            (
                env_module
                for env_module in env_modules
                if callable(getattr(env_module, "move_agent", None))
            ),
            None,
        )
        if move_env is None:
            return ""

        lines = [
            f"已识别为集合/移动干预，直接调用环境寻路到：{location}",
            f"目标: {self._describe_ask_target(AskTarget(type='all_agents') if len(agents) != 1 else AskTarget(type='agent', agent_id=int(agents[0].id)), agents)}",
            "下一次 Run Step/Auto 会推进路径并写入 replay；若 tick 足够大，会在同一个 step 内到达。",
            "",
        ]
        ok_count = 0
        for agent in agents:
            move_agent = getattr(move_env, "move_agent")
            result = move_agent(agent_id=int(agent.id), location=location)
            if asyncio.iscoroutine(result):
                result = await result
            if isinstance(result, dict) and result.get("ok") is True:
                ok_count += 1
                lines.append(
                    f"{agent.name} (agent_id={agent.id}): moving -> "
                    f"{result.get('location') or result.get('location_id')}, "
                    f"path_length={result.get('path_length', 'unknown')}"
                )
            else:
                lines.append(
                    f"{agent.name} (agent_id={agent.id}): move failed: {result}"
                )

        if ok_count == 0:
            lines.insert(
                1,
                "没有 agent 成功开始移动；请检查地点名称是否是地图 manifest 中的 location/alias。",
            )
        return "\n".join(lines)

    def _extract_movement_location(self, instruction: str) -> str:
        text = " ".join(str(instruction or "").split())
        if not text:
            return ""
        movement_keywords = (
            "移动",
            "前往",
            "去到",
            "去",
            "到",
            "集合",
            "集结",
            "集中",
            "待命",
            "move",
            "gather",
            "meet",
        )
        if not any(keyword in text.casefold() for keyword in movement_keywords):
            return ""

        patterns = [
            r"(?:集中到|集合到|集结到|移动到|前往|去到|去|到)\s*(?P<location>[^，。,；;！!\n]+)",
            r"(?:在|于)\s*(?P<location>[^，。,；;！!\n]+?)\s*(?:集合|集结|集中|待命)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            location = self._clean_movement_location(match.group("location"))
            if location:
                return location
        return ""

    @staticmethod
    def _clean_movement_location(location: str) -> str:
        cleaned = str(location or "").strip(" ：:，。,；;！!。")
        for marker in ("集合", "集结", "集中", "待命", "准备", "并", "然后"):
            index = cleaned.find(marker)
            if index > 0:
                cleaned = cleaned[:index]
        return cleaned.strip(" ：:，。,；;！!。")

    async def _apply_environment_intervention(
        self,
        society: AgentSociety,
        instruction: str,
    ) -> str:
        env_router = getattr(society, "_env_router", None)
        env_modules = getattr(env_router, "env_modules", None)
        if not isinstance(env_modules, list):
            return ""

        for env_module in env_modules:
            publish_event = getattr(env_module, "publish_event", None)
            if not callable(publish_event):
                continue

            severity = (
                "emergency"
                if self._looks_like_emergency(instruction)
                else "info"
            )
            result = publish_event(
                event=instruction,
                severity=severity,
                broadcast=True,
                group_id=1,
            )
            if asyncio.iscoroutine(result):
                result = await result
            return (
                "已将系统干预写入环境公共事件；"
                "该事件会出现在后续 observation/latest_event 中，并已广播到小镇群组。\n\n"
                f"Environment result: {result}"
            )

        return ""

    def _looks_like_emergency(self, instruction: str) -> bool:
        lowered = instruction.lower()
        keywords = (
            "火山",
            "爆发",
            "地震",
            "火灾",
            "洪水",
            "海啸",
            "爆炸",
            "撤离",
            "疏散",
            "紧急",
            "危险",
            "灾",
            "evacuate",
            "emergency",
            "volcano",
            "earthquake",
            "fire",
            "flood",
        )
        return any(keyword in lowered for keyword in keywords)

    async def _run_interaction(
        self,
        *,
        command_type: Literal["ask", "intervene"],
        busy_status: Literal["asking", "intervening"],
        prompt: str,
        runner: Any,
        metadata: Optional[dict[str, Any]] = None,
    ) -> CommandResponse:
        async with self._lock:
            society = self._ensure_waiting()
            command_id = uuid4().hex
            self.status = busy_status
            self.current_command = command_type
            self.error = None
            self._write_pid(self.status)
            await self.broadcast(
                _event(
                    "command_started",
                    command_id=command_id,
                    type=command_type,
                    status=self.to_status().model_dump(),
                )
            )
            try:
                result = await asyncio.wait_for(
                    runner(society),
                    timeout=self._interaction_timeout,
                )
                artifact_name = self._write_artifact(
                    command_type,
                    prompt,
                    result,
                    metadata=metadata,
                )
                if self.replay_writer is not None:
                    await write_operator_command(
                        self.replay_writer,
                        command_id=command_id,
                        command_type=command_type,
                        step=society.step_count,
                        simulation_time=society.current_time,
                        prompt=prompt,
                        target=metadata.get("target") if metadata else None,
                        result=result,
                        artifact_name=artifact_name,
                        status="completed",
                    )
            except asyncio.CancelledError:
                await self._mark_interaction_failed(
                    command_id=command_id,
                    command_type=command_type,
                    message="Live command was cancelled before completion.",
                )
                raise
            except asyncio.TimeoutError as exc:
                message = (
                    f"Live {command_type} timed out after "
                    f"{self._interaction_timeout:.0f} seconds."
                )
                await self._mark_interaction_failed(
                    command_id=command_id,
                    command_type=command_type,
                    message=message,
                )
                raise HTTPException(status_code=504, detail=message) from exc
            except HTTPException as exc:
                await self._mark_interaction_failed(
                    command_id=command_id,
                    command_type=command_type,
                    message=str(exc.detail),
                )
                raise
            except Exception as exc:
                message = str(exc)
                await self._mark_interaction_failed(
                    command_id=command_id,
                    command_type=command_type,
                    message=message,
                )
                raise HTTPException(status_code=500, detail=message) from exc

            self.status = "waiting"
            self.current_command = None
            self.error = None
            self._write_pid(self.status)
            response = CommandResponse(
                command_id=command_id,
                type=command_type,
                result=result,
                artifact_name=artifact_name,
                status=self.status,
                step_count=society.step_count,
                simulation_time=society.current_time.isoformat(),
                target=metadata.get("target") if metadata else None,
            )
            await self.broadcast(
                _event(
                    "command_completed",
                    command=response.model_dump(),
                    status=self.to_status().model_dump(),
                )
            )
            await self.broadcast(
                _event(
                    "artifact_created",
                    type=command_type,
                    name=artifact_name,
                    content_preview=result[:300],
                )
            )
            return response

    async def _mark_interaction_failed(
        self,
        *,
        command_id: str,
        command_type: Literal["ask", "intervene"],
        message: str,
    ) -> None:
        self.error = message
        self.status = "waiting"
        self.current_command = None
        self._write_pid(self.status)
        status = self.to_status().model_dump()
        await self.broadcast(
            _event(
                "command_failed",
                command_id=command_id,
                type=command_type,
                message=message,
                status=status,
            )
        )
        await self.broadcast(_event("error", message=message, status=status))

    def _write_artifact(
        self,
        command_type: str,
        prompt: str,
        result: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        if self.society is None:
            raise RuntimeError("Session is not ready")
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        timestamp = self.society.current_time.strftime("%Y%m%d_%H%M%S")
        artifact_stem = f"{command_type}_live_step_{self.society.step_count}_{timestamp}"
        artifact_name = f"{artifact_stem}.md"
        artifact_file = self.artifacts_dir / artifact_name
        suffix = 2
        while artifact_file.exists():
            artifact_name = f"{artifact_stem}_{suffix}.md"
            artifact_file = self.artifacts_dir / artifact_name
            suffix += 1
        frontmatter_key = "question" if command_type == "ask" else "instruction"
        frontmatter = {frontmatter_key: prompt, **(metadata or {})}
        with artifact_file.open("w", encoding="utf-8") as f:
            f.write("---\n")
            f.write(yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False))
            f.write("---\n\n")
            f.write(f"{result}\n")
        return artifact_name

    async def set_auto(self, request: AutoRequest) -> LiveExperimentStatus:
        if not request.enabled:
            await self.pause()
            return self.to_status()
        self._ensure_waiting()
        self._pause_requested = False
        self.status = "auto"
        self.current_command = "auto"
        self._write_pid(self.status)
        self._auto_task = asyncio.create_task(self._auto_loop(request))
        await self.broadcast(
            _event("auto_started", status=self.to_status().model_dump())
        )
        return self.to_status()

    async def _auto_loop(self, request: AutoRequest) -> None:
        steps_run = 0
        while not self._pause_requested and not self._stopped:
            if request.max_steps is not None and steps_run >= request.max_steps:
                break
            async with self._lock:
                society = self._ensure_ready()
                if self.status not in ("waiting", "auto"):
                    break
                step_tick = request.tick or self.default_tick
                self.status = "auto"
                self.current_command = "auto"
                self._write_pid(self.status)
                await self.broadcast(
                    _event(
                        "step_started",
                        step=society.step_count,
                        tick=step_tick,
                        status=self.to_status().model_dump(),
                    )
                )
                try:
                    await asyncio.wait_for(
                        society.step(step_tick),
                        timeout=self._step_timeout,
                    )
                except asyncio.TimeoutError:
                    timeout_error = TimeoutError(
                        f"Live auto step timed out after {self._step_timeout:.0f}s. "
                        "The downstream agent service did not return a complete step."
                    )
                    await self._mark_failed(timeout_error)
                    return
                except Exception as exc:
                    await self._mark_failed(exc)
                    return
                steps_run += 1
                self._write_pid(self.status)
                await self.broadcast(
                    _event(
                        "step_completed",
                        step=society.step_count,
                        tick=step_tick,
                        replay_available=True,
                        status=self.to_status().model_dump(),
                    )
                )
            if request.interval_ms > 0:
                await asyncio.sleep(request.interval_ms / 1000)

        async with self._lock:
            if self.status not in ("failed", "stopped"):
                self.status = "waiting"
                self.current_command = None
                self._write_pid(self.status)
                await self.broadcast(
                    _event("auto_paused", status=self.to_status().model_dump())
                )
        self._pause_requested = False

    async def pause(self) -> None:
        self._pause_requested = True
        if self._auto_task is None or self._auto_task.done():
            if self.status == "auto":
                self.status = "waiting"
                self.current_command = None
                self._write_pid(self.status)
            await self.broadcast(
                _event("auto_paused", status=self.to_status().model_dump())
            )

    async def stop(self) -> LiveExperimentStatus:
        self._pause_requested = True
        self._stopped = True
        async with self._lock:
            if self.status != "stopped":
                self.status = "stopped"
                self.current_command = None
                self._write_pid(self.status)
            if self.society is not None:
                await self.society.close()
                self.society = None
                self.replay_writer = None
            await self.broadcast(_event("status", status=self.to_status().model_dump()))
            return self.to_status()

    async def _mark_failed(self, exc: Exception) -> None:
        self.error = str(exc)
        self.status = "failed"
        self.current_command = None
        self._write_pid(self.status)
        await self.broadcast(
            _event("error", message=str(exc), status=self.to_status().model_dump())
        )


class LiveExperimentManager:
    def __init__(self) -> None:
        self._sessions: dict[tuple[str, str, str], LiveExperimentSession] = {}
        self._lock = asyncio.Lock()

    def _key(
        self,
        workspace_path: str,
        hypothesis_id: str,
        experiment_id: str,
    ) -> tuple[str, str, str]:
        return (str(Path(workspace_path).resolve()), hypothesis_id, experiment_id)

    async def get_or_create(
        self,
        *,
        workspace_path: str,
        hypothesis_id: str,
        experiment_id: str,
        default_tick: Optional[int] = None,
    ) -> LiveExperimentSession:
        key = self._key(workspace_path, hypothesis_id, experiment_id)
        async with self._lock:
            session = self._sessions.get(key)
            if session is None or session.status in ("stopped", "failed"):
                session = LiveExperimentSession(
                    workspace_path=Path(workspace_path),
                    hypothesis_id=hypothesis_id,
                    experiment_id=experiment_id,
                    default_tick=default_tick,
                )
                self._sessions[key] = session
        await session.init()
        return session

    def get(
        self,
        *,
        workspace_path: str,
        hypothesis_id: str,
        experiment_id: str,
    ) -> LiveExperimentSession:
        key = self._key(workspace_path, hypothesis_id, experiment_id)
        session = self._sessions.get(key)
        if session is None:
            raise HTTPException(status_code=404, detail="Live session not found")
        return session


manager = LiveExperimentManager()


@router.post(
    "/{hypothesis_id}/{experiment_id}/sessions",
    response_model=LiveExperimentStatus,
)
async def create_live_session(
    hypothesis_id: str,
    experiment_id: str,
    request: LiveSessionRequest | None = None,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> LiveExperimentStatus:
    session = await manager.get_or_create(
        workspace_path=workspace_path,
        hypothesis_id=hypothesis_id,
        experiment_id=experiment_id,
        default_tick=request.tick if request else None,
    )
    return session.to_status()


@router.get("/{hypothesis_id}/{experiment_id}/status", response_model=LiveExperimentStatus)
async def get_live_status(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> LiveExperimentStatus:
    return manager.get(
        workspace_path=workspace_path,
        hypothesis_id=hypothesis_id,
        experiment_id=experiment_id,
    ).to_status()


@router.post(
    "/{hypothesis_id}/{experiment_id}/run-step",
    response_model=LiveExperimentStatus,
)
async def run_live_step(
    hypothesis_id: str,
    experiment_id: str,
    request: RunStepRequest | None = None,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> LiveExperimentStatus:
    session = manager.get(
        workspace_path=workspace_path,
        hypothesis_id=hypothesis_id,
        experiment_id=experiment_id,
    )
    return await session.run_step(request.tick if request else None)


@router.post(
    "/{hypothesis_id}/{experiment_id}/sync-agents",
    response_model=SyncAgentsResponse,
)
async def sync_live_agents(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> SyncAgentsResponse:
    session = manager.get(
        workspace_path=workspace_path,
        hypothesis_id=hypothesis_id,
        experiment_id=experiment_id,
    )
    return await session.sync_agents_from_config()


@router.post("/{hypothesis_id}/{experiment_id}/ask", response_model=CommandResponse)
async def live_ask(
    hypothesis_id: str,
    experiment_id: str,
    request: AskRequest,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> CommandResponse:
    session = manager.get(
        workspace_path=workspace_path,
        hypothesis_id=hypothesis_id,
        experiment_id=experiment_id,
    )
    return await session.ask(request)


@router.post(
    "/{hypothesis_id}/{experiment_id}/intervene",
    response_model=CommandResponse,
)
async def live_intervene(
    hypothesis_id: str,
    experiment_id: str,
    request: InterveneRequest,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> CommandResponse:
    session = manager.get(
        workspace_path=workspace_path,
        hypothesis_id=hypothesis_id,
        experiment_id=experiment_id,
    )
    return await session.intervene(request)


@router.post("/{hypothesis_id}/{experiment_id}/auto", response_model=LiveExperimentStatus)
async def live_auto(
    hypothesis_id: str,
    experiment_id: str,
    request: AutoRequest,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> LiveExperimentStatus:
    session = manager.get(
        workspace_path=workspace_path,
        hypothesis_id=hypothesis_id,
        experiment_id=experiment_id,
    )
    return await session.set_auto(request)


@router.post("/{hypothesis_id}/{experiment_id}/pause", response_model=LiveExperimentStatus)
async def live_pause(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> LiveExperimentStatus:
    session = manager.get(
        workspace_path=workspace_path,
        hypothesis_id=hypothesis_id,
        experiment_id=experiment_id,
    )
    await session.pause()
    return session.to_status()


@router.post("/{hypothesis_id}/{experiment_id}/stop", response_model=LiveExperimentStatus)
async def live_stop(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> LiveExperimentStatus:
    session = manager.get(
        workspace_path=workspace_path,
        hypothesis_id=hypothesis_id,
        experiment_id=experiment_id,
    )
    return await session.stop()


@router.websocket("/{hypothesis_id}/{experiment_id}/ws")
async def live_ws(
    websocket: WebSocket,
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> None:
    try:
        session = manager.get(
            workspace_path=workspace_path,
            hypothesis_id=hypothesis_id,
            experiment_id=experiment_id,
        )
    except HTTPException:
        await websocket.close(code=4404)
        return

    await session.add_subscriber(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        session.remove_subscriber(websocket)
