# Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
"""Orchestrate AgentServer + Gateway in two processes (split layout, one command).

Runs ``jiuwenclaw.app_agentserver`` then ``jiuwenclaw.app_gateway`` with the same
environment as a normal CLI launch. Web RPC handlers live in ``app_web_handlers``.

Supports ``--dotenv <path>`` for multi-instance isolation.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

from dotenv import load_dotenv

# --- Early --dotenv parsing (before jiuwenclaw imports) ---
from jiuwenclaw.dotenv_early import parse_dotenv_early, get_parsed_dotenv
parse_dotenv_early("jiuwenclaw-app")

# --- Now safe to import jiuwenclaw modules ---
from jiuwenclaw.common.utils import (
    cleanup_team_files,
    get_env_file,
    get_user_workspace_dir,
    prepare_workspace,
    reset_free_search_runtime_flags,
)

# Record the parsed dotenv path for subprocess spawning
_parsed_dotenv_path = get_parsed_dotenv()


_workspace_dir = get_user_workspace_dir()
_config_file = _workspace_dir / "config" / "config.yaml"
_new_workspace = _workspace_dir / "agent" / "jiuwenclaw_workspace"
_old_workspace = _workspace_dir / "agent" / "workspace"

# 始终清理 Team 旧版本遗留文件（幂等操作，在 prepare_workspace 之前执行）
cleanup_team_files(_workspace_dir)

# Initialize if config doesn't exist, or if legacy workspace exists but new doesn't (migration)
if not _config_file.exists() or (_old_workspace.exists() and not _new_workspace.exists()):
    prepare_workspace(overwrite=False)

load_dotenv(dotenv_path=get_env_file(), override=True)
reset_free_search_runtime_flags()


def _agent_server_endpoint() -> tuple[str, int]:
    host = os.getenv("AGENT_SERVER_HOST", "127.0.0.1")
    connect_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    port_raw = os.getenv("AGENT_SERVER_PORT") or os.getenv("AGENT_PORT") or "18092"
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid AGENT_SERVER_PORT/AGENT_PORT: {port_raw}") from exc
    return connect_host, port


def _terminate_process(process: subprocess.Popen, *, timeout: float = 5.0) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout)


def _wait_for_agent_server(
    process: subprocess.Popen,
    *,
    host: str,
    port: int,
    timeout: float = 30.0,
) -> None:
    deadline = time.monotonic() + timeout
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"AgentServer exited before it became ready on {host}:{port} "
                f"(exit code {process.returncode})."
            )
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.1)
    detail = f": {last_error}" if last_error else ""
    raise RuntimeError(f"AgentServer did not become ready on {host}:{port} within {timeout:.0f}s{detail}.")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="jiuwenclaw-app",
        description="Start JiuWenClaw AgentServer + Gateway (split layout, one command).",
    )
    parser.add_argument(
        "--dotenv",
        metavar="<path>",
        help="Load environment from .env file (processed at startup, not used here).",
    )
    parser.add_argument(
        "--name",
        metavar="<name>",
        help="Start a named instance from instances.yaml.",
    )
    args = parser.parse_args()

    # Handle --name: check if bootstrap .env was loaded successfully
    # (parse_dotenv_early() already processed it at module import time)
    dotenv_path = _parsed_dotenv_path
    if args.name and dotenv_path is None:
        # Early parsing failed - error was already printed
        raise SystemExit(1)

    python = sys.executable

    # Build subprocess commands with --dotenv if parsed
    agent_cmd = [python, "-m", "jiuwenclaw.server.app_agentserver"]
    gateway_cmd = [python, "-m", "jiuwenclaw.gateway.app_gateway"]

    # Pass --dotenv to subprocesses for multi-instance isolation
    if dotenv_path is not None:
        agent_cmd.extend(["--dotenv", str(dotenv_path)])
        gateway_cmd.extend(["--dotenv", str(dotenv_path)])

    agent = subprocess.Popen(agent_cmd)
    gateway = None
    try:
        host, port = _agent_server_endpoint()
        _wait_for_agent_server(agent, host=host, port=port)
        gateway = subprocess.Popen(gateway_cmd)
    except Exception as exc:
        _terminate_process(agent)
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(f"Failed to start JiuwenClaw Gateway after AgentServer readiness check: {exc}") from exc
        raise

    procs: list[subprocess.Popen] = [agent] + ([gateway] if gateway else [])

    def _terminate_all() -> None:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        deadline = time.time() + 12
        while time.time() < deadline:
            if all(p.poll() is not None for p in procs):
                break
            time.sleep(0.1)
        for p in procs:
            if p.poll() is None:
                p.kill()

    exit_code = 0
    try:
        while True:
            if agent.poll() is not None:
                exit_code = agent.returncode or 0
                break
            if gateway is not None and gateway.poll() is not None:
                exit_code = gateway.returncode or 0
                break
            time.sleep(0.25)
    except KeyboardInterrupt:
        exit_code = 130
    finally:
        _terminate_all()

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
