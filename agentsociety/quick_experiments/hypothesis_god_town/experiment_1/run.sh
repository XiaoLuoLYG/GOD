#!/usr/bin/env bash
set -euo pipefail

EXPERIMENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${BACKEND_ROOT:-$EXPERIMENT_DIR/../../..}"

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
command -v "$PYTHON_PATH" >/dev/null || { echo "Cannot find $PYTHON_PATH in $PWD" >&2; exit 1; }
HYPOTHESIS_NAME="$(basename "$(dirname "$EXPERIMENT_DIR")")"
EXPERIMENT_NAME="${EXPERIMENT_DIR##*/}"
RUN_DIR="$EXPERIMENT_DIR/run"
if [[ -d "$RUN_DIR" && ! -L "$RUN_DIR" ]]; then
  # Reset replay while keeping the local connection and resident sessions configured by GOD.
  find "$RUN_DIR" -mindepth 1 -maxdepth 1 ! -name .god-launch.json ! -name .god-session-prefix -exec rm -rf {} +
else
  rm -f "$RUN_DIR"
  mkdir -p "$RUN_DIR"
fi

"$PYTHON_PATH" -m agentsociety2.society.cli \
  --config "$EXPERIMENT_DIR/init/init_config.json" \
  --steps "$EXPERIMENT_DIR/init/steps.yaml" \
  --run-dir "$RUN_DIR" \
  --experiment-id "${HYPOTHESIS_NAME#hypothesis_}_${EXPERIMENT_NAME#experiment_}" \
  --log-level INFO \
  --log-file "$RUN_DIR/output.log"
