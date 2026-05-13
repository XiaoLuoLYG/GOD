#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${GOD_ENV_FILE:-$ROOT_DIR/.env}"

# Internal monorepo layout. Hidden from the outward-facing config surface.
BACKEND_ROOT="${BACKEND_ROOT:-$ROOT_DIR/agentsociety}"
RUNTIME_ROOT="${RUNTIME_ROOT:-$ROOT_DIR/jiuwenclaw}"
LIVE_WORKSPACE_PATH="${LIVE_WORKSPACE_PATH:-$BACKEND_ROOT/quick_experiments}"

# State dirs.
STATE_DIR="$ROOT_DIR/.god"
LOG_DIR="$STATE_DIR/logs"
PID_DIR="$STATE_DIR/pids"
RUN_DIR="$STATE_DIR/run"
mkdir -p "$LOG_DIR" "$PID_DIR" "$RUN_DIR"

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"
RUNTIME_PID_FILE="$PID_DIR/runtime.pid"
CURRENT_EXPERIMENT_FILE="$STATE_DIR/current_experiment.json"
START_REQUEST_FILE="$RUN_DIR/start-request.json"

RUNTIME_INSTANCE="${RUNTIME_INSTANCE:-god-town}"
RUNTIME_MODE="${RUNTIME_MODE:-dev}"
RUNTIME_LANGUAGE="${RUNTIME_LANGUAGE:-zh}"
RUNTIME_LEGACY_INSTANCES="${RUNTIME_LEGACY_INSTANCES:-jiuwenclaw-town jiuwenclaw-town-native-skill}"
RUNTIME_AGENT_PORT="${RUNTIME_AGENT_PORT:-19092}"
RUNTIME_WEB_PORT="${RUNTIME_WEB_PORT:-20000}"
RUNTIME_GATEWAY_PORT="${RUNTIME_GATEWAY_PORT:-20001}"
RUNTIME_UI_PORT="${RUNTIME_UI_PORT:-6173}"
GOD_EXTRA_STOP_PORTS="${GOD_EXTRA_STOP_PORTS:-20092 21000 21001 7173}"

# Default user-facing config (mirrors .env.example).
GOD_EXPERIMENT="${GOD_EXPERIMENT:-god_town}"
GOD_EXPERIMENT_RUN="${GOD_EXPERIMENT_RUN:-1}"
GOD_BACKEND_HOST="${GOD_BACKEND_HOST:-127.0.0.1}"
GOD_BACKEND_PORT="${GOD_BACKEND_PORT:-8001}"
GOD_FRONTEND_PORT="${GOD_FRONTEND_PORT:-5174}"
GOD_LIVE_STEP_TIMEOUT="${GOD_LIVE_STEP_TIMEOUT:-${AGENTSOCIETY_LIVE_STEP_TIMEOUT:-900}}"

backend_url=""
frontend_url=""
runtime_ui_url=""

log() {
  printf '[GOD] %s\n' "$*"
}

die() {
  printf '[GOD] error: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<EOF
Usage: ./scripts/god.sh [menu|setup|configure|start|restart|new-run|stop|status|tail|open]

menu      Interactive menu.
setup     Install or check Python and Node dependencies only.
configure Open the experiment setup wizard and wait for a new experiment request.
start     Start GOD (idempotent; reuses running services) and open frontend pages.
restart   Stop everything cleanly, then start.
new-run   Stop, wipe the current run, then start a fresh session.
stop      Stop GOD and release its ports.
status    Print URLs, ports, and model status.
tail      Follow GOD service logs.
open      Open the GOD frontend pages in the default browser.
EOF
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

shell_quote() {
  printf '%q' "$1"
}

screen_list() {
  screen -ls 2>/dev/null || true
}

require_base_tools() {
  for tool in uv npm curl lsof python3; do
    command_exists "$tool" || die "Required command not found: $tool"
  done
}

refresh_derived() {
  backend_url="http://$GOD_BACKEND_HOST:$GOD_BACKEND_PORT"
  frontend_url="http://127.0.0.1:$GOD_FRONTEND_PORT"
  runtime_ui_url="http://localhost:$RUNTIME_UI_PORT"
}

load_current_experiment() {
  [[ -f "$CURRENT_EXPERIMENT_FILE" ]] || return 0
  local exports
  exports="$(
    python3 - "$CURRENT_EXPERIMENT_FILE" <<'PY'
import json
import shlex
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)
if not isinstance(data, dict):
    raise SystemExit(0)

mapping = {
    "GOD_EXPERIMENT": data.get("hypothesis_id"),
    "GOD_EXPERIMENT_RUN": data.get("experiment_id"),
    "LIVE_WORKSPACE_PATH": data.get("workspace_path"),
}
for key, value in mapping.items():
    if value:
        print(f"{key}={shlex.quote(str(value))}")
PY
  )"
  [[ -n "$exports" ]] || return 0
  eval "$exports"
  export GOD_EXPERIMENT GOD_EXPERIMENT_RUN LIVE_WORKSPACE_PATH
}

load_env() {
  if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi
  export_internal_env
  load_current_experiment
  export_internal_env
  refresh_derived
}

