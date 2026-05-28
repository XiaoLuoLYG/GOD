Overview
========

GOD stands for Govern, Observe, Direct. It is a local-first operator console for running an agent society, watching it step by step, asking residents questions, and injecting instructions into the next live step.

What GOD adds
-------------

GOD is not only a simulation framework:

- The setup wizard configures model settings, chooses built-in experiments, and publishes custom experiments.
- PixelReplay shows the town, timeline, residents, chat, and live controls in one browser UI.
- Agent Studio edits residents with map-aware identity, appearance, personality, routine, and review steps.
- Map Studio generates or uploads map drafts, calibrates anchors and collisions, validates them, and publishes map packages.
- ``scripts/god.sh`` owns the local startup lifecycle so a new contributor does not need to wire four services manually.

Runtime shape
-------------

The normal local stack is:

1. Operator opens the control room in the browser.
2. The React/Vite frontend calls the local FastAPI backend.
3. The backend reads the current experiment from ``.god/current_experiment.json`` and experiment files under ``agentsociety/quick_experiments``.
4. The live experiment runner talks to JiuwenClaw over a local WebSocket.
5. Pixel Town writes replay data so the frontend can scrub and inspect each step.

Primary repo areas
------------------

``scripts/god.sh``
   One-command setup, start, restart, status, browser opening, and cleanup.

``agentsociety/frontend``
   GOD control room, setup wizard, Agent Studio, Map Studio, and PixelReplay UI.

``agentsociety/packages/agentsociety2``
   Backend routers, live experiment runner, map package services, replay services, and selected extension points.

``agentsociety/quick_experiments``
   Built-in and user-published experiments.

``agentsociety/custom/maps``
   Pluggable map packages.

``jiuwenclaw``
   Integrated out-of-process agent runtime.
