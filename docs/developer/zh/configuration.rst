配置
====

GOD 把机器配置和实验选择分开管理。

``.env``
--------

``.env`` 保存本地模型、端口和启动配置。它由 ``.env.example`` 创建，并被 Git 忽略。

必需模型配置：

.. list-table::
   :header-rows: 1

   * - 变量
     - 用途
     - 默认值
   * - ``GOD_LLM_API_KEY``
     - OpenAI 兼容 API key
     - 空
   * - ``GOD_LLM_API_BASE``
     - OpenAI 兼容 API base URL
     - ``https://api.openai.com/v1``
   * - ``GOD_LLM_MODEL``
     - GOD 和 runtime 使用的聊天模型
     - 空；模型运行前必填
   * - ``GOD_EMBEDDING_MODEL``
     - embedding 模型
     - ``text-embedding-3-large``

``.god/current_experiment.json``
--------------------------------

配置向导会把 active 实验写到这里。``start``、``open`` 和 ``new-run`` 读取这个文件，因此 ``.env`` 不会意外决定当前地图或剧本。

显式覆盖
--------

一次性运行可以用环境变量覆盖当前实验：

.. code-block:: bash

   GOD_EXPERIMENT=pku_trump_visit GOD_EXPERIMENT_RUN=1 ./scripts/god.sh new-run

常用端口
--------

.. list-table::
   :header-rows: 1

   * - 变量
     - 默认值
     - 服务
   * - ``GOD_BACKEND_PORT``
     - ``8001``
     - FastAPI 后端
   * - ``GOD_FRONTEND_PORT``
     - ``5174``
     - GOD 控制台
   * - ``RUNTIME_AGENT_PORT``
     - ``19092``
     - JiuwenClaw agent WebSocket
   * - ``RUNTIME_WEB_PORT``
     - ``20000``
     - JiuwenClaw web 服务
   * - ``RUNTIME_GATEWAY_PORT``
     - ``20001``
     - JiuwenClaw gateway
   * - ``RUNTIME_UI_PORT``
     - ``6173``
     - Runtime UI

浏览器打开
----------

禁止自动打开浏览器：

.. code-block:: bash

   GOD_OPEN_BROWSER=0 ./scripts/god.sh start
