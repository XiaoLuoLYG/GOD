环境变量
========

用户可见变量
------------

.. list-table::
   :header-rows: 1

   * - 变量
     - 默认值
     - 说明
   * - ``GOD_LLM_API_KEY``
     - 空
     - 模型运行必需。
   * - ``GOD_LLM_API_BASE``
     - ``https://api.openai.com/v1``
     - 任意 OpenAI 兼容 endpoint。
   * - ``GOD_LLM_MODEL``
     - 空
     - 必填主聊天模型。示例：``qwen-plus``、``gpt-4o-mini``。
   * - ``GOD_LLM_NANO_MODEL``
     - ``GOD_LLM_MODEL``
     - 可选高频小模型槽位。
   * - ``GOD_EMBEDDING_API_KEY``
     - ``GOD_LLM_API_KEY``
     - 可选覆盖。
   * - ``GOD_EMBEDDING_API_BASE``
     - ``GOD_LLM_API_BASE``
     - 可选覆盖。
   * - ``GOD_EMBEDDING_MODEL``
     - ``text-embedding-3-large``
     - embedding 模型。
   * - ``GOD_BACKEND_HOST``
     - ``127.0.0.1``
     - 后端绑定 host。
   * - ``GOD_BACKEND_PORT``
     - ``8001``
     - 后端端口。
   * - ``GOD_FRONTEND_PORT``
     - ``5174``
     - 控制台端口。
   * - ``GOD_OPEN_BROWSER``
     - ``1``
     - 设为 ``0`` 可禁止自动打开浏览器。
   * - ``GOD_SKIP_SETUP``
     - ``0``
     - 设为 ``1`` 可跳过依赖检查。
   * - ``GOD_PRIME_FIRST_STEP``
     - ``1``
     - 设为 ``0`` 可跳过自动预跑第一步。

高级 runtime 变量
-----------------

Runtime 端口可以通过 ``RUNTIME_AGENT_PORT``、``RUNTIME_WEB_PORT``、``RUNTIME_GATEWAY_PORT`` 和 ``RUNTIME_UI_PORT`` 修改。默认 runtime instance 名是 ``RUNTIME_INSTANCE=god-town``。

兼容旧变量
----------

``scripts/god.sh`` 会接受旧的 ``AGENTSOCIETY_*`` 和 ``JIUWENCLAW_*`` 名称，将其映射为 ``GOD_*`` 值，并导出集成服务需要的内部变量。
