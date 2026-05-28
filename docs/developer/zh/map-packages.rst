地图包
======

GOD 会从这里发现地图包：

.. code-block:: text

   agentsociety/custom/maps/<map_id>/

最小结构
--------

.. code-block:: text

   custom/maps/<map_id>/
     map.yaml
     README.md
     visuals/
       map.json
       map_assets/
       preview.png

``map.yaml`` 是 manifest。``visuals/map.json`` 是 PixelReplay 使用的 Tiled JSON 地图。Tiled map 必须包含 ``Collisions`` layer，其中 ``0`` 表示可行走。

校验
----

.. code-block:: bash

   cd agentsociety
   uv run python scripts/validate_map_package.py custom/maps/<map_id>

更多细节
--------

维护中的 contract 在仓库文档里：

- ``docs/MAP_PACKAGES.md``
- ``docs/MAP_PACKAGES.zh-CN.md``