# Map outward-facing GOD_* config to the internal env names the backend and
# runtime read directly. Kept in one place so the rest of the script and the
# user only ever sees GOD_* names. Legacy variable names from previous
# installations are accepted silently and migrated forward.
export_internal_env() {
  GOD_LLM_API_KEY="${GOD_LLM_API_KEY:-${AGENTSOCIETY_LLM_API_KEY:-${JIUWENCLAW_API_KEY:-}}}"
  GOD_LLM_API_BASE="${GOD_LLM_API_BASE:-${AGENTSOCIETY_LLM_API_BASE:-${JIUWENCLAW_API_BASE:-}}}"
  GOD_LLM_MODEL="${GOD_LLM_MODEL:-${AGENTSOCIETY_LLM_MODEL:-${JIUWENCLAW_MODEL:-}}}"
  GOD_EMBEDDING_API_KEY="${GOD_EMBEDDING_API_KEY:-${AGENTSOCIETY_EMBEDDING_API_KEY:-${JIUWENCLAW_EMBED_API_KEY:-}}}"
  GOD_EMBEDDING_API_BASE="${GOD_EMBEDDING_API_BASE:-${AGENTSOCIETY_EMBEDDING_API_BASE:-${JIUWENCLAW_EMBED_API_BASE:-}}}"
  GOD_EMBEDDING_MODEL="${GOD_EMBEDDING_MODEL:-${AGENTSOCIETY_EMBEDDING_MODEL:-${JIUWENCLAW_EMBED_MODEL:-}}}"
  GOD_BACKEND_PORT="${GOD_BACKEND_PORT:-${BACKEND_PORT:-8001}}"
  GOD_FRONTEND_PORT="${GOD_FRONTEND_PORT:-${AGENTSOCIETY_FRONTEND_PORT:-5174}}"
  GOD_LIVE_STEP_TIMEOUT="${GOD_LIVE_STEP_TIMEOUT:-${AGENTSOCIETY_LIVE_STEP_TIMEOUT:-900}}"
  GOD_EXPERIMENT="${GOD_EXPERIMENT:-${GOD_HYPOTHESIS_ID:-god_town}}"
  GOD_EXPERIMENT_RUN="${GOD_EXPERIMENT_RUN:-${GOD_EXPERIMENT_ID:-1}}"

  local llm_key="${GOD_LLM_API_KEY:-}"
  local llm_base="${GOD_LLM_API_BASE:-https://api.openai.com/v1}"
  local llm_model="${GOD_LLM_MODEL:-gpt-5.4}"
  local nano_model="${GOD_LLM_NANO_MODEL:-${llm_model%.*}.*-nano}"
  # Friendly default for the nano slot when GOD_LLM_MODEL is the canonical "gpt-5.4".
  if [[ "$llm_model" == "gpt-5.4" ]]; then
    nano_model="${GOD_LLM_NANO_MODEL:-gpt-5.4-nano}"
  fi
  local embed_key="${GOD_EMBEDDING_API_KEY:-$llm_key}"
  local embed_base="${GOD_EMBEDDING_API_BASE:-$llm_base}"
  local embed_model="${GOD_EMBEDDING_MODEL:-text-embedding-3-large}"

  export AGENTSOCIETY_LLM_API_KEY="$llm_key"
  export AGENTSOCIETY_LLM_API_BASE="$llm_base"
  export AGENTSOCIETY_LLM_MODEL="$llm_model"
  export AGENTSOCIETY_NANO_LLM_MODEL="$nano_model"
  export AGENTSOCIETY_EMBEDDING_API_KEY="$embed_key"
  export AGENTSOCIETY_EMBEDDING_API_BASE="$embed_base"
  export AGENTSOCIETY_EMBEDDING_MODEL="$embed_model"

  export JIUWENCLAW_API_KEY="$llm_key"
  export JIUWENCLAW_API_BASE="$llm_base"
  export JIUWENCLAW_MODEL="$llm_model"
  export JIUWENCLAW_MODEL_PROVIDER="${JIUWENCLAW_MODEL_PROVIDER:-OpenAI}"
  export JIUWENCLAW_EMBED_API_KEY="$embed_key"
  export JIUWENCLAW_EMBED_API_BASE="$embed_base"
  export JIUWENCLAW_EMBED_MODEL="$embed_model"

  export BACKEND_HOST="$GOD_BACKEND_HOST"
  export BACKEND_PORT="$GOD_BACKEND_PORT"
  export AGENTSOCIETY_FRONTEND_PORT="$GOD_FRONTEND_PORT"

  export GOD_HYPOTHESIS_ID="$GOD_EXPERIMENT"
  export GOD_EXPERIMENT_ID="$GOD_EXPERIMENT_RUN"
}

set_env_value() {
  local key="$1"
  local value="$2"
  python3 - "$ENV_FILE" "$key" "$value" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
out = []
seen = False
for line in lines:
    if line.startswith(f"{key}="):
        out.append(f"{key}={value}")
        seen = True
    else:
        out.append(line)
if not seen:
    if out and out[-1] != "":
        out.append("")
    out.append(f"{key}={value}")
path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY
  export "$key=$value"
}

set_env_values_in_file() {
  local file="$1"
  shift
  python3 - "$file" "$@" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1]).expanduser()
items = list(zip(sys.argv[2::2], sys.argv[3::2]))
path.parent.mkdir(parents=True, exist_ok=True)
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
out = []
seen = set()
for line in lines:
    replaced = False
    for key, value in items:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            seen.add(key)
            replaced = True
            break
    if not replaced:
        out.append(line)
for key, value in items:
    if key not in seen:
        if out and out[-1] != "":
            out.append("")
        out.append(f"{key}={value}")
path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY
}

configured_state() {
  if [[ -n "${1:-}" ]]; then
    printf 'configured'
  else
    printf 'missing'
  fi
}

runtime_workspace() {
  printf '%s/.jiuwenclaw-instances/%s\n' "$HOME" "$RUNTIME_INSTANCE"
}

