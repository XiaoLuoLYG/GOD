import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import anyio

from agentsociety2.agent.brains import (
    AgentBrain,
    SkillDecision,
    create_agent_brains,
    inject_experiment_backend,
    register_brain,
    resolve_brain_spec,
    scan_custom_brains,
)
from agentsociety2.agent.brains.registry import brains
from agentsociety2.society.cli import ExperimentRunner
from agentsociety2.society.models import InitConfig


def _load_jiuwenclaw_agent_class():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "custom" / "agents" / "jiuwenclaw_agent.py"
    spec = importlib.util.spec_from_file_location("god_custom_jiuwenclaw_agent_brains", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.JiuwenClawAgent


def _agent(**kwargs):
    JiuwenClawAgent = _load_jiuwenclaw_agent_class()
    values = {"id": 7, "name": "Ada", "profile": {"name": "Ada"}}
    values.update(kwargs)
    return JiuwenClawAgent(**values)


def _choice_kwargs():
    return {
        "tick": 60,
        "t": datetime(2026, 5, 26, tzinfo=timezone.utc),
        "observation": {},
        "catalog": [{"name": "routine.daily", "description": "day"}],
        "mounted_skill_ids": ["routine.daily", "safety.respond", "social.reply"],
        "pending_interventions": [],
        "broadcast_result": "",
    }


def test_resolve_brain_priority(monkeypatch):
    monkeypatch.setenv("GOD_AGENT_BACKEND", "openai_compat")

    agent_spec = resolve_brain_spec(
        brain={"type": "JiuwenClawAgent", "request_timeout": 12},
        agent_backend={"type": "openai_compat", "model": "experiment-model"},
    )
    assert agent_spec.name == "jiuwenclaw"
    assert agent_spec.source == "agent"
    assert agent_spec.overrides == {"request_timeout": 12}

    experiment_spec = resolve_brain_spec(
        brain="",
        agent_backend={"type": "openai-compat", "model": "experiment-model"},
    )
    assert experiment_spec.name == "openai_compat"
    assert experiment_spec.source == "experiment"
    assert experiment_spec.overrides == {"model": "experiment-model"}

    env_spec = resolve_brain_spec(brain=None, agent_backend={"type": ""})
    assert env_spec.name == "openai_compat"
    assert env_spec.source == "env"
    assert env_spec.overrides == {}

    monkeypatch.delenv("GOD_AGENT_BACKEND", raising=False)
    default_spec = resolve_brain_spec(brain=None, agent_backend=None)
    assert default_spec.name == "jiuwenclaw"
    assert default_spec.source == "default"


def test_jiuwenclaw_agent_name_is_backend_alias():
    assert resolve_brain_spec(brain="JiuwenClawAgent").name == "jiuwenclaw"
    assert resolve_brain_spec(brain="jiuwen_claw").name == "jiuwenclaw"


def test_default_backend_does_not_scan_custom_brains(monkeypatch, tmp_path):
    monkeypatch.delenv("GOD_AGENT_BACKEND", raising=False)
    scanned = []

    def record_scan(workspace):
        scanned.append(workspace)

    monkeypatch.setattr(
        "agentsociety2.agent.brains.registry.scan_custom_brains",
        record_scan,
    )
    brain, ask = create_agent_brains(host=object(), workspace=tmp_path)
    assert ask is brain
    assert brain.name == "jiuwenclaw"
    assert "choose_skill" in brain.capabilities
    assert "ask" in brain.capabilities
    assert scanned == []


def test_init_config_omits_empty_agent_backend_and_keeps_a_real_one():
    bare = InitConfig.model_validate(
        {
            "env_modules": [{"module_type": "pixel_town_social_env", "kwargs": {}}],
            "agents": [
                {
                    "agent_id": 1,
                    "agent_type": "JiuwenClawAgent",
                    "kwargs": {"id": 1},
                }
            ],
        }
    )
    dumped = bare.model_dump(mode="json")
    assert "agent_backend" not in dumped

    configured = InitConfig.model_validate(
        {
            "env_modules": [{"module_type": "pixel_town_social_env", "kwargs": {}}],
            "agents": [
                {
                    "agent_id": 1,
                    "agent_type": "JiuwenClawAgent",
                    "kwargs": {"id": 1},
                }
            ],
            "agent_backend": "openai_compat",
        }
    )
    assert configured.agent_backend == {"type": "openai_compat"}
    assert configured.model_dump(mode="json")["agent_backend"] == {"type": "openai_compat"}


def test_inject_experiment_backend_respects_agent_constructor():
    class PlainAgent:
        def __init__(self, id: int) -> None:
            self.id = id

    class BrainAgent:
        def __init__(self, id: int, agent_backend=None, brain=None) -> None:
            self.id = id
            self.agent_backend = agent_backend
            self.brain = brain

    original = {"id": 1, "brain": {"type": "jiuwenclaw"}}
    assert inject_experiment_backend(PlainAgent, {"id": 1}, {"type": "openai_compat"}) == {"id": 1}
    injected = inject_experiment_backend(BrainAgent, {"id": 1}, {"type": "openai_compat"})
    assert injected["agent_backend"] == {"type": "openai_compat"}
    assert "brain" not in injected
    kept = inject_experiment_backend(
        BrainAgent,
        original,
        {"type": "openai_compat"},
    )
    assert kept["brain"] == {"type": "jiuwenclaw"}
    assert kept["agent_backend"] == {"type": "openai_compat"}
    assert original == {"id": 1, "brain": {"type": "jiuwenclaw"}}


def test_create_agents_passes_experiment_backend_without_overriding_brain(monkeypatch):
    captured = {}

    class Agent:
        def __init__(self, id: int, brain=None, agent_backend=None) -> None:
            captured["id"] = id
            captured["brain"] = brain
            captured["agent_backend"] = agent_backend

    monkeypatch.setattr(
        "agentsociety2.society.cli.get_registered_agent_modules",
        lambda: [("JiuwenClawAgent", Agent)],
    )
    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner._create_agents(
        [
            {
                "agent_id": 3,
                "agent_type": "JiuwenClawAgent",
                "kwargs": {"id": 3, "brain": {"type": "jiuwenclaw"}},
            }
        ],
        agent_backend={"type": "openai_compat"},
    )
    assert captured == {
        "id": 3,
        "brain": {"type": "jiuwenclaw"},
        "agent_backend": {"type": "openai_compat"},
    }


def test_jiuwenclaw_agent_type_remains_default_brain_alias(monkeypatch):
    monkeypatch.delenv("GOD_AGENT_BACKEND", raising=False)
    agent = _agent()
    assert type(agent).__name__ == "JiuwenClawAgent"
    assert agent._brain.name == "jiuwenclaw"
    assert agent._ws is None


def test_backend_failure_uses_existing_skill_fallback(monkeypatch):
    monkeypatch.delenv("GOD_AGENT_BACKEND", raising=False)
    agent = _agent(brain={"type": "codex"})

    async def run_case():
        failed = await agent._select_next_skill(**_choice_kwargs())
        urgent = dict(_choice_kwargs())
        urgent["observation"] = {"latest_event": "火灾"}
        urgent_decision = await agent._select_next_skill(**urgent)
        return failed, urgent_decision

    failed, urgent_decision = anyio.run(run_case)
    assert failed["fallback"] is True
    assert failed["selected_skill_id"] == "routine.daily"
    assert failed["args"] == {}
    assert "unknown agent backend: codex" in failed["reason"]
    assert urgent_decision["selected_skill_id"] == "safety.respond"
    assert "九问" not in agent._last_response


def test_jiuwenclaw_parse_failure_keeps_legacy_fallback_text(monkeypatch):
    monkeypatch.delenv("GOD_AGENT_BACKEND", raising=False)
    agent = _agent()

    async def choose_skill(_request):
        return SkillDecision(raw="not-json", prompt="prompt text")

    async def run_case():
        agent._brain.choose_skill = choose_skill
        return await agent._select_next_skill(**_choice_kwargs())

    decision = anyio.run(run_case)
    assert decision["fallback"] is True
    assert decision["reason"] == "后备技能选择：九问返回的技能决策不是 JSON。"
    assert agent._last_response == "not-json"


def test_jiuwenclaw_request_error_keeps_legacy_failure_text(monkeypatch):
    monkeypatch.delenv("GOD_AGENT_BACKEND", raising=False)
    agent = _agent()

    async def choose_skill(_request):
        raise TimeoutError("timed out")

    async def run_case():
        agent._brain.choose_skill = choose_skill
        return await agent._select_next_skill(**_choice_kwargs())

    decision = anyio.run(run_case)
    assert decision["fallback"] is True
    assert decision["reason"] == "后备技能选择：timed out"
    assert agent._last_response == "九问技能选择失败：timed out"


def test_openai_compat_mocked_http_chooses_skill_and_answers(monkeypatch):
    monkeypatch.delenv("GOD_AGENT_BACKEND", raising=False)
    monkeypatch.setenv("GOD_LLM_API_KEY", "sk-test")
    monkeypatch.setenv("GOD_LLM_API_BASE", "https://example.test/v1")
    monkeypatch.setenv("GOD_LLM_MODEL", "unit-model")
    captured = {}

    async def fake_post(url, api_key, payload, timeout_s):
        captured.setdefault("calls", []).append(
            {
                "url": url,
                "api_key": api_key,
                "model": payload["model"],
                "content": payload["messages"][0]["content"],
                "timeout_s": timeout_s,
            }
        )
        if "选择本步骤唯一要执行的技能" in payload["messages"][0]["content"]:
            content = json.dumps(
                {
                    "selected_skill_id": "social.reply",
                    "args": {"tone": "warm"},
                    "reason": "有人说话",
                    "public_summary": "回复邻居",
                },
                ensure_ascii=False,
            )
        else:
            content = "我在广场。"
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 5},
        }

    monkeypatch.setattr("agentsociety2.agent.brains.openai_compat._post_json", fake_post)
    agent = _agent(brain={"type": "openai_compat"})

    async def run_case():
        choice = _choice_kwargs()
        choice["observation"] = {"recent_messages": [{"content": "你好"}]}
        choice["catalog"] = [
            {"name": "routine.daily", "description": "day"},
            {"name": "social.reply", "description": "reply"},
        ]
        decision = await agent._select_next_skill(**choice)
        answer = await agent.ask("你在哪里？", readonly=True)
        return decision, answer

    decision, answer = anyio.run(run_case)
    assert agent._brain.name == "openai_compat"
    assert decision == {
        "selected_skill_id": "social.reply",
        "args": {"tone": "warm"},
        "reason": "有人说话",
        "public_summary": "回复邻居",
        "usage": {"input_tokens": 3, "output_tokens": 5},
        "latency_ms": decision["latency_ms"],
    }
    assert decision["latency_ms"] >= 0
    assert answer == "我在广场。"
    assert agent._last_response == "我在广场。"
    assert captured["calls"][0]["url"] == "https://example.test/v1/chat/completions"
    assert captured["calls"][0]["api_key"] == "sk-test"
    assert captured["calls"][0]["model"] == "unit-model"
    assert "social.reply" in captured["calls"][0]["content"]
    assert "secret" not in captured["calls"][0]["content"]


