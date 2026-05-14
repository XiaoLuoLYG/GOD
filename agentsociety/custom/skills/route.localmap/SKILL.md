---
name: route.localmap
description: Use local map knowledge to pick a sensible route.
script: scripts/run_skill.py
shared: false
effects:
  - move
  - interact
  - set_state
  - direct_message
  - group_message
  - remember
args_schema: {"type":"object","additionalProperties":true}
trigger_examples:
  - the agent needs to use route.localmap in a grounded town situation
outputs:
  - state/skill_results/route_localmap.json
---

# Route Localmap

This is a real executable GOD agent skill. Its local `skill.json` describes
its own targets, interaction preferences, status changes, speech template,
memory template, and fallback strategy. `scripts/run_skill.py` returns a
standard `SkillResult`; the JiuwenClawAgent runtime validates and applies the
result to movement, interaction, speech, state, and memory.