ensure_env_file() {
  local env_was_created=0
  if [[ ! -f "$ENV_FILE" ]]; then
    cp "$ROOT_DIR/.env.example" "$ENV_FILE"
    env_was_created=1
    log "Created .env from .env.example"
  fi

  load_env

  if [[ "${GOD_SETUP_MODE:-0}" == "1" ]]; then
    set_env_value "GOD_LLM_API_BASE" "${GOD_LLM_API_BASE:-https://api.openai.com/v1}"
    set_env_value "GOD_LLM_MODEL" "${GOD_LLM_MODEL:-gpt-5.4}"
    set_env_value "GOD_EMBEDDING_MODEL" "${GOD_EMBEDDING_MODEL:-text-embedding-3-large}"
    load_env
    return 0
  fi

  if [[ -z "${GOD_LLM_API_KEY:-}" ]]; then
    if [[ -t 0 ]]; then
      printf '[GOD] LLM API key is required. Paste it now (input hidden): '
      stty -echo
      read -r api_key
      stty echo
      printf '\n'
      [[ -n "$api_key" ]] || die "LLM API key is empty"
      set_env_value "GOD_LLM_API_KEY" "$api_key"
    else
      die "GOD_LLM_API_KEY is empty. Fill $ENV_FILE first."
    fi
  fi

  if [[ "$env_was_created" == "1" && -t 0 ]]; then
    local default_api_base="${GOD_LLM_API_BASE:-https://api.openai.com/v1}"
    local default_model="${GOD_LLM_MODEL:-gpt-5.4}"
    local api_base_input
    local model_input
    printf '[GOD] LLM API base URL [%s]: ' "$default_api_base"
    read -r api_base_input
    printf '[GOD] LLM model [%s]: ' "$default_model"
    read -r model_input
    set_env_value "GOD_LLM_API_BASE" "${api_base_input:-$default_api_base}"
    set_env_value "GOD_LLM_MODEL" "${model_input:-$default_model}"
  fi

  set_env_value "GOD_LLM_API_BASE" "${GOD_LLM_API_BASE:-https://api.openai.com/v1}"
  set_env_value "GOD_LLM_MODEL" "${GOD_LLM_MODEL:-gpt-5.4}"
  set_env_value "GOD_EMBEDDING_MODEL" "${GOD_EMBEDDING_MODEL:-text-embedding-3-large}"

  load_env
}

is_port_open() {
  local port="$1"
  python3 - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
for host in ("127.0.0.1", "::1", "localhost"):
    try:
        with socket.create_connection((host, port), timeout=0.35):
            raise SystemExit(0)
    except OSError:
        pass
raise SystemExit(1)
PY
}

wait_for_port() {
  local port="$1"
  local label="$2"
  local timeout="${3:-90}"
  local deadline=$((SECONDS + timeout))
  while (( SECONDS < deadline )); do
    if is_port_open "$port"; then
      log "$label ready on port $port"
      return 0
    fi
    sleep 1
  done
  print_wait_timeout_context "$label" "$port"
  die "Timed out waiting for $label on port $port"
}

print_wait_timeout_context() {
  local label="$1"
  local port="$2"
  printf '[GOD] timeout diagnostics for %s on port %s\n' "$label" "$port" >&2
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >&2 2>/dev/null || true

  if [[ "$label" == "Agent runtime"* && -f "$LOG_DIR/runtime.log" ]]; then
    printf '[GOD] recent runtime log:\n' >&2
    tail -n 80 "$LOG_DIR/runtime.log" >&2 || true
  fi
}

urlencode() {
  python3 - "$1" <<'PY'
import sys
from urllib.parse import quote
print(quote(sys.argv[1], safe=""))
PY
}

replay_url() {
  printf '%s/pixel-replay/%s/%s\n' \
    "$frontend_url" \
    "$GOD_EXPERIMENT" \
    "$GOD_EXPERIMENT_RUN"
}

session_url() {
  printf '%s/api/v1/live-experiments/%s/%s/sessions?workspace_path=%s\n' \
    "$backend_url" \
    "$GOD_EXPERIMENT" \
    "$GOD_EXPERIMENT_RUN" \
    "$(urlencode "$LIVE_WORKSPACE_PATH")"
}

run_step_url() {
  printf '%s/api/v1/live-experiments/%s/%s/run-step?workspace_path=%s\n' \
    "$backend_url" \
    "$GOD_EXPERIMENT" \
    "$GOD_EXPERIMENT_RUN" \
    "$(urlencode "$LIVE_WORKSPACE_PATH")"
}

stop_live_url() {
  printf '%s/api/v1/live-experiments/%s/%s/stop?workspace_path=%s\n' \
    "$backend_url" \
    "$GOD_EXPERIMENT" \
    "$GOD_EXPERIMENT_RUN" \
    "$(urlencode "$LIVE_WORKSPACE_PATH")"
}

print_frontend_links() {
  printf 'Control room:     %s\n' "$(replay_url)"
  printf 'Agent runtime UI: %s\n' "$runtime_ui_url"
}

open_browser_window() {
  local url="$1"
  [[ "${GOD_OPEN_BROWSER:-1}" == "1" ]] || return 0
  if command_exists open; then
    open "$url" >/dev/null 2>&1 || true
  fi
}

open_frontend_pages() {
  command_exists open || return 0
  log "Opening frontend pages"
  open_browser_window "$(replay_url)"
  open_browser_window "$runtime_ui_url"
}

setup_url() {
  printf '%s/setup\n' "$frontend_url"
}

open_setup_page() {
  log "Opening setup wizard"
  open_browser_window "$(setup_url)"
  printf 'Setup wizard:     %s\n' "$(setup_url)"
}

has_ready_start_config() {
  load_env
  [[ -n "${GOD_LLM_API_KEY:-}" ]] || return 1
  [[ -f "$CURRENT_EXPERIMENT_FILE" ]] || return 1
  local config_path="$LIVE_WORKSPACE_PATH/hypothesis_${GOD_EXPERIMENT}/experiment_${GOD_EXPERIMENT_RUN}/init/init_config.json"
  [[ -f "$config_path" ]] || return 1
}

