Custom Experiments
==================

The primary custom-experiment path is the setup wizard.

Browser flow
------------

Run:

.. code-block:: bash

   ./scripts/god.sh configure

Then choose **Create Custom Experiment**. The wizard asks for scenario context, generates a draft, lets you edit agents and steps, and publishes the result as the current experiment.

Published shape
---------------

Custom experiments are written under:

.. code-block:: text

   agentsociety/quick_experiments/hypothesis_<slug>/experiment_1/

The important files are:

``init/init_config.json``
   World context, map module, initial locations, agent profiles, enabled skills, and runtime-facing config.

``init/steps.yaml``
   Start timestamp, step count, and tick duration.

``README.md`` and ``README.zh-CN.md``
   Human explanation for the experiment.

``run.sh``
   Optional foreground runner for debugging.

Current experiment pointer
--------------------------

When you click **Save and Launch**, setup writes ``.god/current_experiment.json``. The shell script then starts that experiment without changing ``.env``.

Manual editing
--------------

You can edit experiment files directly, but the setup wizard is safer for first drafts because it keeps IDs, map selection, and runtime config aligned.
