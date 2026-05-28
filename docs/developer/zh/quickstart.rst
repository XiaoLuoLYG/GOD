快速开始
========

启动 GOD
--------

.. code-block:: bash

   ./scripts/god.sh start

``start`` 是可重复执行的：如果服务已经运行，脚本会尽量复用已有服务。

首次运行流程
------------

在干净 checkout 里，GOD 会：

1. 从 ``.env.example`` 创建 ``.env``。
2. 安装 Python 和 Node 依赖。
3. 启动 setup 后端和控制台。
4. 在浏览器打开 ``/setup``。
5. 要求填写 OpenAI 兼容 API key、base URL 和模型名。
6. 选择 GOD Town、PKU Trump Visit，或创建自定义实验。
7. 为当前实验启动完整服务栈。
8. 创建 live session，预跑第一步，并打开 PixelReplay。

预期控制台 URL
--------------

默认 GOD Town 的 URL 类似：

.. code-block:: text

   http://127.0.0.1:5174/pixel-replay/god_town/1

PKU Trump Visit:

.. code-block:: bash

   GOD_EXPERIMENT=pku_trump_visit GOD_EXPERIMENT_RUN=1 ./scripts/god.sh new-run

然后打开：

.. code-block:: text

   http://127.0.0.1:5174/pixel-replay/pku_trump_visit/1

验证
----

.. code-block:: bash

   ./scripts/god.sh status

健康状态应该显示 backend、control room、agent runtime、runtime web、runtime gateway 和 runtime UI 端口均为 up。

什么时候用 ``new-run``
----------------------

``restart`` 用于清理进程但不清空当前 replay。``new-run`` 用于为当前实验开一个全新的 live session 和干净 replay。