stop_control_services() {
  kill_pid_file "$FRONTEND_PID_FILE" "control room"
  kill_pid_file "$BACKEND_PID_FILE" "backend"
  kill_listeners_on_port "$GOD_FRONTEND_PORT"
  kill_listeners_on_port "$GOD_BACKEND_PORT"
}

kill_pid_file() {
  local file="$1"
  local label="$2"
  [[ -f "$file" ]] || return 0
  local pid
  pid="$(cat "$file" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    log "Stopping $label pid=$pid"
    kill "$pid" 2>/dev/null || true
    local deadline=$((SECONDS + 8))
    while (( SECONDS < deadline )); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.3
    done
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$file"
}

kill_listeners_on_port() {
  local port="$1"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ' || true)"
  [[ -n "${pids// }" ]] || return 0
  log "Clearing port $port"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  sleep 0.6
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ' || true)"
  if [[ -n "${pids// }" ]]; then
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
}

clear_live_ports() {
  for port in \
    "$GOD_BACKEND_PORT" \
    "$GOD_FRONTEND_PORT" \
    "$RUNTIME_AGENT_PORT" \
    "$RUNTIME_WEB_PORT" \
    "$RUNTIME_GATEWAY_PORT" \
    "$RUNTIME_UI_PORT" \
    $GOD_EXTRA_STOP_PORTS
  do
    kill_listeners_on_port "$port"
  done
}

stop_known_screens() {
  command_exists screen || return 0
  for name in "$RUNTIME_INSTANCE" $RUNTIME_LEGACY_INSTANCES god-town god-backend god-frontend agentsociety-backend agentsociety-frontend; do
    if screen_list | grep -q "[.]$name[[:space:]]"; then
      log "Stopping leftover session: $name"
      screen -S "$name" -X quit >/dev/null 2>&1 || true
    fi
  done
}

start_detached_service() {
  local session_name="$1"
  local pid_file="$2"
  local command="$3"

  if command_exists screen; then
    if screen_list | grep -q "[.]$session_name[[:space:]]"; then
      log "Replacing old session: $session_name"
      screen -S "$session_name" -X quit >/dev/null 2>&1 || true
      sleep 0.5
    fi
    screen -dmS "$session_name" bash -lc "$command"
    sleep 0.5
    local screen_pid
    screen_pid="$(
      screen_list \
        | awk -v name="$session_name" '$1 ~ "[.]" name "$" { split($1, a, "."); print a[1]; exit }'
    )"
    [[ -n "$screen_pid" ]] || die "Failed to create session: $session_name"
    printf '%s\n' "$screen_pid" > "$pid_file"
  else
    nohup bash -lc "$command" >/dev/null 2>&1 &
    printf '%s\n' "$!" > "$pid_file"
  fi
}

stop_runtime_instance() {
  local name="$1"
  [[ -d "$RUNTIME_ROOT" ]] || return 0
  command_exists uv || return 0
  (
    cd "$RUNTIME_ROOT"
    uv run jiuwenclaw-start --stop "$name" >/dev/null 2>&1 || true
  )
}

stop_all() {
  log "Stopping GOD services"
  if is_port_open "$GOD_BACKEND_PORT"; then
    curl -fsS -X POST "$(stop_live_url)" >/dev/null 2>&1 || true
  fi
  kill_pid_file "$FRONTEND_PID_FILE" "control room"
  kill_pid_file "$BACKEND_PID_FILE" "backend"
  kill_pid_file "$RUNTIME_PID_FILE" "agent runtime"
  stop_known_screens
  stop_runtime_instance "$RUNTIME_INSTANCE"
  for name in $RUNTIME_LEGACY_INSTANCES; do
    stop_runtime_instance "$name"
  done
  clear_live_ports
}

remove_runtime_registry_entries() {
  [[ -d "$RUNTIME_ROOT" ]] || return 0
  command_exists uv || return 0
  (
    cd "$RUNTIME_ROOT"
    uv run python - "$RUNTIME_INSTANCE" $RUNTIME_LEGACY_INSTANCES <<'PY'
import sys
from pathlib import Path
from ruamel.yaml import YAML

names = set(sys.argv[1:])
path = Path.home() / ".jiuwenclaw" / "instances.yaml"
if not path.exists():
    raise SystemExit(0)

yaml = YAML()
data = yaml.load(path.read_text(encoding="utf-8")) or {}
instances = data.get("instances")
if not isinstance(instances, dict):
    raise SystemExit(0)

for name in names:
    instances.pop(name, None)

if instances:
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f)
else:
    path.unlink()
PY
  ) || log "Could not update runtime registry; continuing reset"
}

remove_path() {
  local path="$1"
  local label="$2"
  if [[ -e "$path" || -L "$path" ]]; then
    log "Removing $label"
    rm -rf "$path"
  fi
}

remove_experiment_runs() {
  [[ -d "$LIVE_WORKSPACE_PATH" ]] || return 0
  log "Removing experiment run directories"
  find "$LIVE_WORKSPACE_PATH" -maxdepth 4 \( -name run -o -name 'run_*' \) -type d -prune -exec rm -rf {} +
}

