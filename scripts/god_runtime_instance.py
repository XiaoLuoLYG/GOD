"""Configure the JiuwenSwarm instance used by both GOD launchers."""

import argparse
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from ruamel.yaml import YAML

from jiuwenswarm.common.utils import prepare_workspace
from jiuwenswarm.instance_manager import (
    PORT_TYPES,
    InstanceConfig,
    create_bootstrap_env,
    get_instance_config,
    get_instance_workspace_path,
    validate_instance_name,
)
from jiuwenswarm.instance_manager.yaml import load_instances_yaml, save_instances_yaml


def legacy_registry() -> tuple[Path, dict]:
    path = Path.home() / ".jiuwenclaw" / "instances.yaml"
    data = YAML().load(path.read_text(encoding="utf-8")) if path.exists() else None
    if data is None:
        data = {"instances": {}}
    if not isinstance(data, dict) or not isinstance(data.get("instances"), dict):
        raise ValueError(f"Invalid legacy runtime registry: {path}")
    return path, data


def configure(name: str, language: str, ports: dict[str, int]) -> Path:
    error = validate_instance_name(name)
    if error:
        raise ValueError(error)
    if any(not 1 <= port <= 65535 for port in ports.values()) or len(set(ports.values())) != len(ports):
        raise ValueError("Runtime ports must be distinct integers from 1 to 65535")

    existing = get_instance_config(name)
    if existing is None:
        _, legacy = legacy_registry()
        legacy_entry = legacy.get("instances", {}).get(name) or {}
        legacy_path = legacy_entry.get("workspace") or Path.home() / ".jiuwenclaw-instances" / name
        legacy_workspace = Path(legacy_path).expanduser()
        workspace = legacy_workspace if legacy_workspace.is_dir() else get_instance_workspace_path(name)
    else:
        workspace = existing.workspace

    config = InstanceConfig(name, workspace, ports)
    agent_root = config.workspace / "agent"
    legacy_agent = agent_root / "jiuwenclaw_workspace"
    agent_workspace = agent_root / "workspace"
    if legacy_agent.is_dir() and not agent_workspace.exists():
        # Keep the original layout available to the previous runtime.
        with tempfile.TemporaryDirectory(dir=agent_root) as temp_dir:
            staged = Path(temp_dir) / "workspace"
            shutil.copytree(legacy_agent, staged, symlinks=True)
            staged.rename(agent_workspace)
    if not (config.workspace / "config" / "config.yaml").is_file():
        prepare_workspace(overwrite=False, preferred_language=language, workspace_dir=config.workspace)

    data = load_instances_yaml()
    data["instances"].setdefault(name, {}).update(workspace=str(config.workspace), ports=ports)
    save_instances_yaml(data)
    create_bootstrap_env(config)
    return config.workspace


def forget(names: list[str]) -> None:
    current = load_instances_yaml()
    legacy_path, legacy = legacy_registry()
    current_names = current["instances"].keys() & set(names)
    if current_names:
        for name in current_names:
            del current["instances"][name]
        save_instances_yaml(current)
    legacy_names = legacy["instances"].keys() & set(names)
    if legacy_names:
        for name in legacy_names:
            del legacy["instances"][name]
        fd, temp_path = tempfile.mkstemp(dir=legacy_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                YAML().dump(legacy, file)
            os.replace(temp_path, legacy_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("configure")
    setup.add_argument("name")
    setup.add_argument("language", choices=("zh", "en"))
    setup.add_argument("ports", type=int, nargs=len(PORT_TYPES))
    commands.add_parser("forget").add_argument("names", nargs="+")
    args = parser.parse_args()
    if args.command == "forget":
        forget(args.names)
    else:
        with redirect_stdout(sys.stderr):
            workspace = configure(args.name, args.language, dict(zip(PORT_TYPES, args.ports, strict=True)))
        print(json.dumps({"workspace": str(workspace)}))


if __name__ == "__main__":
    main()
