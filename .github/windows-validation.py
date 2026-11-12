import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(sys.argv[1]).resolve()
MODE = sys.argv[2]
EXP = "pku_trump_visit"
INSTANCE = "god-windows-ci"
WORKSPACE = ROOT / "agentsociety" / "windows smoke workspace"
EXP_DIR = WORKSPACE / f"hypothesis_{EXP}" / "experiment_1"
STATE = ROOT / ".god"
BACKEND = "http://127.0.0.1:8001"
FRONTEND = "http://127.0.0.1:5174"
SETUP = BACKEND + "/api/v1/god/setup"
LIVE = BACKEND + f"/api/v1/live-experiments/{EXP}/1"
QUERY = "?" + urlencode({"workspace_path": str(WORKSPACE)})
RUNTIME_PORTS = (19092, 20000, 20001, 6173)
ASK_MARKER = "WINDOWS_LOCAL_ASK_ANSWER"
ASK_QUESTION = "windows_ci_ask_827: What are you doing?"
FIXTURE_CALLS = []
LOG = ROOT / "launcher-output.log"
CMD = ["cmd.exe", "/d", "/c", r"scripts\god.cmd"]
PS = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", r"scripts\god.ps1"]


class LocalModel(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def reply(self, body, content_type="application/json", status=200):
        payload = (json.dumps(body) if content_type == "application/json" else body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self.reply({"object": "list", "data": [{"id": "gpt-4o-mini", "object": "model"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        model = body.get("model", "gpt-4o-mini")
        if self.path.endswith("/embeddings"):
            dimensions = body.get("dimensions", 1536)
            inputs = body.get("input", "")
            count = len(inputs) if isinstance(inputs, list) and inputs and isinstance(inputs[0], (str, list)) else 1
            self.reply({"object": "list", "data": [
                {"object": "embedding", "index": index, "embedding": [0.01] * dimensions}
                for index in range(count)
            ], "model": model, "usage": {"prompt_tokens": 1, "total_tokens": 1}})
            return
        if not self.path.endswith("/chat/completions"):
            self.reply({"error": "Unexpected fixture path"}, status=404)
            return
        messages = json.dumps(body.get("messages", []), ensure_ascii=False)
        is_ask = "windows_ci_ask_827" in messages
        FIXTURE_CALLS.append("ask" if is_ask else "completion")
        content = ASK_MARKER if is_ask else json.dumps({
            "selected_skill_id": "routine.daily", "args": {}, "public_summary": "Windows fixture step"
        })
        metadata = {"id": "chatcmpl-god-ci", "created": 1, "model": model}
        usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
        if body.get("stream"):
            parts = [
                {**metadata, "object": "chat.completion.chunk", "choices": [
                    {"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}
                ]},
                {**metadata, "object": "chat.completion.chunk", "choices": [
                    {"index": 0, "delta": {}, "finish_reason": "stop"}
                ]},
            ]
            if (body.get("stream_options") or {}).get("include_usage"):
                parts.append({**metadata, "object": "chat.completion.chunk", "choices": [], "usage": usage})
            self.reply("".join(f"data: {json.dumps(part)}\n\n" for part in parts) + "data: [DONE]\n\n", "text/event-stream")
        else:
            self.reply({**metadata, "object": "chat.completion", "choices": [
                {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
            ], "usage": usage})


def call(url, payload=None, timeout=15):
    headers = {"Content-Type": "application/json"}
    request = Request(url, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as result:
            body = result.read()
            return json.loads(body) if result.headers.get_content_type() == "application/json" else body
    except HTTPError as error:
        raise AssertionError(f"{url}: HTTP {error.code}: {error.read().decode(errors='replace')}") from error


def live(route, payload=None, timeout=15):
    return call(f"{LIVE}/{route}{QUERY}", payload, timeout=timeout)


def is_open(port):
    for host in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            pass
    return False


def launch(env):
    with LOG.open("wb") as output:
        return subprocess.Popen(CMD + ["start"], cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)


def launcher(command, env, timeout=180):
    print(f"Running {command[-2:]} (Windows)", flush=True)
    result = subprocess.run(command, cwd=ROOT, env=env, timeout=timeout, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.stdout.decode("utf-8", errors="replace")
    print(output, flush=True)
    assert result.returncode == 0, f"{command[-1]} returned {result.returncode}"
    return output


def show_logs():
    for path in [LOG, *sorted((STATE / "logs").glob("*.log"))]:
        if path.is_file():
            raw = path.read_bytes()
            print(f"--- {path.name} ---\n{raw.decode('utf-8-sig', errors='replace')[-14000:]}", flush=True)


def await_setup(process):
    deadline = monotonic() + 1080
    while monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"start exited before setup wizard with {process.returncode}")
        output = LOG.read_bytes()
        if b"Waiting for setup wizard" in output:
            return
        sleep(2)
    raise AssertionError("setup wizard startup timed out")


def status_matches(output, label, port, status):
    assert re.search(rf"^{re.escape(label)}\s+{port} {status}\s*$", output, re.MULTILINE), output


def run():
    subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True)
    subprocess.run(PS[:-2] + ["-Command", "$PSVersionTable.PSVersion.ToString()"], cwd=ROOT, check=True)
    assert os.name == "nt"
    native_path_test = r"""
$tokens = $null
$parseErrors = $null
$source = (Resolve-Path -LiteralPath 'scripts\god.ps1').Path
$ast = [System.Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw "Could not parse god.ps1: $parseErrors" }
$definition = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Update-ProcessPath' }, $true)
if ($null -eq $definition) { throw 'Update-ProcessPath was not found' }
. ([ScriptBlock]::Create($definition.Extent.Text))
$nodeBefore = (Get-Command node.exe).Source
$npmBefore = (Get-Command npm.cmd).Source
Write-Host "Original normal runner PATH length: $($env:Path.Length)"
$stablePath = $null
foreach ($appendCount in 1..5) {
  Update-ProcessPath
  if ($appendCount -eq 1) { $stablePath = $env:Path }
  elseif ($stablePath -cne $env:Path) { throw 'Update-ProcessPath changed PATH on a repeated call' }
  if ((Get-Command node.exe).Source -ne $nodeBefore -or (Get-Command npm.cmd).Source -ne $npmBefore) {
    throw 'Update-ProcessPath changed tool lookup precedence'
  }
  cmd.exe /d /c node --version
  if ($LASTEXITCODE -ne 0) { throw 'Nested cmd.exe failed to resolve node' }
}
Write-Host "PASS idempotent Windows PATH refresh and nested cmd.exe node lookup (5 calls; $($env:Path.Length) characters)"
$wrapper = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Invoke-NativeCommand' }, $true)
if ($null -eq $wrapper) { throw 'Invoke-NativeCommand was not found' }
. ([ScriptBlock]::Create($wrapper.Extent.Text))
$probeFile = Join-Path $env:RUNNER_TEMP 'god-stdin-assert.py'
$probeLog = Join-Path $env:RUNNER_TEMP 'god-stdin-assert.log'
Set-Content -LiteralPath $probeFile -Encoding Ascii -Value "import sys; print(' '.join(line.hex() for line in sys.stdin.buffer.read().splitlines() if line))"
$uv = (Get-Command uv.exe).Source
$beforeEncoding = $OutputEncoding
$beforeConsoleInput = [Console]::InputEncoding
$cases = [ordered]@{ "en`n" = '656e'; "zh`n" = '7a68'; "yes`nen`n" = '796573 656e' }
foreach ($sample in $cases.GetEnumerator()) {
  Remove-Item -LiteralPath $probeLog -ErrorAction SilentlyContinue
  $sample.Key | Invoke-NativeCommand -FilePath $uv -ArgumentList @('run', '--no-project', 'python', $probeFile) -LogPath $probeLog
  if ($LASTEXITCODE -ne 0) { throw "Native stdin probe failed: $LASTEXITCODE" }
  $actualBytes = (Get-Content -LiteralPath $probeLog -Encoding UTF8 -Raw).Trim()
  if ($actualBytes -ne $sample.Value) { throw "Native stdin has unexpected bytes: $actualBytes; expected $($sample.Value)" }
  if (-not [object]::ReferenceEquals($beforeEncoding, $OutputEncoding)) { throw 'Invoke-NativeCommand changed caller OutputEncoding' }
  if ($beforeConsoleInput.CodePage -ne [Console]::InputEncoding.CodePage -or $beforeConsoleInput.GetPreamble().Length -ne [Console]::InputEncoding.GetPreamble().Length) {
    throw 'Invoke-NativeCommand changed the caller console input encoding'
  }
}
Write-Host 'PASS exact PowerShell wrapper sends BOM-free en, zh, and yes/en to native uv subprocesses'
"""
    subprocess.run(PS[:-2] + ["-Command", native_path_test], cwd=ROOT, check=True)
    assert not (ROOT / ".env").exists() and not (STATE / "current_experiment.json").exists()
    source = ROOT / "agentsociety" / "quick_experiments" / f"hypothesis_{EXP}" / "experiment_1"
    shutil.copytree(source / "init", EXP_DIR / "init")
    config_path = EXP_DIR / "init" / "init_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["agents"] = config["agents"][:1]
    config["agents"][0]["kwargs"]["request_timeout"] = 50
    world = config["env_modules"][0]["kwargs"]
    world["agent_id_name_pairs"] = world["agent_id_name_pairs"][:1]
    world["initial_locations"] = {"1": world["initial_locations"]["1"]}
    config["codegen_router"]["final_summary_enabled"] = False
    if MODE == "external":
        config["agent_backend"] = {"type": "openai_compat"}
    config_path.write_text(json.dumps(config), encoding="utf-8")

    model = ThreadingHTTPServer(("127.0.0.1", 0), LocalModel)
    Thread(target=model.serve_forever, daemon=True).start()
    api_base = f"http://127.0.0.1:{model.server_port}/v1"
    env = dict(os.environ, GOD_OPEN_BROWSER="0", GOD_LIVE_STEP_TIMEOUT="90", GOD_BACKEND_START_TIMEOUT="150",
               AGENTSOCIETY_LIVE_INTERACTION_TIMEOUT="75", LIVE_WORKSPACE_PATH=str(WORKSPACE),
               RUNTIME_INSTANCE=INSTANCE, RUNTIME_LANGUAGE="en", GOD_EXTRA_STOP_PORTS="29193",
               JIUWENSWARM_HOME=str(ROOT / "swarm-home"), PYTHONUTF8="1")
    legacy = ROOT / "legacy runtime workspace"
    if MODE == "migration":
        registry = Path.home() / ".jiuwenclaw" / "instances.yaml"
        assert not registry.exists(), f"unexpected existing registry {registry}"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps({"instances": {INSTANCE: {"workspace": str(legacy)}}}), encoding="utf-8")
        sentinel = legacy / "agent" / "jiuwenclaw_workspace" / "windows-ci-marker.txt"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("legacy data\n", encoding="utf-8")

    process = launch(env)
    try:
        await_setup(process)
        setup_status = call(SETUP + "/status")
        assert setup_status["setup_mode"] and setup_status["needs_setup"], setup_status
        assert setup_status["current_experiment"] is None
        assert call(FRONTEND + "/setup"), "Vite did not serve /setup"
        assert all(not is_open(port) for port in RUNTIME_PORTS), "setup should leave runtime ports closed"
        assert (ROOT / ".env").is_file()
        print("PASS fresh wizard, .env creation, frontend /setup, and runtime ports closed during wizard", flush=True)
        saved = call(SETUP + "/model-config", {
            "GOD_LLM_API_KEY": "sk-windows-local-fixture-827", "GOD_LLM_API_BASE": api_base,
            "GOD_LLM_MODEL": "gpt-4o-mini", "GOD_EMBEDDING_MODEL": "text-embedding-3-small",
        })
        assert "sk-windows-local-fixture-827" not in json.dumps(saved), "wizard leaked synthetic key"
        selection = call(SETUP + "/start-default", {"experiment_key": EXP})
        assert selection["hypothesis_id"] == EXP and selection["map_id"] == "pku"
        assert selection["start_request"]["hypothesis_id"] == EXP
        print("PASS model configuration with key redaction and selection of the PKU experiment", flush=True)
        start_code = process.wait(timeout=900)
        if start_code != 0:
            print(f"Native start exit: {start_code} ({start_code & 0xffffffff:#010x})", flush=True)
            native_log = LOG.read_bytes()
            if b"brains\\config.py" in native_log and b"Command failed" in native_log:
                checker = Path("packages/agentsociety2/agentsociety2/agent/brains/config.py")
                result = subprocess.run(
                    ["uv", "run", "--no-project", "--managed-python", "python", str(checker), str(config_path)],
                    cwd=ROOT / "agentsociety", env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
                )
                print(f"Direct gate immediately after failure: exit={result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}", flush=True)
        assert start_code == 0, "launcher start returned failure"
        assert (STATE / "run" / "start-request.json.consumed").exists(), "setup start request was not consumed"
        state = live("status")
        assert state["hypothesis_id"] == EXP and state["step_count"] == 1 and not state["error"], state
        assert call(FRONTEND + f"/pixel-replay/{EXP}/1")
        persisted = call(SETUP + "/status")
        assert not persisted["setup_mode"] and not persisted["needs_setup"], persisted
        assert persisted["selected_map_id"] == "pku"
        print(f"PASS consumed request and primed first live step: {state}", flush=True)
        status = launcher(PS + ["status"], env)
        status_matches(status, "Backend", 8001, "up")
        status_matches(status, "Control room", 5174, "up")
        assert re.search(rf"Experiment:\s+{EXP} / experiment_1", status)
        expected = MODE != "external"
        for port in RUNTIME_PORTS:
            assert is_open(port) == expected, f"unexpected runtime port state: {port}"
        if MODE == "external":
            assert not (ROOT / "jiuwenclaw" / ".venv").exists(), "external selection installed the runtime"
            assert not (STATE / "pids" / "runtime.pid").exists()
            assert "completion" in FIXTURE_CALLS, "first step did not use external decision backend"
        if MODE == "migration":
            assert sentinel.read_text(encoding="utf-8") == "legacy data\n"
            assert (legacy / "agent" / "workspace" / sentinel.name).read_text(encoding="utf-8") == "legacy data\n"
            assert (legacy / "config" / "config.yaml").is_file()
        print(f"PASS expected runtime selection, port state, and persistence ({MODE})", flush=True)
        answer = live("ask", {
            "question": ASK_QUESTION, "target": {"type": "agent", "agent_id": 1}, "response_language": "en"
        }, timeout=100)
        assert answer["step_count"] == 1 and ASK_MARKER in answer["result"], answer
        assert "ask" in FIXTURE_CALLS
        print(f"PASS targeted Ask returned the localhost fixture response ({MODE})", flush=True)
        launcher(CMD + ["start"], env, timeout=240)
        assert live("status")["step_count"] == 1, "idempotent start primed again"
        print("PASS idempotent start reused live session and did not prime a second step", flush=True)
        launcher(PS + ["stop"], env)
        assert all(not is_open(port) for port in (8001, 5174, *RUNTIME_PORTS)), "stop left a service listening"
        assert not list((STATE / "pids").glob("*.pid")), "stop left PID files"
        print("PASS native PowerShell stop released all service ports and PID files", flush=True)
        if MODE == "external":
            setup = launcher(CMD + ["setup"], env)
            assert "Syncing backend Python dependencies" in setup and "Syncing agent runtime" not in setup
            assert not (ROOT / "jiuwenclaw" / ".venv").exists()
            assert all(not is_open(port) for port in (8001, 5174, *RUNTIME_PORTS))
            print("PASS dependency-only setup honors selected external backend and leaves services stopped", flush=True)
    except BaseException:
        show_logs()
        raise
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            subprocess.run(PS + ["stop"], cwd=ROOT, env={**env, "GOD_SKIP_SETUP": "1"},
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=40)
        except subprocess.TimeoutExpired:
            print("Timed out during best-effort runner cleanup", flush=True)
        model.shutdown()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    run()
