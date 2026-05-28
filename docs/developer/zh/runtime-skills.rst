Runtime Skills
==============

GOD 使用 JiuwenClaw 作为 out-of-process agent runtime，并把 AgentSociety 作为产品层 skill 执行路径。

Runtime bridge
--------------

默认本地 runtime instance 是 ``god-town``。启动时会把 GOD 模型配置映射到 AgentSociety 和 JiuwenClaw 环境变量，然后在本地端口启动 JiuwenClaw 服务。

相关默认值：

- Agent WebSocket: ``RUNTIME_AGENT_PORT=19092``
- Runtime web: ``RUNTIME_WEB_PORT=20000``
- Runtime gateway: ``RUNTIME_GATEWAY_PORT=20001``
- Runtime UI: ``RUNTIME_UI_PORT=6173``

Skill 包
--------

自定义 agent skills 通过 ``/api/v1/agent-skills`` 下的后端路由管理。Setup 和 Agent Studio 会让 skill runtime metadata 与实验配置同步，因此生成、导入和应用之后，agent 使用同一条 runtime 路径。

查看位置
--------

- ``agentsociety/packages/agentsociety2/agentsociety2/backend/routers/agent_skills.py``
- ``agentsociety/packages/agentsociety2/agentsociety2/backend/routers/god_setup.py``
- ``agentsociety/packages/agentsociety2/agentsociety2/backend/routers/experiment_configs.py``
- ``jiuwenclaw/``
