概览
====

GOD 是 Govern, Observe, Direct 的缩写。它是一个 local-first 的 agent society 操作台：你可以运行一个小镇，逐步观察它，向居民提问，并把指令注入到下一步 live 执行里。

GOD 增加了什么
---------------

GOD 不只是模拟框架：

- Setup Wizard 负责模型配置、内置实验选择和自定义实验发布。
- PixelReplay 在一个浏览器界面里显示地图、时间线、居民、聊天和 live 控制。
- Agent Studio 用地图感知的流程编辑居民身份、外貌、性格、日程和 review。
- Map Studio 生成或上传地图草稿，校准 anchor 和 collision，校验后发布地图包。
- ``scripts/god.sh`` 统一本地启动生命周期，新贡献者不用手动串四个服务。

运行结构
--------

常规本地栈是：

1. 操作者在浏览器打开控制台。
2. React/Vite 前端调用本地 FastAPI 后端。
3. 后端从 ``.god/current_experiment.json`` 和 ``agentsociety/quick_experiments`` 读取当前实验。
4. live experiment runner 通过本地 WebSocket 连接 JiuwenClaw。
5. Pixel Town 写入 replay 数据，前端可以按 step 拖动和检查。

主要目录
--------

``scripts/god.sh``
   一键 setup、start、restart、status、打开浏览器和清理。

``agentsociety/frontend``
   GOD 控制台、配置向导、Agent Studio、Map Studio 和 PixelReplay UI。

``agentsociety/packages/agentsociety2``
   后端路由、live runner、地图包服务、replay 服务和扩展点。

``agentsociety/quick_experiments``
   内置实验和用户发布的实验。

``agentsociety/custom/maps``
   可插拔地图包。

``jiuwenclaw``
   集成的 out-of-process agent runtime。
