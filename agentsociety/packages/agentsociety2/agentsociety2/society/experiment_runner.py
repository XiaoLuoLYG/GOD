"""Relocate only the standalone runners shipped in historical GOD ExperimentPacks."""

from hashlib import sha256
import re

MAX_STOCK_RUNNER_BYTES = 4096

# Whole-file matches keep user-authored shell code byte-for-byte intact.
_STOCK_RUNNERS = {
    "216b01055c4c2bfb079f5b646f7f001f4044de434c0e46d4f2574caf738f58ab",  # sunblade-palace
    "246f56ce40648c4f19dece1c987d83f05d1c6f972f21b0ded73efd75286aa40e",  # god-town-daily-life
    "30e09e28adb252ea9e2db6e3316494361dbe1f62dcf268b532ee6397ceab3093",  # fuji-ash-town
    "5717ace7b1969850805388bac21f924e4dcb07f9d513b8df6a8d89f624cca2ee",  # lunar-condo-hoa
    "61abb903cb93caff23d57705a8b52b8cb66b095d8ec70d49a3df3657e39de41c",  # empty-city-gate
    "88250d381114b3533e36f60b784420d75026da06aa362cb964725824872b5ac1",  # gaokao-blackout
    "b9bebda513dc85d001c3c53205f0f3a2849cd6a28ef4ad914fe93586ab1c3e91",  # GOD Town with sidecars
    "c2de5f1f122ac4b7d874ea23a17c4cc57c2dd7960572e35ea2b550a798934b91",  # hogwarts-parent-meeting
    "cd54a4c471a39d0c9bd113326e840d7a542156c05e82746442d2c9fc72ffd74f",  # taohuayuan-online
    "f3443cee5a81daf5e06d1400e4e6e3e071697817f6a94bf30df6c17e99925e2c",  # idol-rift-variety
}

_OLD_ROOT = b'''ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"'''
_PORTABLE_ROOT = b'''EXPERIMENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${BACKEND_ROOT:-$EXPERIMENT_DIR/../../..}"'''
_PORTABLE_RUN = b'''command -v "$PYTHON_PATH" >/dev/null || { echo "Cannot find $PYTHON_PATH in $PWD" >&2; exit 1; }
HYPOTHESIS_NAME="$(basename "$(dirname "$EXPERIMENT_DIR")")"
EXPERIMENT_NAME="${EXPERIMENT_DIR##*/}"
RUN_DIR="$EXPERIMENT_DIR/run"
if [[ -d "$RUN_DIR" && ! -L "$RUN_DIR" ]]; then
  # Reset replay while keeping the local connection and resident sessions configured by GOD.
  find "$RUN_DIR" -mindepth 1 -maxdepth 1 ! -name .god-launch.json ! -name .god-session-prefix -exec rm -rf {} +
else
  rm -f "$RUN_DIR"
  mkdir -p "$RUN_DIR"
fi'''


def portable_experiment_runner(script: bytes) -> bytes:
    """Relocate recognized stock scripts and preserve all other scripts byte-for-byte."""
    if len(script) > MAX_STOCK_RUNNER_BYTES:
        return script
    source = script.replace(b"\r\n", b"\n")
    if sha256(source).hexdigest() not in _STOCK_RUNNERS:
        return script

    before_run, after_run = source.split(b'RUN_DIR="', 1)
    old_experiment, _ = after_run.split(b'/run"', 1)
    command = source[source.index(b'"$PYTHON_PATH" -m '):]
    for filename in (b"init_config.json", b"steps.yaml"):
        command = command.replace(old_experiment + b"/init/" + filename, b'"$EXPERIMENT_DIR/init/' + filename + b'"')
    command = re.sub(
        rb'--experiment-id "[^"]+"',
        b'--experiment-id "${HYPOTHESIS_NAME#hypothesis_}_${EXPERIMENT_NAME#experiment_}"',
        command,
    )
    return before_run.replace(_OLD_ROOT, _PORTABLE_ROOT) + _PORTABLE_RUN + b"\n\n" + command
