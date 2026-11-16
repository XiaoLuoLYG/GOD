"""Exercise launcher stop and startup against an unrelated local listener."""

import base64
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
            GOD_SKIP_SETUP="1", GOD_OPEN_BROWSER="0", SCREENDIR=str(screen_dir),
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

            def run(action: str) -> subprocess.CompletedProcess:
                return subprocess.run(
                    [*command, action], cwd=fixture, env=env, capture_output=True,
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

            started = run("start")
            output = started.stdout + started.stderr
            assert started.returncode != 0, output
            assert f"Port {frontend_port} is occupied" in output and "GOD_FRONTEND_PORT" in output, output
            assert listener.poll() is None, "start killed the process that owns the port"
            status = run("status")
            assert status.returncode == 0 and f"{frontend_port} occupied" in status.stdout, status.stdout

            runtime_port = int(ports["RUNTIME_AGENT_PORT"])
            runtime_log = fixture / ".god" / "logs" / "runtime.log"
            runtime = [sys.executable, "-u", "-c", serve, str(runtime_port)]
            if windows:
                def quote(value: str) -> str:
                    return "'" + value.replace("'", "''") + "'"

                encoded = base64.b64encode(
                    ("& " + " ".join(map(quote, runtime)) + " >> " + quote(str(runtime_log))).encode("utf-16le")
                ).decode("ascii")
                owned = subprocess.Popen(["powershell.exe", "-NoProfile", "-EncodedCommand", encoded])
            else:
                with runtime_log.open("w", encoding="utf-8") as log:
                    owned = subprocess.Popen(runtime, stdout=log, stderr=log)
            try:
                (fixture / ".god" / "pids" / "runtime.pid").write_text(f"{owned.pid}\n", encoding="ascii")
                for _ in range(50):
                    try:
                        with socket.create_connection(("127.0.0.1", runtime_port), timeout=0.3):
                            break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise AssertionError("the fixture's GOD service did not start")
                status = run("status")
                assert status.returncode == 0 and f"{runtime_port} up" in status.stdout, status.stdout + status.stderr
                stopped = run("stop")
                assert stopped.returncode == 0, stopped.stderr
                owned.wait(timeout=10)
                assert listener.poll() is None
            finally:
                if owned.poll() is None:
                    if windows:
                        subprocess.run(["taskkill", "/PID", str(owned.pid), "/T", "/F"], capture_output=True)
                    else:
                        owned.terminate()
                    owned.wait(timeout=10)
            print("start and status identified the port conflict, and stop cleaned up only the recorded service")
        finally:
            if listener.poll() is None:
                listener.terminate()
            listener.wait(timeout=10)


if __name__ == "__main__":
    main()
