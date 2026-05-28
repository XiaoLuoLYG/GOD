命令
====

所有命令都在仓库根目录运行。

.. list-table::
   :header-rows: 1

   * - 命令
     - 何时使用
   * - ``./scripts/god.sh menu``
     - 打开交互菜单。
   * - ``./scripts/god.sh setup``
     - 只安装或检查依赖。
   * - ``./scripts/god.sh configure``
     - 重新打开 setup，切换当前实验，或发布自定义实验。
   * - ``./scripts/god.sh start``
     - 常规可重复启动路径。
   * - ``./scripts/god.sh restart``
     - 停止进程并重启，不清空 replay 状态。
   * - ``./scripts/god.sh new-run``
     - 清空当前实验 run，启动新的 live session。
   * - ``./scripts/god.sh stop``
     - 停止 GOD 并释放端口。
   * - ``./scripts/god.sh status``
     - 查看端口、URL、模型状态和当前实验。
   * - ``./scripts/god.sh tail``
     - 跟随 GOD 服务日志。
   * - ``./scripts/god.sh open``
     - 重新打开控制台和 runtime UI。

常用例子
--------

启动但不自动打开浏览器：

.. code-block:: bash

   GOD_OPEN_BROWSER=0 ./scripts/god.sh start

一次性运行 PKU Trump Visit：

.. code-block:: bash

   GOD_EXPERIMENT=pku_trump_visit GOD_EXPERIMENT_RUN=1 ./scripts/god.sh new-run

另一个终端里跟随日志：

.. code-block:: bash

   ./scripts/god.sh tail