factory_reset() {
  require_base_tools
  log "Factory reset"
  stop_all

  remove_experiment_runs
  remove_runtime_registry_entries
  for name in "$RUNTIME_INSTANCE" $RUNTIME_LEGACY_INSTANCES; do
    remove_path "$HOME/.jiuwenclaw-instances/$name" "runtime instance state"
  done

  remove_path "$ENV_FILE" ".env"
  remove_path "$STATE_DIR" "state and logs"
  remove_path "$BACKEND_ROOT/.venv" "backend virtualenv"
  remove_path "$RUNTIME_ROOT/.venv" "runtime virtualenv"
  remove_path "$BACKEND_ROOT/frontend/node_modules" "frontend dependencies"
  remove_path "$RUNTIME_ROOT/jiuwenclaw/channels/web/frontend/node_modules" "runtime UI dependencies"

  find "$ROOT_DIR" -maxdepth 5 \( -name .pytest_cache -o -name .ruff_cache -o -name __pycache__ \) -type d -prune -exec rm -rf {} + 2>/dev/null || true

  log "Factory reset complete."
}

setup_deps() {
  require_base_tools
  if [[ "${GOD_SKIP_SETUP:-0}" == "1" ]]; then
    log "Skipping dependency setup (GOD_SKIP_SETUP=1)"
    return 0
  fi

  if [[ ! -d "$BACKEND_ROOT/.venv" || "${GOD_FORCE_SETUP:-0}" == "1" ]]; then
    log "Syncing backend Python dependencies"
    (cd "$BACKEND_ROOT" && uv sync)
  fi

  if [[ ! -d "$RUNTIME_ROOT/.venv" || "${GOD_FORCE_SETUP:-0}" == "1" ]]; then
    log "Syncing agent runtime Python dependencies"
    (cd "$RUNTIME_ROOT" && uv sync)
  fi

  if [[ ! -d "$BACKEND_ROOT/frontend/node_modules" || "${GOD_FORCE_SETUP:-0}" == "1" ]]; then
    log "Installing control-room dependencies"
    npm install --no-audit --no-fund --loglevel=error --prefix "$BACKEND_ROOT/frontend"
  fi

  local runtime_frontend="$RUNTIME_ROOT/jiuwenclaw/channels/web/frontend"
  if [[ ! -d "$runtime_frontend/node_modules" || "${GOD_FORCE_SETUP:-0}" == "1" ]]; then
    log "Installing runtime UI dependencies"
    npm install --no-audit --no-fund --loglevel=error --prefix "$runtime_frontend"
  fi
}

ensure_runtime_instance() {
  setup_deps
  local existing=0
  (
    cd "$RUNTIME_ROOT"
    uv run jiuwenclaw-start --status "$RUNTIME_INSTANCE" >/dev/null 2>&1
  ) || existing=1

  if [[ "$existing" != "0" ]]; then
    log "Initializing agent runtime instance (default language: $RUNTIME_LANGUAGE)"
    local workspace="$HOME/.jiuwenclaw-instances/$RUNTIME_INSTANCE"
    : > "$LOG_DIR/runtime-init.log"
    if [[ -d "$workspace" ]]; then
      (
        cd "$RUNTIME_ROOT"
        printf 'yes\n%s\n' "$RUNTIME_LANGUAGE" | uv run jiuwenclaw-init --name "$RUNTIME_INSTANCE" >> "$LOG_DIR/runtime-init.log" 2>&1
      ) || {
        tail -n 80 "$LOG_DIR/runtime-init.log" >&2 || true
        die "Failed to initialize agent runtime instance"
      }
    else
      (
        cd "$RUNTIME_ROOT"
        printf '%s\n' "$RUNTIME_LANGUAGE" | uv run jiuwenclaw-init --name "$RUNTIME_INSTANCE" >> "$LOG_DIR/runtime-init.log" 2>&1
      ) || {
        tail -n 80 "$LOG_DIR/runtime-init.log" >&2 || true
        die "Failed to initialize agent runtime instance"
      }
    fi
  fi

  (
    cd "$RUNTIME_ROOT"
    RUNTIME_INSTANCE="$RUNTIME_INSTANCE" \
    RUNTIME_AGENT_PORT="$RUNTIME_AGENT_PORT" \
    RUNTIME_WEB_PORT="$RUNTIME_WEB_PORT" \
    RUNTIME_GATEWAY_PORT="$RUNTIME_GATEWAY_PORT" \
    RUNTIME_UI_PORT="$RUNTIME_UI_PORT" \
    uv run python - <<'PY'
import os
from pathlib import Path
from ruamel.yaml import YAML

name = os.environ["RUNTIME_INSTANCE"]
path = Path.home() / ".jiuwenclaw" / "instances.yaml"
path.parent.mkdir(parents=True, exist_ok=True)
yaml = YAML()
data = yaml.load(path.read_text(encoding="utf-8")) if path.exists() else None
if not isinstance(data, dict):
    data = {"instances": {}}
instances = data.setdefault("instances", {})
entry = instances.setdefault(name, {})
workspace = entry.get("workspace") or str(Path.home() / ".jiuwenclaw-instances" / name)
entry["workspace"] = workspace
entry["ports"] = {
    "agent_server": int(os.environ["RUNTIME_AGENT_PORT"]),
    "web": int(os.environ["RUNTIME_WEB_PORT"]),
    "gateway": int(os.environ["RUNTIME_GATEWAY_PORT"]),
    "frontend": int(os.environ["RUNTIME_UI_PORT"]),
}
with path.open("w", encoding="utf-8") as f:
    yaml.dump(data, f)

workspace_path = Path(workspace).expanduser()
workspace_path.mkdir(parents=True, exist_ok=True)
bootstrap_env = workspace_path / ".env"
bootstrap_env.write_text(
    "\n".join(
        [
            f"# Bootstrap .env for runtime instance: {name}",
            f"JIUWENCLAW_DATA_DIR={workspace_path}",
            f"JIUWENCLAW_INSTANCE={name}",
            f"AGENT_SERVER_PORT={os.environ['RUNTIME_AGENT_PORT']}",
            f"WEB_PORT={os.environ['RUNTIME_WEB_PORT']}",
            f"GATEWAY_PORT={os.environ['RUNTIME_GATEWAY_PORT']}",
            f"FRONTEND_PORT={os.environ['RUNTIME_UI_PORT']}",
            "",
        ]
    ),
    encoding="utf-8",
)
PY
  )
  sync_runtime_model_env
}

