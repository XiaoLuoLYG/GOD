# GOD Quick Start

The shortest path from a clean machine to the setup wizard and then a live GOD control room.

> Chinese version: [QUICKSTART.zh-CN.md](QUICKSTART.zh-CN.md)

---

## 1. Prerequisites

You will need:

- Python 3.11+
- Node.js & `npm`
- [`uv`](https://docs.astral.sh/uv/)
- `screen` (recommended; keeps local services running cleanly)

macOS:

```bash
brew install python node uv screen
```

Sanity check:

```bash
python3 --version && npm --version && uv --version
```

## 2. Clone

```bash
git clone https://github.com/XiaoLuoLYG/GOD.git
cd GOD
```

## 3. Start

```bash
./scripts/god.sh start
```

`start` is the normal one-command path. It is idempotent, so running it again reuses services that are already up.

On first run, GOD will:

1. Create `.env` from `.env.example`.
2. Install Python + Node dependencies.
3. Start the setup backend/control room.
4. Open the browser setup wizard at `/setup`.
5. Wait for you to save model settings and choose a launch path.
6. Bring up the full stack, create a live session, run the first step, and open the control room.

<p align="center">
  <img src="docs/assets/screenshots/02-setup-wizard-en.png" alt="GOD setup wizard" width="100%" />
</p>


In the wizard you can choose either path:

- **Save Model and Run Default** launches the built-in GOD Town baseline immediately.
- **Save and Configure Params** lets you describe a scenario, generate an editable experiment draft, adjust agents/steps, and then click **Save and Launch**.

Three settings are required:

| Variable | Example |
| --- | --- |
| `GOD_LLM_API_KEY` | `sk-...` |
| `GOD_LLM_API_BASE` | `https://api.openai.com/v1` |
| `GOD_LLM_MODEL` | `gpt-5.4` |

Any OpenAI-compatible endpoint works. The API key is saved only in local `.env`; the browser only receives redacted status.

To create another experiment later, run:

```bash
./scripts/god.sh configure
```

## 4. Open the control room

When startup finishes, the script opens the control room and prints a URL like:

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

`new-run` stops services, wipes the previous replay/run state, and starts a clean live session.

## 7. Day-to-day commands

```bash
./scripts/god.sh start     # idempotent; reuses running services
./scripts/god.sh setup     # install/check dependencies only
./scripts/god.sh configure # create a new experiment through the setup wizard
./scripts/god.sh restart   # stop everything cleanly, then start again
./scripts/god.sh new-run   # wipe replay data and start a fresh session
./scripts/god.sh status    # print URLs, ports, and model status
./scripts/god.sh stop      # stop everything
./scripts/god.sh tail      # follow logs
./scripts/god.sh open      # open the frontend pages in the browser
```
