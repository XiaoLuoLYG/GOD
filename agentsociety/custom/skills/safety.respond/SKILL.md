---
name: safety.respond
description: Respond to urgent or risky events with safety movement, announcement, and memory.
script: scripts/run_skill.py
shared: true
effects:
  - move
  - interact
  - set_state
  - group_message
  - remember
args_schema: {"type":"object","additionalProperties":true}
trigger_examples:
  - fire, earthquake, emergency, evacuation, urgent warning, or safety intervention is present
outputs:
  - state/skill_results/safety_respond.json
---

# Safety Respond

This is a real executable GOD agent skill. Its local `skill.json` describes
its own targets, interaction preferences, status changes, speech template,
memory template, and fallback strategy. `scripts/run_skill.py` returns a
standard `SkillResult`; the JiuwenClawAgent runtime validates and applies the
result to movement, interaction, speech, state, and memory.
