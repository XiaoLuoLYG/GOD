Runtime Skills
==============

GOD uses JiuwenClaw as the out-of-process agent runtime and AgentSociety as the product-level skill execution path.

Runtime bridge
--------------

The default local runtime instance is ``god-town``. Startup maps GOD model settings to both AgentSociety and JiuwenClaw environment variables, then starts JiuwenClaw services on local ports.

Relevant defaults:

- Agent WebSocket: ``RUNTIME_AGENT_PORT=19092``
- Runtime web: ``RUNTIME_WEB_PORT=20000``
- Runtime gateway: ``RUNTIME_GATEWAY_PORT=20001``
- Runtime UI: ``RUNTIME_UI_PORT=6173``

Skill packages
--------------

Custom agent skills are managed through backend routes under ``/api/v1/agent-skills``. Setup and Agent Studio keep skill runtime metadata synchronized with experiment config so agents use the same runtime path after generation, import, and apply flows.

Where to inspect
----------------

- ``agentsociety/packages/agentsociety2/agentsociety2/backend/routers/agent_skills.py``
- ``agentsociety/packages/agentsociety2/agentsociety2/backend/routers/god_setup.py``
- ``agentsociety/packages/agentsociety2/agentsociety2/backend/routers/experiment_configs.py``
- ``jiuwenclaw/``
