"""Machine-local settings shared by the GOD launchers and experiment readers."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


_SETTINGS_FILE = ".god-launch.json"


def read_launch_settings(run_dir: Path) -> dict[str, Any]:
    path = run_dir / _SETTINGS_FILE
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(settings, dict):
        raise ValueError(f"Expected GOD launch settings in {path}")
    return settings


def launch_map_id(experiment: Path) -> str | None:
    run_dir = experiment / "run"
    if not (run_dir / _SETTINGS_FILE).resolve().is_relative_to(experiment.resolve()):
        return None
    return read_launch_settings(run_dir).get("map_id")


def apply_map_override(config: dict[str, Any], map_id: str | None) -> None:
    if map_id:
        for module in config.get("env_modules", []):
            if module.get("module_type") == "PixelTownSocialEnv":
                kwargs = module.setdefault("kwargs", {})
                kwargs["map_id"] = map_id
                kwargs["map_manifest_path"] = f"custom/maps/{map_id}/map.yaml"


def apply_launch_settings(config: dict[str, Any], settings: dict[str, Any]) -> None:
    apply_map_override(config, settings.get("map_id"))
    if settings.get("runtime_port"):
        for agent in config.get("agents", []):
            if agent.get("agent_type") == "JiuwenClawAgent":
                kwargs = agent["kwargs"]
                kwargs["jiuwenclaw_ws_url"] = f"ws://127.0.0.1:{settings['runtime_port']}"
                kwargs["session_id"] = f"{settings['session_prefix']}_agent_{int(agent['agent_id'])}"
                kwargs["trusted_dirs"] = [settings["backend_root"]]


def _legacy_session_prefix(run_dir: Path) -> str:
    # Older runs recorded the actual decision and Ask sessions in each resident workspace.
    residents = run_dir / "agents"
    configs = sorted(residents.glob("agent_*/agent_config.json"))
    snapshots = sorted(residents.glob("agent_*/.runtime/logs/agent_state_snapshot.json"))
    for path in configs + snapshots:
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
            decision = snapshot.get("last_skill_decision") or {}
            backend = snapshot.get("decision_backend") or decision.get("decision_backend")
            used_jiuwen = backend in (None, "jiuwenclaw") or snapshot.get("ask_backend") == "jiuwenclaw"
            prefix, separator, agent_id = str(snapshot["session_id"]).rpartition("_agent_")
            if used_jiuwen and separator and agent_id == str(snapshot["id"]):
                return prefix
        except (OSError, ValueError, KeyError, AttributeError, TypeError):
            continue
    return ""


def prepare_launch(config_path: Path, backend_root: Path, runtime_port: int) -> None:
    experiment = config_path.parent.parent
    run_dir = experiment / "run"
    previous = read_launch_settings(run_dir)
    prefix_file = run_dir / ".god-session-prefix"
    saved = prefix_file.read_text(encoding="utf-8").strip() if prefix_file.is_file() else ""
    prefix = os.environ.get("GOD_SESSION_PREFIX") or saved or previous.get("session_prefix")
    if not prefix:
        hypothesis = experiment.parent.name.removeprefix("hypothesis_")
        experiment_id = experiment.name.removeprefix("experiment_")
        prefix = _legacy_session_prefix(run_dir) or f"{hypothesis}_run_{experiment_id}"
    map_id = os.environ.get("GOD_MAP_ID", "").strip() or previous.get("map_id")
    if map_id:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if not any(module.get("module_type") == "PixelTownSocialEnv" for module in config.get("env_modules", [])):
            map_id = None
    settings = {
        "runtime_port": runtime_port,
        "backend_root": str(backend_root.resolve()),
        "session_prefix": prefix,
        "map_id": map_id,
    }
    if settings == previous:
        return
    run_dir.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", dir=run_dir, encoding="utf-8", delete=False) as handle:
        temp = Path(handle.name)
        json.dump(settings, handle, ensure_ascii=False)
    try:
        temp.replace(run_dir / _SETTINGS_FILE)
    finally:
        temp.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Save machine settings for a GOD run")
    parser.add_argument("config_path", type=Path)
    parser.add_argument("backend_root", type=Path)
    parser.add_argument("runtime_port", type=int, help="Jiuwen agent port, or 0 when unused")
    args = parser.parse_args()
    prepare_launch(args.config_path, args.backend_root, args.runtime_port)
