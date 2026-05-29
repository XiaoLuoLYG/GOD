# GOD Quick Start

The shortest path from a clean machine to the setup wizard and then a live GOD control room.

> Chinese version: [QUICKSTART.zh-CN.md](QUICKSTART.zh-CN.md)

---

## 1. Prerequisites

You will need:

- macOS/Linux: Python 3.11+, Node.js & `npm`, [`uv`](https://docs.astral.sh/uv/), and `screen`
- Windows: PowerShell 5.1+ and `winget`; the startup script installs missing Git, Node.js LTS/npm, and `uv`

macOS:

```bash
brew install python node uv screen
```

If `git clone` is not available on Windows yet, install Git first with `winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements` or download the repository ZIP.

## 2. Clone

```bash
git clone https://github.com/XiaoLuoLYG/GOD.git
cd GOD
```

## 3. Start

macOS/Linux:

```bash
./scripts/god.sh start
```

Windows PowerShell:

```powershell
.\scripts\god.cmd start
```

`start` is the normal one-command path. It is idempotent, so running it again reuses services that are already up.

On first run, GOD will:

1. Create `.env` from `.env.example`.
2. Install Python + Node dependencies.
3. Start the setup backend/control room.
4. Open the browser setup wizard at `/setup`.
5. Wait for you to save model settings and choose an experiment.
6. Bring up the full stack for that current experiment, create a live session, run the first step, and open the control room.

<p align="center">
  <img src="docs/assets/screenshots/02-setup-wizard-en.png" alt="GOD setup wizard" width="100%" />
</p>


In the wizard you can choose one of three paths:

- **Open GOD Town** launches the built-in The Ville baseline.
- **Open PKU Trump Visit** launches the built-in PKU campus experiment.
- **Create Custom Experiment** lets you describe a scenario, generate an editable experiment draft, adjust agents/steps, and then click **Save and Launch**.

Three settings are required:

| Variable | Example |
| --- | --- |
| `GOD_LLM_API_KEY` | `sk-...` |
| `GOD_LLM_API_BASE` | `https://api.openai.com/v1` |
| `GOD_LLM_MODEL` | `gpt-5.4` |

Any OpenAI-compatible endpoint works. The API key is saved only in local `.env`; the browser only receives redacted status. Experiment selection is saved separately in `.god/current_experiment.json`, so `.env` does not control which map or experiment starts.

To switch between built-in experiments or create another experiment later, run:

```bash
./scripts/god.sh configure
```

## 4. Open the control room

When startup finishes, the script opens the control room for the current experiment and prints a URL like:

```text
http://127.0.0.1:5174/pixel-replay/god_town/1
```

If the browser did not open automatically, open that URL. You should see the pixel town, the resident roster, step controls, and the live console.

## 5. Verify

```bash
./scripts/god.sh status
```

You should see every service marked `up`.

## 6. Restart or run fresh

Use `restart` when you want a clean process restart without wiping the current run:

```bash
./scripts/god.sh restart
```

Use `new-run` when the UI shows old replay data or you want a fresh live session:

```bash
./scripts/god.sh new-run
```

`new-run` prints the current experiment run directory, stops services, wipes only that current run state, and starts a clean live session.

## 7. Day-to-day commands

```bash
./scripts/god.sh start     # idempotent; reuses running services
./scripts/god.sh setup     # install/check dependencies only
./scripts/god.sh configure # switch built-in experiments or create a custom one
./scripts/god.sh restart   # stop everything cleanly, then start again
./scripts/god.sh new-run   # wipe the current experiment run and start fresh
./scripts/god.sh status    # print URLs, ports, and model status
./scripts/god.sh stop      # stop everything
./scripts/god.sh tail      # follow logs
./scripts/god.sh open      # open the frontend pages in the browser
```

On Windows, replace `./scripts/god.sh` with `.\scripts\god.cmd`.
