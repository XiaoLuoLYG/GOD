---
name: map.navigate
description: Move toward a requested target location or perform a requested interaction if already there.
script: scripts/run_skill.py
shared: true
effects:
  - move
  - interact
  - set_state
  - remember
args_schema: {"type":"object","additionalProperties":true}
trigger_examples:
  - the decision includes a specific target location or map interaction
outputs:
  - state/skill_results/map_navigate.json
---

# Map Navigate

This is a real executable GOD agent skill. Its local `skill.json` describes
its own targets, interaction preferences, status changes, speech template,
memory template, and fallback strategy. `scripts/run_skill.py` returns a
standard `SkillResult`; the JiuwenClawAgent runtime validates and applies the
result to movement, interaction, speech, state, and memory.
