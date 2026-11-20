"""Exercise launcher port ownership and startup checks with local listeners."""

import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    windows = os.name == "nt"

    def quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    with tempfile.TemporaryDirectory(prefix="god launcher ") as directory:
        fixture = Path(directory).resolve()
        scripts = fixture / "scripts"
        scripts.mkdir()
        for name in ("god.sh", "god.ps1", "god.cmd"):
            shutil.copyfile(root / "scripts" / name, scripts / name)
        screen_dir = fixture / "screen"
        screen_dir.mkdir(mode=0o700)
        names = (
            "GOD_BACKEND_PORT", "GOD_FRONTEND_PORT", "RUNTIME_AGENT_PORT",
            "RUNTIME_WEB_PORT", "RUNTIME_GATEWAY_PORT", "RUNTIME_UI_PORT",
        )
        sockets = [socket.socket() for _ in names]
        try:
            for sock in sockets:
                sock.bind(("127.0.0.1", 0))
            ports = {name: str(sock.getsockname()[1]) for name, sock in zip(names, sockets)}
        finally:
            for sock in sockets:
                sock.close()
        env_file = fixture / ".env"
        env_file.write_text("".join(f"{name}={port}\n" for name, port in ports.items()), encoding="utf-8")
        env = dict(
            os.environ, GOD_ENV_FILE=str(env_file), RUNTIME_ROOT=str(fixture / "absent-runtime"),
            BACKEND_ROOT=str(fixture / "absent-backend"), GOD_SKIP_SETUP="1", GOD_OPEN_BROWSER="0", SCREENDIR=str(screen_dir),
        )
        frontend_port = int(ports["GOD_FRONTEND_PORT"])
        serve = (
            "import socket, sys, time; s=socket.socket(); "
            "s.bind(('127.0.0.1', int(sys.argv[1]))); s.listen(32); "
            "print('ready'); time.sleep(90)"
        )
        listener = subprocess.Popen(
            [sys.executable, "-u", "-c", serve, str(frontend_port)],
            stdout=subprocess.PIPE, text=True,
        )
        try:
            assert listener.stdout.readline().strip() == "ready"
            command = (
                ["cmd.exe", "/d", "/c", r"scripts\god.cmd"] if windows else ["bash", "scripts/god.sh"]
            )

            def run(action: str, *, skip_setup: bool = True) -> subprocess.CompletedProcess:
                return subprocess.run(
                    [*command, action], cwd=fixture, env=dict(env, GOD_SKIP_SETUP=str(int(skip_setup))), capture_output=True,
                    text=True, errors="replace", timeout=30,
                )

            stopped = run("stop")
            assert stopped.returncode == 0, stopped.stderr
            assert listener.poll() is None, "stop killed a process with no GOD PID record"

            # A stale PID file can refer to another process after an OS restart.
            (fixture / ".god" / "pids" / "frontend.pid").write_text(f"{listener.pid}\n", encoding="ascii")
            stopped = run("stop")
            assert stopped.returncode == 0, stopped.stderr
            assert listener.poll() is None, "stop trusted a stale GOD PID record"

            started = run("start", skip_setup=False)
            output = started.stdout + started.stderr
            assert started.returncode != 0, output
            assert f"Port {frontend_port} is occupied" in output and "GOD_FRONTEND_PORT" in output, output
            assert "Syncing backend Python dependencies" not in output, output
            assert listener.poll() is None, "start killed the process that owns the port"
            status = run("status")
            assert status.returncode == 0 and f"{frontend_port} occupied" in status.stdout, status.stdout

            @contextmanager
            def recorded_listener(service: str, port: int):
                logfile = fixture / ".god" / "logs" / f"{service}.log"
                serve_cmd = [sys.executable, "-u", "-c", serve, str(port)]
                if windows:
                    encoded = base64.b64encode(
                        ("& " + " ".join(map(quote, serve_cmd)) + " >> " + quote(str(logfile))).encode("utf-16le")
                    ).decode("ascii")
                    owned = subprocess.Popen(["powershell.exe", "-NoProfile", "-EncodedCommand", encoded])
                else:
                    with logfile.open("w", encoding="utf-8") as log:
                        owned = subprocess.Popen(serve_cmd, stdout=log, stderr=log)
                try:
                    pid_file = fixture / ".god" / "pids" / f"{service}.pid"
                    pid_file.write_text(f"{owned.pid}\n", encoding="ascii")
                    for _ in range(50):
                        try:
                            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                                break
                        except OSError:
                            time.sleep(0.1)
                    else:
                        raise AssertionError("the fixture's GOD service did not start")
                    yield owned, pid_file
                finally:
                    if owned.poll() is None:
                        if windows:
                            subprocess.run(["taskkill", "/PID", str(owned.pid), "/T", "/F"], capture_output=True)
                        else:
                            owned.terminate()
                        owned.wait(timeout=10)

            runtime_port = int(ports["RUNTIME_AGENT_PORT"])
            with recorded_listener("runtime", runtime_port) as (owned, _):
                status = run("status")
                assert status.returncode == 0 and f"{runtime_port} up" in status.stdout, status.stdout + status.stderr
                stopped = run("stop")
                assert stopped.returncode == 0, stopped.stderr
                owned.wait(timeout=10)
                assert listener.poll() is None

            # JiuwenSwarm workers have their own session and outlive a graceful Front stop.
            worker_code = """
import signal, socket, sys, time
from pathlib import Path
marker = Path(sys.argv[1])
if sys.argv[2] == "stubborn":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
else:
    def stop(*_):
        marker.write_text("SIGTERM")
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
sock = socket.socket()
sock.bind(("127.0.0.1", int(sys.argv[3])))
sock.listen(32)
marker.with_suffix(".ready").touch()
deadline = time.monotonic() + 90
while marker.with_suffix(".alive").exists() and time.monotonic() < deadline:
    time.sleep(0.05)
"""
            front_code = """
import json, os, subprocess, sys, time
from pathlib import Path
worker = subprocess.Popen([sys.executable, "-u", sys.argv[1], *sys.argv[3:]], start_new_session=True)
Path(sys.argv[2]).write_text(json.dumps({"front": os.getpid(), "worker": worker.pid}))
time.sleep(90)
"""
            worker_script = fixture / "worker.py"
            worker_script.write_text(worker_code, encoding="utf-8")
            front_script = fixture / "front.py"
            front_script.write_text(front_code, encoding="utf-8")
            runtime_root = fixture / "runtime"
            metadata = fixture / "worker.json"
            env["RUNTIME_ROOT"] = str(runtime_root)
            if windows:
                launcher = scripts / "god.ps1"
                native_stop = """
function Stop-RuntimeInstance {
  param([string]$Name)
  $record = Get-Content -LiteralPath (Join-Path $script:RootDir "worker.json") -Raw | ConvertFrom-Json
  Stop-Process -Id $record.front -Force -ErrorAction SilentlyContinue
  $rootId = [int](Get-Content -LiteralPath $script:RuntimePidFile)
  Wait-Process -Id $rootId -Timeout 5 -ErrorAction SilentlyContinue
}
"""
                launcher.write_text(launcher.read_text(encoding="utf-8").replace(
                    "\nLoad-Env\n\nswitch ($Action)", "\n" + native_stop + "\nLoad-Env\n\nswitch ($Action)",
                ), encoding="utf-8")
            else:
                native_stop = runtime_root / ".venv" / "bin" / "jiuwenswarm-start"
                native_stop.parent.mkdir(parents=True)
                native_stop.write_text(
                    f"#!{sys.executable}\nimport json, os, signal, time\n"
                    f"from pathlib import Path\nrecord = json.loads(Path({str(metadata)!r}).read_text())\n"
                    "os.kill(record['front'], signal.SIGTERM)\ntime.sleep(0.3)\n",
                    encoding="utf-8",
                )
                native_stop.chmod(0o755)
            for mode in ("graceful", "stubborn"):
                marker = fixture / f"{mode}.signal"
                alive = marker.with_suffix(".alive")
                alive.touch()
                log = fixture / ".god" / "logs" / "runtime.log"
                front_cmd = [sys.executable, "-u", str(front_script), str(worker_script), str(metadata),
                             str(marker), mode, str(runtime_port)]
                if windows:
                    encoded = base64.b64encode(
                        ("& " + " ".join(map(quote, front_cmd)) + " >> " + quote(str(log))).encode("utf-16le")
                    ).decode("ascii")
                    front = subprocess.Popen(["powershell.exe", "-NoProfile", "-EncodedCommand", encoded])
                else:
                    with log.open("w", encoding="utf-8") as stream:
                        front = subprocess.Popen(front_cmd, stdout=stream, stderr=stream, start_new_session=True)
                try:
                    (fixture / ".god" / "pids" / "runtime.pid").write_text(f"{front.pid}\n", encoding="ascii")
                    ready = marker.with_suffix(".ready")
                    for _ in range(100):
                        if ready.exists():
                            break
                        time.sleep(0.05)
                    else:
                        raise AssertionError(f"the {mode} worker did not start")
                    status = run("status")
                    assert status.returncode == 0 and f"{runtime_port} up" in status.stdout, status.stdout + status.stderr
                    stopped = run("stop")
                    assert stopped.returncode == 0, stopped.stdout + stopped.stderr
                    front.wait(timeout=10)
                    try:
                        with socket.create_connection(("127.0.0.1", runtime_port), timeout=0.3):
                            raise AssertionError(f"stop left the {mode} worker alive after its Front exited")
                    except OSError:
                        pass
                    if not windows and mode == "graceful":
                        assert marker.exists(), "the worker did not receive graceful SIGTERM"
                    assert listener.poll() is None, "worker cleanup killed an unrelated process"
                finally:
                    alive.unlink(missing_ok=True)
                    if front.poll() is None:
                        front.terminate()
                    front.wait(timeout=10)
            env["RUNTIME_ROOT"] = str(fixture / "absent-runtime")

            if not windows:
                stopping = (scripts / "god.sh").read_text(encoding="utf-8").split(
                    "kill_pid_file() {", 1,
                )[1].split("\nstart_detached_service()", 1)[0]
                race_pid = fixture / ".god" / "pids" / "race.pid"
                for ps_status, ps_error in ((1, ""), (1, "ps inspection failed"), (2, "")):
                    race_pid.write_text("fixture\n", encoding="ascii")
                    result = subprocess.run([
                        "bash", "-c", "set -euo pipefail\n"
                        "service_processes() { echo 9999999; }\n"
                        f"ps() {{ printf '%s' '{ps_error}' >&2; return {ps_status}; }}\n"
                        "die() { echo \"$*\" >&2; exit 1; }\n"
                        "kill_pid_file() {" + stopping + "\nkill_pid_file \"$1\" fixture",
                        "fixture", str(race_pid),
                    ], capture_output=True, text=True, timeout=5)
                    already_exited = ps_status == 1 and not ps_error
                    assert (result.returncode == 0) == already_exited, result.stderr
                    assert race_pid.exists() != already_exited
                    if not already_exited:
                        assert "Could not snapshot" in result.stderr, result.stderr

            workspace = fixture / "experiments"
            config = workspace / "hypothesis_fixture" / "experiment_1" / "init" / "init_config.json"
            config.parent.mkdir(parents=True)
            config.write_text('{"agents": []}', encoding="ascii")
            (fixture / ".god" / "current_experiment.json").write_text(json.dumps({
                "hypothesis_id": "fixture", "experiment_id": "1", "workspace_path": str(workspace),
            }), encoding="utf-8")
            previous_port = int(ports["GOD_BACKEND_PORT"])
            ports["GOD_BACKEND_PORT"] = ports["RUNTIME_WEB_PORT"]
            ports["GOD_FRONTEND_PORT"] = ports["RUNTIME_UI_PORT"]
            env_file.write_text(
                "".join(f"{name}={port}\n" for name, port in ports.items())
                + "GOD_LLM_API_KEY=launcher-fixture\nGOD_LLM_MODEL=fixture\n",
                encoding="utf-8",
            )
            with recorded_listener("backend", previous_port) as (owned, pid_file):
                started = run("start")
                output = started.stdout + started.stderr
                assert started.returncode != 0 and "restart" in output and "configured ports" in output, output
                assert pid_file.read_text(encoding="ascii").strip() == str(owned.pid)
                stopped = run("stop")
                assert stopped.returncode == 0, stopped.stderr
                owned.wait(timeout=10)
                assert listener.poll() is None

            # Session preparation runs before the backend connection. Keep that connection local and occupied.
            ports["GOD_BACKEND_PORT"] = str(frontend_port)
            env_file.write_text("".join(f"{name}={port}\n" for name, port in ports.items()), encoding="utf-8")
            env.update(
                BACKEND_ROOT=str(root / "agentsociety"), GOD_AGENT_BACKEND="jiuwenclaw",
                GOD_SESSION_PREFIX="fixture-live", GOD_MAP_ID="pku",
            )
            stock = root / "agentsociety/quick_experiments/hypothesis_god_town/experiment_1/init/init_config.json"
            config.write_bytes(stock.read_bytes())
            prepared = run("session")
            assert f"Port {frontend_port} is occupied" in prepared.stdout + prepared.stderr, prepared
            assert config.read_bytes() == stock.read_bytes(), "the launcher rewrote the experiment template"
            settings = json.loads((config.parents[1] / "run/.god-launch.json").read_text(encoding="utf-8"))
            assert settings["runtime_port"] == int(ports["RUNTIME_AGENT_PORT"])
            assert settings["session_prefix"] == "fixture-live" and settings["map_id"] == "pku"
            print("port conflicts are checked before setup; moved ports preserve ownership; stop leaves unrelated listeners")
        finally:
            if listener.poll() is None:
                listener.terminate()
            listener.wait(timeout=10)


if __name__ == "__main__":
    main()
