Map Packages
============

GOD discovers map packages from:

.. code-block:: text

   agentsociety/custom/maps/<map_id>/

Minimum package shape
---------------------

.. code-block:: text

   custom/maps/<map_id>/
     map.yaml
     README.md
     visuals/
       map.json
       map_assets/
       preview.png

``map.yaml`` is the manifest. ``visuals/map.json`` is the Tiled JSON map consumed by PixelReplay. The Tiled map must include a ``Collisions`` layer where ``0`` means walkable.

Validation
----------

.. code-block:: bash

   cd agentsociety
   uv run python scripts/validate_map_package.py custom/maps/<map_id>

More detail
-----------

The maintained contract lives in the repo docs:

- ``docs/MAP_PACKAGES.md``
- ``docs/MAP_PACKAGES.zh-CN.md``
