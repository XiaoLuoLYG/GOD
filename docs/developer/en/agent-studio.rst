Agent Studio
============

Agent Studio is the map-aware editor for residents.

Where it appears
----------------

Agent Studio can be opened from:

- Setup, while editing a generated draft.
- PixelReplay, while inspecting or extending the current experiment.
- The standalone Agent Builder route during focused editing.

What it edits
-------------

The Studio flow covers:

- Seed and role direction.
- Identity, biography, and profile metadata.
- Appearance and map-compatible sprite settings.
- Personality, routines, social ties, goals, needs, worries, and secrets.
- Review before saving.

Persistence path
----------------

For setup drafts, saved agents flow into the draft that will become ``init/init_config.json``. For replay-side edits, the frontend saves the experiment config and asks the backend to sync live agents when a live session is waiting.

Generated sprites
-----------------

Generated ``Generated_Agent_*.png`` files are local user output by default and should not be committed unless a later release explicitly changes that policy.

Related backend routes
----------------------

- ``POST /api/v1/god/setup/agent-studio/generate``
- ``POST /api/v1/god/setup/agent-studio/character``
- ``POST /api/v1/god/setup/agent-studio/complete-role-visuals``
- ``PUT /api/v1/experiment-configs/{hypothesis_id}/{experiment_id}/init``
