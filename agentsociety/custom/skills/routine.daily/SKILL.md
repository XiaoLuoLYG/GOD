---
name: routine.daily
description: Choose a natural daily movement, interaction, or state from time, role, and current town context.
script: scripts/run_skill.py
shared: true
effects:
  - move
  - interact
  - set_state
  - remember
args_schema: {"type":"object","additionalProperties":true}
trigger_examples:
  - morning, lunch, work, school, evening, or sleep routine is the most natural next step
outputs:
  - state/skill_results/routine_daily.json
---

# Routine Daily

This is a real executable GOD agent skill. Its local `skill.json` describes
its own targets, interaction preferences, status changes, speech template,
memory template, and fallback strategy. `scripts/run_skill.py` returns a
standard `SkillResult`; the JiuwenClawAgent runtime validates and applies the
result to movement, interaction, speech, state, and memory.
