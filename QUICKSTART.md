# GOD Quick Start

The shortest path from a clean machine to a live GOD control room.

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

The first run will:

1. Create `.env` from `.env.example`.
2. Prompt for the LLM API key, API base URL, and model name.
3. Install Python + Node dependencies.
4. Bring up the full stack, create a live session, and run the first step.

Three settings are required:

| Variable | Example |
| --- | --- |
| `GOD_LLM_API_KEY` | `sk-...` |
| `GOD_LLM_API_BASE` | `https://api.openai.com/v1` |
| `GOD_LLM_MODEL` | `gpt-5.4` |

Any OpenAI-compatible endpoint works.

## 4. Open the control room

When startup finishes, the script prints a URL like:

```text
http://127.0.0.1:5174/pixel-replay/god_town/1
```

Open it. You should see the pixel town, the resident roster, step controls, and the live console.

## 5. Verify

```bash
./scripts/god.sh status
```

You should see every service marked `up`.

## 6. Run a fresh experiment

If the UI shows old replay data, reset and re-run:

```bash
./scripts/god.sh new-run
```

This wipes the previous run and starts a clean live session.

## 7. Day-to-day commands

```bash
./scripts/god.sh start    # idempotent; reuses running services
./scripts/god.sh restart  # stop everything cleanly, then start again
./scripts/god.sh stop     # stop everything
./scripts/god.sh tail     # follow logs
./scripts/god.sh open     # open the control room in the browser
```
