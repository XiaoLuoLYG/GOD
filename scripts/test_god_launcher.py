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
                    def quote(value: str) -> str:
                        return "'" + value.replace("'", "''") + "'"

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
            print("port conflicts are checked before setup; moved ports preserve ownership; stop leaves unrelated listeners")
        finally:
            if listener.poll() is None:
                listener.terminate()
            listener.wait(timeout=10)


if __name__ == "__main__":
    main()
