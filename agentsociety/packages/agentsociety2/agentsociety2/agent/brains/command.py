"""Run an operator-configured agent adapter with a text stdin/stdout contract."""

from __future__ import annotations

import asyncio
import json
import math
import os
import signal
import time
from contextlib import suppress
from tempfile import TemporaryDirectory

from agentsociety2.agent.brains.base import AgentBrain, AskRequest, SkillChoiceRequest, SkillDecision, decision_from_text

_ENVIRONMENT_KEYS = {
    "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR", "PATHEXT", "COMSPEC",
    "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TEMP", "TMP",
    "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "CODEX_HOME", "CLAUDE_CONFIG_DIR",
}


class CommandBrain(AgentBrain):
    name = "command"
    capabilities = frozenset({"choose_skill", "ask"})

    async def choose_skill(self, req: SkillChoiceRequest) -> SkillDecision:
        started = time.perf_counter()
        raw = await self._run(req.prompt)
        decision = decision_from_text(req.prompt, raw)
        decision.latency_ms = (time.perf_counter() - started) * 1000
        return decision

    async def ask(self, req: AskRequest) -> str:
        return await self._run(req.prompt)

    async def _run(self, prompt: str) -> str:
        profile = self.config.get("profile", "default")
        try:
            commands = json.loads(os.getenv("GOD_AGENT_COMMANDS", "{}"))
            command = commands.get(profile) if isinstance(commands, dict) and isinstance(profile, str) else None
        except ValueError:
            command = None
        if not isinstance(command, list) or not command or not all(isinstance(arg, str) and arg for arg in command):
            raise RuntimeError("configure a command profile in local GOD_AGENT_COMMANDS")

        try:
            timeout = float(self.config.get("timeout_s", 60))
        except (TypeError, ValueError):
            timeout = 60
        timeout = min(180, max(1, timeout)) if math.isfinite(timeout) else 60
        with TemporaryDirectory(prefix="god-agent-") as workspace:
            returncode, output = await run_agent_command(command, prompt, cwd=workspace, timeout=timeout)
        if returncode:
            raise RuntimeError(f"agent command exited with status {returncode}")

        answer = output.decode("utf-8").strip()
        if not answer:
            raise RuntimeError("agent command returned empty output")
        return answer


async def run_agent_command(
    command: list[str], prompt: str, *, cwd: str, timeout: float,
) -> tuple[int, bytes]:
    env = {key: os.environ[key] for key in _ENVIRONMENT_KEYS if key in os.environ}
    own_group = os.name == "posix"
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        env=env,
        stdin=asyncio.subprocess.PIPE if prompt else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        start_new_session=own_group,
    )
    try:
        output, _ = await asyncio.wait_for(
            process.communicate(prompt.encode("utf-8") if prompt else None), timeout
        )
    except (asyncio.TimeoutError, asyncio.CancelledError):
        with suppress(ProcessLookupError):
            if own_group:
                os.killpg(process.pid, signal.SIGKILL)
            elif process.returncode is None:
                process.kill()
        await process.wait()
        raise
    return process.returncode, output
