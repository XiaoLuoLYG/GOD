Configuration
=============

GOD separates machine settings from experiment selection.

``.env``
--------

``.env`` stores local model, port, and startup settings. It is created from ``.env.example`` and ignored by Git.

Required model settings:

.. list-table::
   :header-rows: 1

   * - Variable
     - Purpose
     - Default
   * - ``GOD_LLM_API_KEY``
     - OpenAI-compatible API key
     - empty
   * - ``GOD_LLM_API_BASE``
     - OpenAI-compatible API base URL
     - ``https://api.openai.com/v1``
   * - ``GOD_LLM_MODEL``
     - Chat model used by GOD and the runtime
     - empty; required before model-backed runs
   * - ``GOD_EMBEDDING_MODEL``
     - Embedding model
     - ``text-embedding-3-large``

``.god/current_experiment.json``
--------------------------------

The setup wizard writes the active experiment here. ``start``, ``open``, and ``new-run`` read this file so ``.env`` does not accidentally decide the current map or scenario.

Explicit overrides
------------------

For one-off runs, these environment variables override current-experiment state:

.. code-block:: bash

   GOD_EXPERIMENT=pku_trump_visit GOD_EXPERIMENT_RUN=1 ./scripts/god.sh new-run

Common ports
------------

.. list-table::
   :header-rows: 1

   * - Variable
     - Default
     - Service
   * - ``GOD_BACKEND_PORT``
     - ``8001``
     - FastAPI backend
   * - ``GOD_FRONTEND_PORT``
     - ``5174``
     - GOD control room
   * - ``RUNTIME_AGENT_PORT``
     - ``19092``
     - JiuwenClaw agent WebSocket
   * - ``RUNTIME_WEB_PORT``
     - ``20000``
     - JiuwenClaw web service
   * - ``RUNTIME_GATEWAY_PORT``
     - ``20001``
     - JiuwenClaw gateway
   * - ``RUNTIME_UI_PORT``
     - ``6173``
     - Runtime UI

Browser opening
---------------

Disable automatic browser opening:

.. code-block:: bash

   GOD_OPEN_BROWSER=0 ./scripts/god.sh start
