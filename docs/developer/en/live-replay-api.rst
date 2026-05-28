Live and Replay API
===================

GOD's browser UI uses a small set of backend API families.

Live experiment control
-----------------------

Base prefix:

.. code-block:: text

   /live-experiments/{hypothesis_id}/{experiment_id}

Important actions:

.. list-table::
   :header-rows: 1

   * - Method
     - Path
     - Purpose
   * - ``POST``
     - ``/start``
     - Start or attach a live experiment.
   * - ``GET``
     - ``/status``
     - Read live status.
   * - ``POST``
     - ``/run-step``
     - Advance one step.
   * - ``POST``
     - ``/intervene``
     - Inject instructions into the next step.
   * - ``POST``
     - ``/ask``
     - Ask one target, a group, or the whole town.
   * - ``POST``
     - ``/auto``
     - Toggle auto-run.
   * - ``POST``
     - ``/pause``
     - Pause auto-run.
   * - ``POST``
     - ``/stop``
     - Stop live execution.

Replay data
-----------

Base prefix:

.. code-block:: text

   /replay/{hypothesis_id}/{experiment_id}

Common reads:

- ``/info``
- ``/datasets``
- ``/map``
- ``/map/tiled``
- ``/map/assets/{tileset_index}``
- ``/map/preview``
- ``/map/characters/{character_name}``
- ``/map/location-assets/{location_id}``
- ``/timeline``

Setup and configuration
-----------------------

- ``/api/v1/god/setup/*`` owns setup wizard model config, draft generation, Agent Studio generation, publish, and start-request flow.
- ``/api/v1/experiment-configs/*`` owns experiment config read/write and agent import/apply flows.
- ``/api/v1/god/map-studio/*`` owns map draft generation, upload, validation, and publish.
