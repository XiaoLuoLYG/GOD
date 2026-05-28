Quickstart
==========

Start GOD
---------

.. code-block:: bash

   ./scripts/god.sh start

``start`` is idempotent: if a service is already running, the script reuses it where possible.

First-run flow
--------------

On a clean checkout, GOD will:

1. Create ``.env`` from ``.env.example``.
2. Install Python and Node dependencies.
3. Start the setup backend and control room.
4. Open the browser setup wizard at ``/setup``.
5. Ask for an OpenAI-compatible API key, base URL, and model name.
6. Let you choose GOD Town, PKU Trump Visit, or create a custom experiment.
7. Start the full stack for the selected current experiment.
8. Create a live session, prime the first step, and open PixelReplay.

Expected control room URL
-------------------------

For the default GOD Town experiment, the URL looks like:

.. code-block:: text

   http://127.0.0.1:5174/pixel-replay/god_town/1

For PKU Trump Visit:

.. code-block:: bash

   GOD_EXPERIMENT=pku_trump_visit GOD_EXPERIMENT_RUN=1 ./scripts/god.sh new-run

Then open:

.. code-block:: text

   http://127.0.0.1:5174/pixel-replay/pku_trump_visit/1

Verify
------

.. code-block:: bash

   ./scripts/god.sh status

Healthy output should show backend, control room, agent runtime, runtime web, runtime gateway, and runtime UI ports as up.

When to use ``new-run``
-----------------------

Use ``restart`` for process cleanup without wiping the current replay. Use ``new-run`` when you want a fresh live session and clean replay state for the current experiment.
