Commands
========

Run commands from the repo root.

.. list-table::
   :header-rows: 1

   * - Command
     - Use it when
   * - ``./scripts/god.sh menu``
     - You want an interactive menu.
   * - ``./scripts/god.sh setup``
     - You only want to install or check dependencies.
   * - ``./scripts/god.sh configure``
     - You want to reopen setup, switch the current experiment, or publish a custom experiment.
   * - ``./scripts/god.sh start``
     - You want the normal idempotent startup path.
   * - ``./scripts/god.sh restart``
     - You want to stop processes and start again without wiping replay state.
   * - ``./scripts/god.sh new-run``
     - You want to wipe the current experiment run and start a fresh live session.
   * - ``./scripts/god.sh stop``
     - You want to stop GOD and release ports.
   * - ``./scripts/god.sh status``
     - You want ports, URLs, model status, and current experiment details.
   * - ``./scripts/god.sh tail``
     - You want to follow GOD service logs.
   * - ``./scripts/god.sh open``
     - You want to open the control room and runtime UI again.

Useful examples
---------------

Start without opening browser tabs:

.. code-block:: bash

   GOD_OPEN_BROWSER=0 ./scripts/god.sh start

Run PKU Trump Visit as the current shell invocation:

.. code-block:: bash

   GOD_EXPERIMENT=pku_trump_visit GOD_EXPERIMENT_RUN=1 ./scripts/god.sh new-run

Follow logs while another terminal runs the UI:

.. code-block:: bash

   ./scripts/god.sh tail
