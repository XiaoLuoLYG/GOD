Agent Studio
============

Agent Studio 是地图感知的居民编辑器。

入口
----

Agent Studio 可以从这些位置打开：

- Setup 中编辑生成草稿。
- PixelReplay 中检查或扩展当前实验。
- 单独的 Agent Builder 路由。

编辑内容
--------

Studio 流程覆盖：

- seed 和角色方向。
- 身份、简介和 profile metadata。
- 外貌和地图兼容 sprite 设置。
- 性格、日程、社交关系、目标、需求、担忧和秘密。
- 保存前 review。

持久化路径
----------

Setup 草稿中的 agent 会进入即将发布的 ``init/init_config.json``。Replay 侧编辑会保存实验配置；如果 live session 正在等待，前端还会请求后端同步 live agents。

生成 sprite
-----------

生成的 ``Generated_Agent_*.png`` 默认是本地用户输出，不应提交，除非之后的 release 明确改变策略。

相关后端路由
------------

- ``POST /api/v1/god/setup/agent-studio/generate``
- ``POST /api/v1/god/setup/agent-studio/character``
- ``POST /api/v1/god/setup/agent-studio/complete-role-visuals``
- ``PUT /api/v1/experiment-configs/{hypothesis_id}/{experiment_id}/init``
