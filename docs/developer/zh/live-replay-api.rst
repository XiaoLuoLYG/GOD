Live 和 Replay API
==================

GOD 浏览器 UI 使用几组后端 API。

Live experiment 控制
--------------------

基础 prefix：

.. code-block:: text

   /live-experiments/{hypothesis_id}/{experiment_id}

重要动作：

.. list-table::
   :header-rows: 1

   * - 方法
     - 路径
     - 用途
   * - ``POST``
     - ``/start``
     - 启动或附着 live experiment。
   * - ``GET``
     - ``/status``
     - 读取 live 状态。
   * - ``POST``
     - ``/run-step``
     - 推进一步。
   * - ``POST``
     - ``/intervene``
     - 向下一步注入指令。
   * - ``POST``
     - ``/ask``
     - 向目标、群组或全镇提问。
   * - ``POST``
     - ``/auto``
     - 切换自动运行。
   * - ``POST``
     - ``/pause``
     - 暂停自动运行。
   * - ``POST``
     - ``/stop``
     - 停止 live 执行。

Replay 数据
-----------

基础 prefix：

.. code-block:: text

   /replay/{hypothesis_id}/{experiment_id}

常见读取：

- ``/info``
- ``/datasets``
- ``/map``
- ``/map/tiled``
- ``/map/assets/{tileset_index}``
- ``/map/preview``
- ``/map/characters/{character_name}``
- ``/map/location-assets/{location_id}``
- ``/timeline``

Setup 和配置
------------

- ``/api/v1/god/setup/*`` 管理 setup wizard 的模型配置、草稿生成、Agent Studio 生成、发布和 start-request。
- ``/api/v1/experiment-configs/*`` 管理实验配置读写和 agent import/apply。
- ``/api/v1/god/map-studio/*`` 管理地图草稿生成、上传、校验和发布。