sync_runtime_model_env() {
  local workspace
  workspace="$(runtime_workspace)"
  local config_env="$workspace/config/.env"
  [[ -d "$workspace" ]] || return 0

  local api_key="${GOD_LLM_API_KEY:-}"
  local api_base="${GOD_LLM_API_BASE:-}"
  local model="${GOD_LLM_MODEL:-}"
  local provider="${JIUWENCLAW_MODEL_PROVIDER:-OpenAI}"
  local embed_key="${GOD_EMBEDDING_API_KEY:-$api_key}"
  local embed_base="${GOD_EMBEDDING_API_BASE:-$api_base}"
  local embed_model="${GOD_EMBEDDING_MODEL:-}"

  [[ -n "$api_key" ]] || return 0
  [[ -n "$api_base" ]] || return 0
  [[ -n "$model" ]] || return 0

  log "Syncing runtime model config"
  set_env_values_in_file "$config_env" \
    API_KEY "$api_key" \
    API_BASE "$api_base" \
    MODEL_NAME "$model" \
    MODEL_PROVIDER "$provider" \
    EMBED_API_KEY "$embed_key" \
    EMBED_API_BASE "$embed_base" \
    EMBED_MODEL "$embed_model"
}

prepare_experiment() {
  local experiment_path="$LIVE_WORKSPACE_PATH/hypothesis_${GOD_EXPERIMENT}/experiment_${GOD_EXPERIMENT_RUN}"
  local config_path="$experiment_path/init/init_config.json"
  [[ -f "$config_path" ]] || die "Experiment config not found: $config_path"

  local session_prefix="${GOD_SESSION_PREFIX:-${GOD_EXPERIMENT}_run_${GOD_EXPERIMENT_RUN}}"
  log "Preparing experiment: $GOD_EXPERIMENT (run $GOD_EXPERIMENT_RUN)"
  BACKEND_ROOT="$BACKEND_ROOT" \
  RUNTIME_AGENT_PORT="$RUNTIME_AGENT_PORT" \
  GOD_SESSION_PREFIX="$session_prefix" \
  python3 - "$config_path" <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
config = json.loads(path.read_text(encoding="utf-8"))
agent_root = str(Path(os.environ["BACKEND_ROOT"]).resolve())
ws_url = f"ws://127.0.0.1:{os.environ['RUNTIME_AGENT_PORT']}"
session_prefix = os.environ["GOD_SESSION_PREFIX"]

for module in config.get("env_modules", []):
    if module.get("module_type") == "PixelTownSocialEnv":
        kwargs = module.setdefault("kwargs", {})
        kwargs["map_manifest_path"] = "custom/maps/the_ville/town.yaml"

for agent in config.get("agents", []):
    kwargs = agent.setdefault("kwargs", {})
    agent_id = int(agent.get("agent_id") or kwargs.get("id") or 0)
    kwargs["jiuwenclaw_ws_url"] = ws_url
    kwargs["session_id"] = f"{session_prefix}_agent_{agent_id}"
    kwargs["trusted_dirs"] = [agent_root]

path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

start_runtime() {
  ensure_runtime_instance
  if is_port_open "$RUNTIME_AGENT_PORT" \
    && is_port_open "$RUNTIME_WEB_PORT" \
    && is_port_open "$RUNTIME_GATEWAY_PORT" \
    && is_port_open "$RUNTIME_UI_PORT"; then
    log "Agent runtime already up"
    return 0
  fi

  log "Starting agent runtime"
  : > "$LOG_DIR/runtime.log"
  local runtime_cmd
  runtime_cmd="cd $(shell_quote "$RUNTIME_ROOT")"
  runtime_cmd+=" && export JIUWENCLAW_ROOT=$(shell_quote "$RUNTIME_ROOT")"
  runtime_cmd+=" && export JIUWENCLAW_PROJECT_ROOT=$(shell_quote "$RUNTIME_ROOT")"
  runtime_cmd+=" && export AGENT_SERVER_PORT=$(shell_quote "$RUNTIME_AGENT_PORT")"
  runtime_cmd+=" && export WEB_PORT=$(shell_quote "$RUNTIME_WEB_PORT")"
  runtime_cmd+=" && export GATEWAY_PORT=$(shell_quote "$RUNTIME_GATEWAY_PORT")"
  runtime_cmd+=" && export FRONTEND_PORT=$(shell_quote "$RUNTIME_UI_PORT")"
  runtime_cmd+=" && exec uv run jiuwenclaw-start $(shell_quote "$RUNTIME_MODE") --name $(shell_quote "$RUNTIME_INSTANCE") >> $(shell_quote "$LOG_DIR/runtime.log") 2>&1"
  start_detached_service "$RUNTIME_INSTANCE" "$RUNTIME_PID_FILE" "$runtime_cmd"

  wait_for_port "$RUNTIME_AGENT_PORT" "Agent runtime" 180
  wait_for_port "$RUNTIME_WEB_PORT" "Agent runtime web" 120
  wait_for_port "$RUNTIME_GATEWAY_PORT" "Agent runtime gateway" 120
  wait_for_port "$RUNTIME_UI_PORT" "Agent runtime UI" 120
}

start_backend() {
  ensure_env_file
  if is_port_open "$GOD_BACKEND_PORT" && curl -fsS "$backend_url/health" >/dev/null 2>&1; then
    log "Backend already up"
    return 0
  fi

  log "Starting backend"
  : > "$LOG_DIR/backend.log"
  local backend_log_level="${BACKEND_LOG_LEVEL:-info}"
  local backend_cmd
  backend_cmd="cd $(shell_quote "$BACKEND_ROOT")"
  backend_cmd+=" && set -a && source $(shell_quote "$ENV_FILE") && set +a"
  backend_cmd+=" && export GOD_ROOT=$(shell_quote "$ROOT_DIR")"
  backend_cmd+=" && export GOD_ENV_FILE=$(shell_quote "$ENV_FILE")"
  backend_cmd+=" && export LIVE_WORKSPACE_PATH=$(shell_quote "$LIVE_WORKSPACE_PATH")"
  backend_cmd+=" && export AGENTSOCIETY_LLM_API_KEY=\"\${GOD_LLM_API_KEY:-}\""
  backend_cmd+=" && export AGENTSOCIETY_LLM_API_BASE=\"\${GOD_LLM_API_BASE:-https://api.openai.com/v1}\""
  backend_cmd+=" && export AGENTSOCIETY_LLM_MODEL=\"\${GOD_LLM_MODEL:-gpt-5.4}\""
  backend_cmd+=" && export AGENTSOCIETY_NANO_LLM_MODEL=\"\${GOD_LLM_NANO_MODEL:-gpt-5.4-nano}\""
  backend_cmd+=" && export AGENTSOCIETY_EMBEDDING_API_KEY=\"\${GOD_EMBEDDING_API_KEY:-\$AGENTSOCIETY_LLM_API_KEY}\""
  backend_cmd+=" && export AGENTSOCIETY_EMBEDDING_API_BASE=\"\${GOD_EMBEDDING_API_BASE:-\$AGENTSOCIETY_LLM_API_BASE}\""
  backend_cmd+=" && export AGENTSOCIETY_EMBEDDING_MODEL=\"\${GOD_EMBEDDING_MODEL:-text-embedding-3-large}\""
  backend_cmd+=" && export BACKEND_HOST=$(shell_quote "$GOD_BACKEND_HOST")"
  backend_cmd+=" && export BACKEND_PORT=$(shell_quote "$GOD_BACKEND_PORT")"
  backend_cmd+=" && export AGENTSOCIETY_LIVE_STEP_TIMEOUT=$(shell_quote "$GOD_LIVE_STEP_TIMEOUT")"
  backend_cmd+=" && export BACKEND_LOG_LEVEL=$(shell_quote "$backend_log_level")"
  backend_cmd+=" && exec uv run python -m agentsociety2.backend.run --log-level $(shell_quote "$backend_log_level") >> $(shell_quote "$LOG_DIR/backend.log") 2>&1"
  start_detached_service "god-backend" "$BACKEND_PID_FILE" "$backend_cmd"

  wait_for_port "$GOD_BACKEND_PORT" "Backend" 120
  local deadline=$((SECONDS + 30))
  while (( SECONDS < deadline )); do
    curl -fsS "$backend_url/health" >/dev/null 2>&1 && return 0
    sleep 1
  done
  die "Backend port is open but /health did not respond"
}

start_frontend() {
  if is_port_open "$GOD_FRONTEND_PORT"; then
    log "Control room already up"
    return 0
  fi

  log "Starting control room"
  : > "$LOG_DIR/frontend.log"
  local frontend_cmd
  frontend_cmd="cd $(shell_quote "$BACKEND_ROOT/frontend")"
  frontend_cmd+=" && export VITE_REPLAY_WORKSPACE_PATH=$(shell_quote "$LIVE_WORKSPACE_PATH")"
  frontend_cmd+=" && export VITE_DEFAULT_REPLAY_HYPOTHESIS_ID=$(shell_quote "$GOD_EXPERIMENT")"
  frontend_cmd+=" && export VITE_DEFAULT_REPLAY_EXPERIMENT_ID=$(shell_quote "$GOD_EXPERIMENT_RUN")"
  frontend_cmd+=" && exec npm run dev -- --host 127.0.0.1 --port $(shell_quote "$GOD_FRONTEND_PORT") >> $(shell_quote "$LOG_DIR/frontend.log") 2>&1"
  start_detached_service "god-frontend" "$FRONTEND_PID_FILE" "$frontend_cmd"

  wait_for_port "$GOD_FRONTEND_PORT" "Control room" 120
}

start_setup_services() {
  setup_deps
  export GOD_SETUP_MODE=1
  ensure_env_file
  rm -f "$START_REQUEST_FILE"
  stop_control_services
  start_backend
  start_frontend
  open_setup_page
}

wait_for_start_request() {
  log "Waiting for setup wizard to save and request startup"
  local next_notice=$((SECONDS + 30))
  while [[ ! -f "$START_REQUEST_FILE" ]]; do
    sleep 2
    if (( SECONDS >= next_notice )); then
      log "Still waiting on $(setup_url)"
      next_notice=$((SECONDS + 30))
    fi
  done

  local parsed hypothesis_id experiment_id workspace_path
  parsed="$(
    python3 - "$START_REQUEST_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
print(
    "\t".join(
        [
            str(data.get("hypothesis_id") or ""),
            str(data.get("experiment_id") or "1"),
            str(data.get("workspace_path") or ""),
        ]
    )
)
PY
  )" || die "Could not read setup start request"
  IFS=$'\t' read -r hypothesis_id experiment_id workspace_path <<< "$parsed"
  [[ -n "$hypothesis_id" ]] || die "Setup start request is missing hypothesis_id"
  mv "$START_REQUEST_FILE" "$START_REQUEST_FILE.consumed" 2>/dev/null || rm -f "$START_REQUEST_FILE"

  export GOD_EXPERIMENT="$hypothesis_id"
  export GOD_EXPERIMENT_RUN="${experiment_id:-1}"
  if [[ -n "$workspace_path" ]]; then
    export LIVE_WORKSPACE_PATH="$workspace_path"
  fi
  load_env
  log "Received start request: $GOD_EXPERIMENT / experiment_$GOD_EXPERIMENT_RUN"
}

