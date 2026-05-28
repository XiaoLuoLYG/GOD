Installation
============

Prerequisites
-------------

GOD currently expects:

- Python 3.11 or newer.
- Node.js and ``npm``.
- ``uv`` for Python dependency management.
- ``screen`` on macOS/Linux so local services can stay attached cleanly.

On macOS:

.. code-block:: bash

   brew install python node uv screen

Clone
-----

.. code-block:: bash

   git clone https://github.com/XiaoLuoLYG/GOD.git
   cd GOD

The repo contains the integrated AgentSociety and JiuwenClaw checkouts needed by the local GOD stack.

Install by starting
-------------------

The recommended install path is the same as the start path:

.. code-block:: bash

   ./scripts/god.sh start

On first run, the script creates ``.env`` from ``.env.example``, installs backend/runtime/frontend dependencies, opens the setup wizard, and waits for model configuration.

Install only
------------

To check or install dependencies without opening the full live stack:

.. code-block:: bash

   ./scripts/god.sh setup

If you already know the dependencies are ready and want to skip setup checks during startup:

.. code-block:: bash

   GOD_SKIP_SETUP=1 ./scripts/god.sh start

Local-only files
----------------

Do not commit local runtime state:

- ``.env``
- ``.god/``
- ``.live/``
- ``agentsociety/quick_experiments/**/run*/`` except the tracked built-in sample run folders already in the repo
- generated ``Generated_Agent_*.png`` sprite files
- generated map packages under ``agentsociety/custom/generated_maps/``
