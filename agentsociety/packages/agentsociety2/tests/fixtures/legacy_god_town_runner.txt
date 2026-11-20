#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -z "${AGENTSOCIETY_LLM_API_KEY:-}" ]]; then
  echo "AGENTSOCIETY_LLM_API_KEY is empty. Fill it in .env before running." >&2
  exit 1
fi

PYTHON_PATH="${PYTHON_PATH:-.venv/bin/python}"
RUN_DIR="quick_experiments/hypothesis_god_town/experiment_1/run"
rm -rf "$RUN_DIR"
mkdir -p "$RUN_DIR"

"$PYTHON_PATH" -m agentsociety2.society.cli \
  --config quick_experiments/hypothesis_god_town/experiment_1/init/init_config.json \
  --steps quick_experiments/hypothesis_god_town/experiment_1/init/steps.yaml \
  --run-dir "$RUN_DIR" \
  --experiment-id "god_town_1" \
  --log-level INFO \
  --log-file "$RUN_DIR/output.log"