start_with_setup_if_needed() {
  require_base_tools
  load_env
  if has_ready_start_config; then
    start_all
    return 0
  fi

  log "No complete experiment configuration found; starting setup wizard first"
  start_setup_services
  wait_for_start_request
  unset GOD_SETUP_MODE
  stop_control_services
  start_all
}

configure_experiment() {
  require_base_tools
  log "Starting new experiment setup wizard"
  start_setup_services
  wait_for_start_request
  unset GOD_SETUP_MODE
  stop_control_services
  start_all
}

create_session() {
  if ! is_port_open "$GOD_BACKEND_PORT" || ! curl -fsS "$backend_url/health" >/dev/null 2>&1; then
    start_backend
  fi
  log "Creating live session"
  local status_json
  status_json="$(curl -fsS -X POST "$(session_url)" \
    -H 'content-type: application/json' \
    -d '{}')" || die "Failed to create live session"

  local step_count
  step_count="$(python3 -c 'import json, sys; print(json.load(sys.stdin).get("step_count", 0))' <<< "$status_json")"
  if [[ "${GOD_PRIME_FIRST_STEP:-1}" != "0" && "$step_count" == "0" ]]; then
    log "Priming live session (step 1)"
    curl -fsS -X POST "$(run_step_url)" \
      -H 'content-type: application/json' \
      -d '{}' >/dev/null || die "Failed to run the first live step"
  fi
}

