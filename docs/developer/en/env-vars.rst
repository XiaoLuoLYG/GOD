Environment Variables
=====================

User-facing variables
---------------------

.. list-table::
   :header-rows: 1

   * - Variable
     - Default
     - Notes
   * - ``GOD_LLM_API_KEY``
     - empty
     - Required for model-backed runs.
   * - ``GOD_LLM_API_BASE``
     - ``https://api.openai.com/v1``
     - Any OpenAI-compatible endpoint.
   * - ``GOD_LLM_MODEL``
     - empty
     - Required main chat model. Examples: ``qwen-plus``, ``gpt-4o-mini``.
   * - ``GOD_LLM_NANO_MODEL``
     - ``GOD_LLM_MODEL``
     - Optional high-frequency smaller model slot.
   * - ``GOD_EMBEDDING_API_KEY``
     - ``GOD_LLM_API_KEY``
     - Optional override.
   * - ``GOD_EMBEDDING_API_BASE``
     - ``GOD_LLM_API_BASE``
     - Optional override.
   * - ``GOD_EMBEDDING_MODEL``
     - ``text-embedding-3-large``
     - Embedding model.
   * - ``GOD_BACKEND_HOST``
     - ``127.0.0.1``
     - Backend bind host.
   * - ``GOD_BACKEND_PORT``
     - ``8001``
     - Backend port.
   * - ``GOD_FRONTEND_PORT``
     - ``5174``
     - Control room port.
   * - ``GOD_OPEN_BROWSER``
     - ``1``
     - Set ``0`` to suppress automatic browser opening.
   * - ``GOD_SKIP_SETUP``
     - ``0``
     - Set ``1`` to skip dependency checks.
   * - ``GOD_PRIME_FIRST_STEP``
     - ``1``
     - Set ``0`` to skip automatic first-step priming.

Advanced runtime variables
--------------------------

Runtime ports can be changed with ``RUNTIME_AGENT_PORT``, ``RUNTIME_WEB_PORT``, ``RUNTIME_GATEWAY_PORT``, and ``RUNTIME_UI_PORT``. The default runtime instance name is ``RUNTIME_INSTANCE=god-town``.

Legacy compatibility
--------------------

``scripts/god.sh`` accepts older ``AGENTSOCIETY_*`` and ``JIUWENCLAW_*`` names, maps them into ``GOD_*`` values, and exports the internal names needed by the integrated services.