def test_openai_compat_http_error_falls_back_without_response_body(monkeypatch):
    monkeypatch.delenv("GOD_AGENT_BACKEND", raising=False)
    monkeypatch.setenv("GOD_LLM_API_KEY", "sk-test")
    monkeypatch.setenv("GOD_LLM_MODEL", "unit-model")

    async def fake_post(_url, _api_key, _payload, _timeout_s):
        raise RuntimeError("openai_compat HTTP 503")

    monkeypatch.setattr("agentsociety2.agent.brains.openai_compat._post_json", fake_post)
    agent = _agent(agent_backend={"type": "openai_compat", "model": "override-model"})

    async def run_case():
        return await agent._select_next_skill(**_choice_kwargs())

    decision = anyio.run(run_case)
    assert decision["fallback"] is True
    assert decision["selected_skill_id"] == "routine.daily"
    assert agent._last_response == "技能选择失败：openai_compat HTTP 503"
    assert "response body" not in agent._last_response
    assert agent._brain.config["model"] == "override-model"


def test_custom_brain_module_can_register_without_replacing_builtin(tmp_path, monkeypatch):
    monkeypatch.delenv("GOD_AGENT_BACKEND", raising=False)
    brains_dir = tmp_path / "custom" / "brains"
    brains_dir.mkdir(parents=True)
    (brains_dir / "demo_brain.py").write_text(
        "\n".join(
            [
                "from agentsociety2.agent.brains.base import AgentBrain, SkillDecision",
                "",
                "class DemoBrain(AgentBrain):",
                "    name = 'phase1_demo'",
                "    capabilities = frozenset({'choose_skill'})",
                "",
                "    def __init__(self, host=None, config=None):",
                "        self.host = host",
                "        self.config = dict(config or {})",
                "",
                "    async def choose_skill(self, req):",
                "        return SkillDecision(selected_skill_id='routine.daily')",
                "",
                "    async def ask(self, req):",
                "        return 'no'",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (brains_dir / "shadow_builtin.py").write_text(
        "\n".join(
            [
                "from agentsociety2.agent.brains.base import AgentBrain",
                "",
                "class Shadow(AgentBrain):",
                "    name = 'jiuwenclaw'",
                "    capabilities = frozenset()",
                "",
                "    def __init__(self, host=None, config=None):",
                "        raise AssertionError('custom scan must not replace jiuwenclaw')",
                "",
                "    async def choose_skill(self, req):",
                "        raise AssertionError('unused')",
                "",
                "    async def ask(self, req):",
                "        raise AssertionError('unused')",
                "",
            ]
        ),
        encoding="utf-8",
    )
    scan_custom_brains(tmp_path)
    assert "phase1_demo" in brains()
    assert brains()["jiuwenclaw"].__name__ == "JiuwenClawBrain"

    agent = _agent(brain="phase1_demo")

    async def run_case():
        decision = await agent._select_next_skill(**_choice_kwargs())
        try:
            await agent.ask("hi")
        except RuntimeError as exc:
            return decision, str(exc)
        raise AssertionError("ask must fail when the backend has no ask capability")

    decision, error = anyio.run(run_case)
    assert decision["selected_skill_id"] == "routine.daily"
    assert decision.get("fallback") is not True
    assert "does not support ask" in error

    class Replacement(AgentBrain):
        name = "phase1_replacement"
        capabilities = frozenset({"ask"})

        def __init__(self, host=None, config=None) -> None:
            self.host = host

        async def choose_skill(self, req):
            return SkillDecision()

        async def ask(self, req):
            return "registered"

    register_brain("phase1_replacement", Replacement)
    assert brains()["phase1_replacement"] is Replacement


def test_typed_brain_decision_is_used_and_ask_can_use_another_backend(monkeypatch):
    class TypedChoice(AgentBrain):
        name = "test_typed_choice"
        capabilities = frozenset({"choose_skill"})

        def __init__(self, *, config):
            self.config = config

        async def choose_skill(self, req):
            assert "social.reply" in req.mounted_skill_ids
            return SkillDecision(selected_skill_id="social.reply", args={"tone": "warm"})

        async def ask(self, req):
            raise AssertionError("the configured ask backend should answer")

    class TestAsk(AgentBrain):
        name = "test_independent_ask"
        capabilities = frozenset({"ask"})
        answered = 0

        async def choose_skill(self, req):
            raise AssertionError("the decision backend should select the skill")

        async def ask(self, req):
            self.answered += 1
            return f"answered: {req.message}"

        def dump(self):
            return {"answered": self.answered}

        def load(self, data):
            self.answered = data["answered"]

    monkeypatch.delenv("GOD_AGENT_ASK_BACKEND", raising=False)
    register_brain(TypedChoice.name, TypedChoice)
    register_brain(TestAsk.name, TestAsk)
    agent = _agent(brain={"type": TypedChoice.name, "ask_backend": TestAsk.name})

    async def run_case():
        decision = await agent._select_next_skill(**_choice_kwargs())
        assert decision["selected_skill_id"] == "social.reply"
        assert decision["args"] == {"tone": "warm"}
        assert decision.get("fallback") is not True
        assert await agent.ask("hello") == "answered: hello"
        snapshot = await agent.dump()
        assert snapshot["backend_states"] == {"ask": {"backend": TestAsk.name, "state": {"answered": 1}}}
        resumed = _agent(brain={"type": TypedChoice.name, "ask_backend": TestAsk.name})
        await resumed.load(snapshot)
        assert resumed._ask_brain.answered == 1

    anyio.run(run_case)


def test_openai_compat_provider_connection_is_local_configuration(monkeypatch):
    from agentsociety2.agent.brains.openai_compat import resolve_llm_settings

    monkeypatch.setenv("GOD_LLM_API_KEY", "local-test")
    monkeypatch.setenv("GOD_LLM_API_BASE", "https://local-provider.example/v1")
    monkeypatch.setenv("GOD_LLM_MODEL", "local-default")
    settings = resolve_llm_settings({"model": "scenario-model", "api_base": "https://scenario.example/v1"})
    assert settings.api_base == "https://local-provider.example/v1"
    assert settings.api_key == "local-test"
    assert settings.model == "scenario-model"


def test_launcher_and_agents_use_the_same_backend_priority():
    from agentsociety2.agent.brains.config import requires_jiuwenclaw

    agent = {"agent_id": 1, "agent_type": "JiuwenClawAgent", "kwargs": {}}
    assert requires_jiuwenclaw({"agents": [agent]}, {})
    assert not requires_jiuwenclaw({"agents": [agent]}, {"GOD_AGENT_BACKEND": "openai_compat"})
    assert not requires_jiuwenclaw({"agents": [agent], "agent_backend": "jev"}, {})
    assert requires_jiuwenclaw(
        {"agents": [agent], "agent_backend": {"type": "jev", "ask_backend": "jiuwenclaw"}}, {}
    )
    assert not requires_jiuwenclaw({"agents": [{**agent, "agent_type": "ScriptedPixelTownAgent"}]}, {})
    override = {**agent, "agent_id": 2, "kwargs": {"brain": "JiuwenClawAgent"}}
    assert requires_jiuwenclaw({"agents": [agent, override], "agent_backend": "openai_compat"}, {})


def test_decision_apis_execute_the_selected_skill(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from aiohttp import web

    expected = {"type": "choice", "choice": "memory.record", "confidence": 0.94}

    async def run_case():
        calls = []

        async def decide(request):
            payload = await request.json()
            calls.append(payload)
            if isinstance(payload["questions"], list):
                assert {item["value"] for item in payload["questions"][0]["choices"]} == {
                    "routine.daily", "memory.record"
                }
                return web.json_response({"answers": [{"name": "skill", **expected}]})
            assert set(payload["questions"]["skill"]["criteria"]) == {"routine.daily", "memory.record"}
            result = {"answers": {"skill": expected}}
            if payload["model"] == "fixture-model":
                return web.json_response({"result": result})
            return web.json_response(result)

        app = web.Application()
        app.router.add_post("/choose", decide)
        runner = web.AppRunner(app)
        await runner.setup()
        try:
            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()
            port = runner.addresses[0][1]
            url = f"http://127.0.0.1:{port}/choose"
            monkeypatch.setattr("agentsociety2.agent.brains.decision_api.JEV_URL", url)
            monkeypatch.setenv("TYPESAFE_API_KEY", "local-test")
            monkeypatch.setenv("GOD_DECISION_API_URL", url)
            monkeypatch.setenv("GOD_DECISION_API_KEY", "local-test")
            monkeypatch.setenv("GOD_DECISION_MODEL", "fixture-model")
            monkeypatch.setenv("GOD_OPENAI_DECISIONS_URL", url)
            monkeypatch.setenv("GOD_OPENAI_DECISIONS_API_KEY", "local-test")
            for backend in ("jev", "decision_api", "openai_decisions"):
                run_dir = tmp_path / backend
                run_dir.mkdir()
                agent = _agent(brain=backend, common_skill_ids=["routine.daily", "memory.record"])
                await agent.init(SimpleNamespace(run_dir=run_dir, env_modules=[]))
                result = await agent._run_skill_runtime(
                    tick=60,
                    t=datetime(2026, 5, 26, tzinfo=timezone.utc),
                    observation={"latest_event": "The town clock was set to 9 am."},
                )
                assert result["ok"]
                assert result["activated_skills"] == ["memory.record"]
                assert result["last_skill_decision"]["decision_backend"] == backend
                assert result["last_skill_decision"]["confidence"] == 0.94
                await agent.close()
        finally:
            await runner.cleanup()

        assert len(calls) == 3

    anyio.run(run_case)


def test_command_backend_reads_request_and_returns_a_typed_decision(monkeypatch):
    import sys

    command = [sys.executable, "-I", "-c", (
        "import sys; "
        "assert 'social.reply' in sys.stdin.read(); "
        "print('{\"selected_skill_id\":\"social.reply\",\"args\":{\"tone\":\"warm\"}}')"
    )]
    monkeypatch.setenv("GOD_AGENT_COMMANDS", json.dumps({"fixture": command}))
    agent = _agent(brain={"type": "command", "profile": "fixture"})
    request = _choice_kwargs()
    request["catalog"].append({"name": "social.reply", "description": "reply"})
    decision = anyio.run(lambda: agent._select_next_skill(**request))
    assert decision["selected_skill_id"] == "social.reply"
    assert decision["args"] == {"tone": "warm"}
    assert decision.get("fallback") is not True
