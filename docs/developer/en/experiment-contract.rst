Experiment Contract
===================

Experiment folders live under:

.. code-block:: text

   agentsociety/quick_experiments/hypothesis_<hypothesis_id>/experiment_<experiment_id>/

Required files
--------------

``init/init_config.json``
   Main scenario and runtime configuration. It includes experiment context, map module settings, agent profiles, initial locations, and enabled skill/runtime metadata.

``init/steps.yaml``
   Step plan with simulation start time, step count, and tick settings.

Recommended files
-----------------

``README.md`` and ``README.zh-CN.md``
   Human-facing experiment explanation.

``run.sh``
   Foreground debug runner.

``OPERATOR_SCRIPT.md``
   Optional live-operator prompts for scripted demos.

Current experiment state
------------------------

The active experiment is stored in:

.. code-block:: text

   .god/current_experiment.json

It records the selected ``hypothesis_id``, ``experiment_id``, and workspace path. Startup reads this file unless the shell command explicitly sets ``GOD_EXPERIMENT`` or ``GOD_EXPERIMENT_RUN``.

Built-in examples
-----------------

- ``agentsociety/quick_experiments/hypothesis_god_town/experiment_1/``
- ``agentsociety/quick_experiments/hypothesis_pku_trump_visit/experiment_1/``
