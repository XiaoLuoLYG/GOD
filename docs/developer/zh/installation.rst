安装
====

前置条件
--------

GOD 当前需要：

- macOS/Linux：Python 3.11 或更新版本、Node.js 和 ``npm``、``uv``，以及 ``screen``。
- Windows：PowerShell 5.1+ 和 ``winget``。PowerShell 入口会自动补齐缺失的 Git、Node.js LTS/npm 与 ``uv``；Python 运行时由 ``uv`` 管理。

macOS:

.. code-block:: bash

   brew install python node uv screen

克隆仓库
--------

.. code-block:: bash

   git clone https://github.com/XiaoLuoLYG/GOD.git
   cd GOD

这个仓库已经包含本地 GOD 栈需要的 AgentSociety 和 JiuwenClaw 集成目录。

通过 start 安装
---------------

推荐的安装路径就是启动路径：

.. code-block:: bash

   ./scripts/god.sh start

Windows PowerShell 使用：

.. code-block:: powershell

   .\scripts\god.cmd start

首次运行时，脚本会从 ``.env.example`` 创建 ``.env``，安装后端/runtime/前端依赖，打开 setup wizard，并等待你配置模型。

只安装依赖
----------

如果只想检查或安装依赖，不打开完整 live 栈：

.. code-block:: bash

   ./scripts/god.sh setup

如果依赖已经准备好，启动时想跳过依赖检查：

.. code-block:: bash

   GOD_SKIP_SETUP=1 ./scripts/god.sh start

本地文件边界
------------

不要提交本地运行状态：

- ``.env``
- ``.god/``
- ``.live/``
- ``agentsociety/quick_experiments/**/run*/``，仓库里已追踪的内置示例 run 目录除外
- 生成的 ``Generated_Agent_*.png`` sprite
- ``agentsociety/custom/generated_maps/`` 下的生成地图