start_all() {
  load_env
  setup_deps
  ensure_env_file
  prepare_experiment
  start_runtime
  start_backend
  start_frontend
  create_session
  print_status
}

restart_all() {
  require_base_tools
  stop_all
  start_with_setup_if_needed
}

new_run() {
  require_base_tools
  load_env
  export GOD_SESSION_PREFIX="${GOD_EXPERIMENT}_fresh_$(date +%Y%m%d_%H%M%S)"
  stop_all
  local run_dir="$LIVE_WORKSPACE_PATH/hypothesis_${GOD_EXPERIMENT}/experiment_${GOD_EXPERIMENT_RUN}/run"
  rm -rf "$run_dir"
  log "Cleared previous run"
  start_all
}

print_port_status() {
  local label="$1"
  local port="$2"
  if is_port_open "$port"; then
    printf '%-24s %s up\n' "$label" "$port"
  else
    printf '%-24s %s down\n' "$label" "$port"
  fi
}

print_status() {
  load_env
  printf '\nGOD status\n'
  printf '%s\n' '----------'
  print_port_status "Backend" "$GOD_BACKEND_PORT"
  print_port_status "Control room" "$GOD_FRONTEND_PORT"
  print_port_status "Agent runtime" "$RUNTIME_AGENT_PORT"
  print_port_status "Agent runtime web" "$RUNTIME_WEB_PORT"
  print_port_status "Agent runtime gateway" "$RUNTIME_GATEWAY_PORT"
  print_port_status "Agent runtime UI" "$RUNTIME_UI_PORT"
  printf '\nURLs\n'
  print_frontend_links
  printf 'Backend:          %s/health\n' "$backend_url"
  printf '\nModel\n'
  printf 'API key:       %s\n' "$(configured_state "${GOD_LLM_API_KEY:-}")"
  printf 'API base:      %s\n' "${GOD_LLM_API_BASE:-<unset>}"
  printf 'Model:         %s\n' "${GOD_LLM_MODEL:-<unset>}"
}

tail_logs() {
  touch "$LOG_DIR/runtime.log" "$LOG_DIR/backend.log" "$LOG_DIR/frontend.log"
  tail -f "$LOG_DIR/runtime.log" "$LOG_DIR/backend.log" "$LOG_DIR/frontend.log"
}

open_replay() {
  if command_exists open; then
    open_frontend_pages
  else
    print_status
  fi
}

interactive_menu() {
  cat <<'EOF'

GOD - Govern, Observe, Direct

1. Start
2. Restart
3. New run (reset replay and start fresh)
4. Configure new experiment
5. Status
6. Stop
7. Tail logs
8. Setup dependencies only

EOF
  printf 'Choose: '
  read -r choice
  case "$choice" in
    1|"") start_with_setup_if_needed ;;
    2) restart_all ;;
    3) new_run ;;
    4) configure_experiment; open_frontend_pages ;;
    5) print_status ;;
    6) stop_all ;;
    7) tail_logs ;;
    8) setup_deps; GOD_SETUP_MODE=1 ensure_env_file ;;
    *) usage; exit 2 ;;
  esac
}

ACTION="${1:-menu}"
load_env

case "$ACTION" in
  menu)
    interactive_menu
    ;;
  setup)
    setup_deps
    GOD_SETUP_MODE=1 ensure_env_file
    ;;
  configure)
    configure_experiment
    open_frontend_pages
    ;;
  start)
    start_with_setup_if_needed
    open_frontend_pages
    ;;
  restart)
    restart_all
    open_frontend_pages
    ;;
  new-run)
    new_run
    open_frontend_pages
    ;;
  factory-reset|reset)
    factory_reset
    ;;
  session)
    require_base_tools
    prepare_experiment
    create_session
    ;;
  stop)
    require_base_tools
    stop_all
    ;;
  status)
    require_base_tools
    print_status
    ;;
  tail)
    tail_logs
    ;;
  open)
    open_replay
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage
    exit 2
    ;;
esac
