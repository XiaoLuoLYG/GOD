自定义实验
==========

主要的自定义实验路径是 setup wizard。

浏览器流程
----------

运行：

.. code-block:: bash

   ./scripts/god.sh configure

然后选择 **Create Custom Experiment**。向导会要求输入场景背景，生成草稿，允许编辑 agent 和 steps，最后发布为当前实验。

发布后的结构
------------

自定义实验会写到：

.. code-block:: text

   agentsociety/quick_experiments/hypothesis_<slug>/experiment_1/

重要文件：

``init/init_config.json``
   世界背景、地图模块、初始位置、agent profile、启用技能和 runtime 配置。

``init/steps.yaml``
   起始时间、步数和每步时长。

``README.md`` 和 ``README.zh-CN.md``
   给人看的实验说明。

``run.sh``
   可选的前台调试 runner。

当前实验指针
------------

点击 **Save and Launch** 后，setup 会写入 ``.god/current_experiment.json``。脚本随后启动该实验，而不是修改 ``.env`` 来决定实验。

手动编辑
--------

你可以直接编辑实验文件，但第一次起草建议用 setup wizard，因为它能保持 ID、地图选择和 runtime 配置一致。
