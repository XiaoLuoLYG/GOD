import json
from pathlib import Path

from agentsociety2.society.cli import ExperimentRunner
from agentsociety2.society.launch_config import prepare_launch


def test_runtime_settings_follow_the_selected_run_and_current_cast(tmp_path, monkeypatch):
    monkeypatch.delenv("GOD_SESSION_PREFIX", raising=False)
    monkeypatch.setenv("GOD_MAP_ID", "pku")
    experiment = tmp_path / "hypothesis_custom" / "experiment_3"
    config = experiment / "init/init_config.json"
    config.parent.mkdir(parents=True)
    data = {
        "env_modules": [{"module_type": "PixelTownSocialEnv", "kwargs": {"map_id": "the_ville"}}],
        "agents": [{"agent_type": "JiuwenClawAgent", "agent_id": 1,
                    "kwargs": {"id": 1, "session_id": "authored", "trusted_dirs": ["authored-dir"]}}],
    }
    config.write_text(json.dumps(data), encoding="utf-8")
    run_dir = experiment / "run"
    runner = ExperimentRunner(run_dir)
    independent = ExperimentRunner(experiment / "other-run")
    assert runner._load_config(config).agents[0].kwargs == data["agents"][0]["kwargs"]

    prepare_launch(config, tmp_path, 19876)
    kwargs = runner._load_config(config).agents[0].kwargs
    assert kwargs == {"id": 1, "session_id": "custom_run_3_agent_1", "trusted_dirs": [str(tmp_path)],
                      "jiuwenclaw_ws_url": "ws://127.0.0.1:19876"}
    assert independent._load_config(config).agents[0].kwargs == data["agents"][0]["kwargs"]
    assert runner._load_config(config).env_modules[0].kwargs["map_manifest_path"] == "custom/maps/pku/map.yaml"
    assert json.loads(config.read_text(encoding="utf-8")) == data

    # new-run saves this marker before startup. Restart must retain it and reread later source edits.
    (run_dir / ".god-session-prefix").write_text("custom_fresh_fixture\n", encoding="utf-8")
    monkeypatch.delenv("GOD_MAP_ID")
    data["agents"].append({"agent_type": "JiuwenClawAgent", "agent_id": 2, "kwargs": {"id": 2, "name": "New resident"}})
    config.write_text(json.dumps(data), encoding="utf-8")
    prepare_launch(config, tmp_path, 19877)
    prepare_launch(config, tmp_path, 19877)
    reloaded = runner._load_config(config)
    assert [a.kwargs["session_id"] for a in reloaded.agents] == ["custom_fresh_fixture_agent_1", "custom_fresh_fixture_agent_2"]
    assert reloaded.agents[1].kwargs["name"] == "New resident"
    assert reloaded.env_modules[0].kwargs["map_id"] == "pku"
    assert json.loads(config.read_text(encoding="utf-8")) == data
    other_config = config.with_name("alternate.json")
    other_config.write_bytes(config.read_bytes())
    assert runner._load_config(other_config).agents[0].kwargs == data["agents"][0]["kwargs"]
    prepare_launch(config, tmp_path, 0)
    assert runner._load_config(config).agents[0].kwargs == data["agents"][0]["kwargs"]


def test_upgrade_keeps_legacy_jiuwen_session_and_replay(tmp_path, monkeypatch):
    monkeypatch.delenv("GOD_SESSION_PREFIX", raising=False)
    experiment = tmp_path / "hypothesis_god_town" / "experiment_1"
    config = experiment / "init/init_config.json"
    config.parent.mkdir(parents=True)
    template = Path(__file__).resolve().parents[3] / "quick_experiments/hypothesis_god_town/experiment_1/init/init_config.json"
    config.write_bytes(template.read_bytes())
    run_dir = experiment / "run"
    history = run_dir / "agents/agent_0001/agent_config.json"
    history.parent.mkdir(parents=True)
    history.write_text(json.dumps({"id": 1, "decision_backend": "openai_compat", "ask_backend": "jiuwenclaw",
                                   "session_id": "legacy_fresh_2026_agent_1"}), encoding="utf-8")
    database = run_dir / "sqlite.db"
    database.write_bytes(b"existing replay")
    prepare_launch(config, tmp_path, 19879)
    loaded = ExperimentRunner(run_dir)._load_config(config)
    assert all(a.kwargs["session_id"] == f"legacy_fresh_2026_agent_{a.agent_id}" for a in loaded.agents)
    assert database.read_bytes() == b"existing replay"
    assert config.read_bytes() == template.read_bytes()
