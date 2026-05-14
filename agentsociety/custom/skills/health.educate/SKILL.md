---
name: health.educate
description: Explain practical health advice in everyday language.
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
  - the agent needs to use health.educate in a grounded town situation
outputs:
  - state/skill_results/health_educate.json
---

# Health Educate

This is a real executable GOD agent skill. Its local `skill.json` describes
its own targets, interaction preferences, status changes, speech template,
memory template, and fallback strategy. `scripts/run_skill.py` returns a
standard `SkillResult`; the JiuwenClawAgent runtime validates and applies the
result to movement, interaction, speech, state, and memory.
