# Jev skill-choice comparison

GOD can ask [TypeSafe Jev](https://docs.typesafe.ai/api) which mounted skill an agent should use, alongside its existing JiuwenClaw decision. This is an opt-in experiment: Jev's answer is recorded, while JiuwenClaw still supplies the executed skill, arguments, reason and summary. It does not establish a speedup or change Ask/Intervene behavior.

In the root `.env`, set:

```dotenv
GOD_JEV_SHADOW=1
TYPESAFE_API_KEY=your-key
GOD_JEV_MODEL=jev-latest
```

Restart GOD, then run a simulation step. Enabling this sends the agent profile, experiment context, observation, pending interventions and skill descriptions to TypeSafe and incurs API usage. Default is off. To reproduce a comparison later, pin `GOD_JEV_MODEL` to the actual model returned by the API.

The existing agent snapshot and step logs include `last_skill_decision.jev_shadow`: status, choice, confidence, probability distribution, model, token usage, request latency and whether it matches the skill ultimately selected. The normal JiuwenClaw request timing remains in backend logs. Agreement is not a correctness metric.

Both calls run concurrently. The optional request has a five-second budget, so it can add up to that delay when JiuwenClaw finishes earlier. Missing keys or catalogs outside 1–255 choices are recorded as skipped; timeouts, HTTP failures and invalid responses are recorded as errors. They do not replace the original decision or its existing fallback. Response bodies and keys are not recorded in errors.

For one live connectivity check without starting a town, from `agentsociety/`:

```bash
uv run python scripts/check_jev.py
# An isolated checkout can use an existing local configuration:
uv run python scripts/check_jev.py --env-file /path/to/GOD/.env
```

This sends a small synthetic two-skill example through the same production client. Exit 0 means a valid response, not a behavior-quality benchmark. Without a key it exits 1 with `missing_api_key`. Local HTTP tests exercise the protocol, failure cases and preserved decisions; a real API key is still needed to establish live quality, latency and cost.

No additional dependency is required. Set `GOD_JEV_SHADOW=0` and restart to disable comparisons.
