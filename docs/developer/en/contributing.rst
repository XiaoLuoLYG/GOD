Contributing
============

Start from the normal local path:

.. code-block:: bash

   git clone https://github.com/XiaoLuoLYG/GOD.git
   cd GOD
   ./scripts/god.sh start

Before a PR
-----------

Run the checks relevant to your change:

.. code-block:: bash

   git diff --check
   npm run build --prefix agentsociety/frontend
   cd agentsociety
   uv run pytest -q packages/agentsociety2/tests/test_god_setup_router.py \
     packages/agentsociety2/tests/test_map_packages.py \
     packages/agentsociety2/tests/test_pixel_town_social_env.py

For map package changes:

.. code-block:: bash

   cd agentsociety
   uv run python scripts/validate_map_package.py custom/maps/<map_id>

Artifact hygiene
----------------

Keep runtime data out of public PRs. Do not stage ``.god/``, ``.live/``, ``.superpowers/``, ``.DS_Store``, generated map output, or generated test sprites.

More detail
-----------

See ``CONTRIBUTING.md`` and ``CONTRIBUTING.zh-CN.md`` at the repo root.
