Map Studio
==========

Map Studio 用于创建和发布本地地图包。

流程
----

Map Studio 可以：

1. 根据 prompt 生成地图草稿。
2. 上传参考图作为草稿。
3. 配置图像生成。
4. 校准地点、anchor 和 collision 数据。
5. 校验地图包。
6. 发布到本地地图包目录。
7. 回到 setup，并选中新 ``map_id``。

生成包
------

生成地图默认是本地输出：

.. code-block:: text

   agentsociety/custom/generated_maps/

该路径被 Git 忽略。需要随 GOD 发布的精选地图应放在 ``agentsociety/custom/maps/<map_id>/``。

重要路由
--------

- ``POST /api/v1/god/map-studio/drafts``
- ``POST /api/v1/god/map-studio/drafts/upload``
- ``PATCH /api/v1/god/map-studio/drafts/{draft_id}``
- ``POST /api/v1/god/map-studio/drafts/{draft_id}/validate``
- ``POST /api/v1/god/map-studio/drafts/{draft_id}/publish``

校验
----

精选地图包：

.. code-block:: bash

   cd agentsociety
   uv run python scripts/validate_map_package.py custom/maps/<map_id>
