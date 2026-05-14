---
name: social.reply
description: Reply to a recent direct or group message without inventing unrelated movement.
script: scripts/run_skill.py
shared: true
effects:
  - set_state
  - direct_message
  - group_message
  - remember
args_schema: {"type":"object","additionalProperties":true}
trigger_examples:
  - another agent or user has sent a message that deserves a response
outputs:
  - state/skill_results/social_reply.json
---

# Social Reply

This is a real executable GOD agent skill. Its local `skill.json` describes
its own targets, interaction preferences, status changes, speech template,
memory template, and fallback strategy. `scripts/run_skill.py` returns a
standard `SkillResult`; the JiuwenClawAgent runtime validates and applies the
result to movement, interaction, speech, state, and memory.
