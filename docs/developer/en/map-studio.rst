Map Studio
==========

Map Studio creates and publishes local map packages.

Flow
----

Map Studio can:

1. Generate a draft map from a prompt.
2. Upload a reference image as a draft.
3. Configure image generation.
4. Calibrate locations, anchors, and collision data.
5. Validate the package.
6. Publish the map into the local map package directory.
7. Return to setup with the new ``map_id`` selected.

Generated packages
------------------

Generated packages are local output under:

.. code-block:: text

   agentsociety/custom/generated_maps/

That path is ignored by Git. Curated maps that should ship with GOD belong under ``agentsociety/custom/maps/<map_id>/``.

Important routes
----------------

- ``POST /api/v1/god/map-studio/drafts``
- ``POST /api/v1/god/map-studio/drafts/upload``
- ``PATCH /api/v1/god/map-studio/drafts/{draft_id}``
- ``POST /api/v1/god/map-studio/drafts/{draft_id}/validate``
- ``POST /api/v1/god/map-studio/drafts/{draft_id}/publish``

Validation
----------

For a curated map package:

.. code-block:: bash

   cd agentsociety
   uv run python scripts/validate_map_package.py custom/maps/<map_id>
