Selected Python API
===================

This page names source files that are stable enough to inspect when extending GOD. It does not attempt to publish the whole upstream AgentSociety API.

Backend routers
---------------

- ``agentsociety2.backend.routers.god_setup``
- ``agentsociety2.backend.routers.live_experiments``
- ``agentsociety2.backend.routers.replay``
- ``agentsociety2.backend.routers.experiment_configs``
- ``agentsociety2.backend.routers.map_studio``
- ``agentsociety2.backend.routers.agent_skills``

Map services
------------

- ``agentsociety2.backend.services.map_packages``
- ``agentsociety2.backend.services.map_generation``

Replay services
---------------

- ``agentsociety2.backend.services.replay_catalog``
- ``agentsociety2.storage.replay_writer``

Custom agent/runtime paths
--------------------------

- ``agentsociety2.backend.services.custom``
- ``agentsociety2.agent``
- ``agentsociety/custom/agents/``

When adding public API documentation later, prefer documenting extension points used by GOD setup, Agent Studio, Map Studio, and PixelReplay before exposing broad internal modules.
