"""Run one persistent native Codex conversation per GOD resident and run."""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any
from uuid import UUID

from agentsociety2.agent.brains.base import (
    AgentBrain, AskRequest, BrainContext, SkillChoiceRequest, SkillDecision, decision_from_text,
)
from agentsociety2.agent.brains.command import run_agent_command

_MAC_APP_CLI = Path("/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex")
_DISABLED_FEATURES = (
    "shell_tool", "unified_exec", "hooks", "plugins", "apps", "multi_agent", "multi_agent_v2",
    "memories", "computer_use", "image_generation", "view_image",
)


def find_codex() -> str | None:
    if _MAC_APP_CLI.is_file():
        return str(_MAC_APP_CLI)
    return shutil.which("codex")


async def codex_login_status() -> str:
    executable = find_codex()
    if not executable:
        return "missing"
    try:
        with TemporaryDirectory(prefix="god-codex-check-") as cwd:
            code, help_output = await run_agent_command(
                [executable, "exec", "--help"], "", cwd=cwd, timeout=5,
            )
            if code or b"--ignore-user-config" not in help_output or b"--json" not in help_output:
                return "unavailable"
            code, output = await run_agent_command(
                [executable, "-c", 'model_reasoning_effort="low"', "login", "status"], "", cwd=cwd, timeout=5,
            )
    except (OSError, TimeoutError):
        return "unavailable"
    if code == 0:
        return "ready"
    return "logged_out" if b"not logged in" in output.lower() else "unavailable"


class CodexBrain(AgentBrain):
    name = "codex"
    capabilities = frozenset({"choose_skill", "ask", "session"})

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._state_path: Path | None = None
        self._thread_id: str | None = None
        self._persist_session = True
        self._lock = asyncio.Lock()

    async def start(self, ctx: BrainContext) -> None:
        self._state_path = None
        self._thread_id = None
        self._persist_session = ctx.enable_memory
        if not self._persist_session or ctx.work_dir is None:
            return
        work_dir = Path(ctx.work_dir).resolve()
        path = (work_dir / ".runtime" / "codex-session.json").resolve()
        if not path.is_relative_to(work_dir):
            raise ValueError("Codex session path escapes the resident workspace")
        self._state_path = path
        if path.is_file():
            state = json.loads(path.read_text(encoding="utf-8"))
            self._thread_id = str(UUID(state["thread_id"]))

    async def choose_skill(self, req: SkillChoiceRequest) -> SkillDecision:
        started = time.perf_counter()
        decision = decision_from_text(req.prompt, await self._turn(req.prompt))
        decision.latency_ms = (time.perf_counter() - started) * 1000
        return decision

    async def ask(self, req: AskRequest) -> str:
        return await self._turn(req.prompt)

    async def _turn(self, prompt: str) -> str:
        async with self._lock:
            executable = find_codex()
            if not executable:
                raise RuntimeError("Install Codex CLI and run codex login before starting a Codex resident")
            command = [
                executable, "-a", "never", "-s", "read-only", "-c", 'web_search="disabled"',
                "-c", "mcp_servers={}", "-c", "project_doc_max_bytes=0", "-c", 'model_reasoning_effort="low"',
            ]
            for feature in _DISABLED_FEATURES:
                command.extend(("-c", f"features.{feature}=false"))
            command.append("exec")
            if self._thread_id:
                command.append("resume")
            command.extend(("--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "--json"))
            if not self._persist_session:
                command.append("--ephemeral")
            if self._thread_id:
                command.append(self._thread_id)
            command.append("-")
            with TemporaryDirectory(prefix="god-codex-") as cwd:
                code, output = await run_agent_command(command, prompt, cwd=cwd, timeout=90)
            return self._response(code, output)

    def _response(self, code: int, output: bytes) -> str:
        if code != 0:
            raise RuntimeError(f"Codex turn failed (exit {code}). Check the Codex CLI version and login on this machine.")
        thread_id = None
        completed = False
        answer = ""
        for line in output.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            match event.get("type"):
                case "thread.started":
                    thread_id = str(UUID(event["thread_id"]))
                case "item.completed":
                    item = event.get("item", {})
                    if item.get("type") == "agent_message":
                        answer = str(item.get("text") or "").strip()
                    elif item.get("type") in {"command_execution", "file_change", "mcp_tool_call", "web_search"}:
                        raise RuntimeError("Codex attempted to use tools outside the simulation")
                case "turn.completed":
                    completed = True
        if not completed or not answer or not thread_id:
            raise RuntimeError("Codex did not return a completed conversation turn")
        if self._thread_id and self._thread_id != thread_id:
            raise RuntimeError("Codex returned an unexpected conversation ID")
        if self._persist_session and not self._thread_id:
            self._save_thread(thread_id)
        return answer

    def _save_thread(self, thread_id: str) -> None:
        if self._state_path is not None:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self._state_path.parent, delete=False) as handle:
                path = Path(handle.name)
                json.dump({"thread_id": thread_id}, handle)
            try:
                path.replace(self._state_path)
            finally:
                path.unlink(missing_ok=True)
        self._thread_id = thread_id
