---
name: memory.record
description: Write relevant step context into agent memory without moving or speaking by default.
script: scripts/run_skill.py
shared: true
effects:
  - remember
args_schema: {"type":"object","additionalProperties":true}
trigger_examples:
  - a meaningful event should be preserved for future decisions
outputs:
  - state/skill_results/memory_record.json
---

# Memory Record

This is a real executable GOD agent skill. Its local `skill.json` describes
its own targets, interaction preferences, status changes, speech template,
memory template, and fallback strategy. `scripts/run_skill.py` returns a
standard `SkillResult`; the JiuwenClawAgent runtime validates and applies the
result to movement, interaction, speech, state, and memory.
