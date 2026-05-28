参与贡献
========

从常规本地路径开始：

.. code-block:: bash

   git clone https://github.com/XiaoLuoLYG/GOD.git
   cd GOD
   ./scripts/god.sh start

提交 PR 前
----------

运行与改动相关的检查：

.. code-block:: bash

   git diff --check
   npm run build --prefix agentsociety/frontend
   cd agentsociety
   uv run pytest -q packages/agentsociety2/tests/test_god_setup_router.py \
     packages/agentsociety2/tests/test_map_packages.py \
     packages/agentsociety2/tests/test_pixel_town_social_env.py

地图包改动：

.. code-block:: bash

   cd agentsociety
   uv run python scripts/validate_map_package.py custom/maps/<map_id>

产物边界
--------

不要把运行数据提交到公开 PR。不要 stage ``.god/``、``.live/``、``.superpowers/``、``.DS_Store``、生成地图输出或生成测试 sprite。

更多细节
--------

见仓库根目录的 ``CONTRIBUTING.md`` 和 ``CONTRIBUTING.zh-CN.md``。
