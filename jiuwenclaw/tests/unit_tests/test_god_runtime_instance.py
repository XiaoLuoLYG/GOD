"""Exercise the GOD launcher helper against isolated instance registries."""

import json
import os
from pathlib import Path
import subprocess
import sys

import yaml

_HELPER = Path(__file__).resolve().parents[3] / "scripts" / "god_runtime_instance.py"


def run_helper(home, *args):
    output = subprocess.run(
        [sys.executable, str(_HELPER), *args],
        env={**os.environ, "HOME": str(home), "USERPROFILE": str(home), "JIUWENSWARM_HOME": str(home)},
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    return json.loads(output)["workspace"] if output else None


def test_reuses_custom_legacy_workspace_and_preserves_other_registry_entries(tmp_path):
    workspace = tmp_path / "已有 custom instance"
    config = workspace / "config" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("preferred_language: en\n", encoding="utf-8")
    legacy_memory = workspace / "agent" / "jiuwenclaw_workspace" / "memory" / "notes.md"
    legacy_memory.parent.mkdir(parents=True)
    legacy_memory.write_text("legacy memory", encoding="utf-8")
    new_memory = workspace / "agent" / "workspace" / "memory" / "notes.md"
    legacy_path = tmp_path / ".jiuwenclaw" / "instances.yaml"
    legacy_path.parent.mkdir()
    legacy_data = {
        "instances": {
            "god-town": {"workspace": str(workspace)},
            "other": {"workspace": str(tmp_path / "other")},
        },
    }
    legacy_path.write_text(yaml.safe_dump(legacy_data), encoding="utf-8")

    assert Path(run_helper(tmp_path, "configure", "god-town", "zh", "19092", "20000", "20001", "6173")) == workspace
    assert yaml.safe_load(legacy_path.read_text(encoding="utf-8")) == legacy_data
    assert config.read_text(encoding="utf-8") == "preferred_language: en\n"
    assert "JIUWENSWARM_DATA_DIR=" in (workspace / ".env").read_text(encoding="utf-8")
    assert new_memory.read_text(encoding="utf-8") == "legacy memory"
    new_memory.write_text("new memory", encoding="utf-8")
    run_helper(tmp_path, "configure", "god-town", "zh", "19092", "20000", "20001", "6173")
    assert new_memory.read_text(encoding="utf-8") == "new memory"
    assert legacy_memory.read_text(encoding="utf-8") == "legacy memory"

    current_path = tmp_path / ".jiuwenswarm" / "instances.yaml"
    instance = yaml.safe_load(current_path.read_text(encoding="utf-8"))["instances"]["god-town"]
    assert Path(instance["workspace"]) == workspace
    assert instance["ports"] == {"agent_server": 19092, "web": 20000, "gateway": 20001, "frontend": 6173}
    run_helper(tmp_path, "forget", "god-town")
    assert yaml.safe_load(current_path.read_text(encoding="utf-8"))["instances"] == {}
    assert yaml.safe_load(legacy_path.read_text(encoding="utf-8"))["instances"] == {"other": legacy_data["instances"]["other"]}


def test_creates_fresh_named_workspace_with_requested_language(tmp_path):
    workspace = tmp_path / ".jiuwenswarm-instances" / "god-town"
    assert Path(run_helper(tmp_path, "configure", "god-town", "en", "19092", "20000", "20001", "6173")) == workspace
    config = yaml.safe_load((workspace / "config" / "config.yaml").read_text(encoding="utf-8"))
    assert config["preferred_language"] == "en"
    assert (workspace / "config" / ".env").is_file()
