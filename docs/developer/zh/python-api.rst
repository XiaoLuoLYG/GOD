精选 Python API
===============

本页列出扩展 GOD 时相对稳定、值得阅读的源码位置。它不会发布完整上游 AgentSociety API。

后端路由
--------

- ``agentsociety2.backend.routers.god_setup``
- ``agentsociety2.backend.routers.live_experiments``
- ``agentsociety2.backend.routers.replay``
- ``agentsociety2.backend.routers.experiment_configs``
- ``agentsociety2.backend.routers.map_studio``
- ``agentsociety2.backend.routers.agent_skills``

地图服务
--------

- ``agentsociety2.backend.services.map_packages``
- ``agentsociety2.backend.services.map_generation``

Replay 服务
-----------

- ``agentsociety2.backend.services.replay_catalog``
- ``agentsociety2.storage.replay_writer``

自定义 agent/runtime 路径
-------------------------

- ``agentsociety2.backend.services.custom``
- ``agentsociety2.agent``
- ``agentsociety/custom/agents/``

以后增加公开 API 文档时，优先文档化 GOD setup、Agent Studio、Map Studio 和 PixelReplay 使用到的扩展点，再考虑暴露更广泛的内部模块。
