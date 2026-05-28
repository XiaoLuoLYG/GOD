实验 Contract
=============

实验目录位于：

.. code-block:: text

   agentsociety/quick_experiments/hypothesis_<hypothesis_id>/experiment_<experiment_id>/

必需文件
--------

``init/init_config.json``
   主要场景和 runtime 配置，包括实验背景、地图模块设置、agent profile、初始位置和启用技能/runtime metadata。

``init/steps.yaml``
   Step 计划，包括模拟开始时间、步数和 tick 设置。

推荐文件
--------

``README.md`` 和 ``README.zh-CN.md``
   给人看的实验说明。

``run.sh``
   前台调试 runner。

``OPERATOR_SCRIPT.md``
   可选的 live operator prompts，适合脚本化 demo。

当前实验状态
------------

Active 实验保存在：

.. code-block:: text

   .god/current_experiment.json

它记录 ``hypothesis_id``、``experiment_id`` 和 workspace path。启动时会读取该文件，除非命令显式设置 ``GOD_EXPERIMENT`` 或 ``GOD_EXPERIMENT_RUN``。

内置示例
--------

- ``agentsociety/quick_experiments/hypothesis_god_town/experiment_1/``
- ``agentsociety/quick_experiments/hypothesis_pku_trump_visit/experiment_1/``
