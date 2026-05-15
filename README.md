<h1 align="center">
  <img src="docs/assets/logo_no_bg.png" alt="GOD logo" height="32" />
  &nbsp;GOD · Govern · Observe · Direct
</h1>

<p align="center">
  <img src="docs/assets/screenshots/00-hero.png" alt="GOD — Govern · Observe · Direct" width="100%" />
</p>
<p align="center">
  <b>🌩️ Be like a god to a town of agents.</b><br/>
  Pause time. Whisper to a soul. Bend the next step. Reset the world — all from a single click.
</p>


<p align="center">
  <a href="#-quick-start"><b>🚀 Quick Start</b></a> ·
  <a href="#-highlights">Highlights</a> ·
  <a href="#-features">Features</a> ·
  <a href="#%EF%B8%8F-how-it-works">How it works</a> ·
  <a href="#-default-experiment">Default Experiment</a> ·
  <a href="#%EF%B8%8F-roadmap">Roadmap</a> ·
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="README.zh-CN.md">🌏 中文</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img alt="React" src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black" />
  <img alt="Vite" src="https://img.shields.io/badge/Vite-6-646CFF?style=flat-square&logo=vite&logoColor=white" />
  <img alt="No-Code Setup" src="https://img.shields.io/badge/setup-no--code-22c55e?style=flat-square&logo=googlechrome&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square" />
  <img alt="PRs welcome" src="https://img.shields.io/badge/PRs-welcome-14b8a6?style=flat-square" />
  <img alt="Status" src="https://img.shields.io/badge/status-alpha-orange?style=flat-square" />
</p>

---

> Other generative-agent projects let you **watch**.
> **GOD lets you reign.**
>
> One screen. Pause time. Question any soul. Rewrite the next step. Restart the world.
> The missing operator console for a society of agents — alive while you steer it.

## ✨ Highlights

<table>
<tr>
  <td align="center" width="20%">⏯️<br/><b>Pause time</b><br/><sub>Stop, scrub, fast-forward, auto-play any live step.</sub></td>
  <td align="center" width="20%">💬<br/><b>Whisper to anyone</b><br/><sub>Ask one resident, a group, or the whole town — mid-run.</sub></td>
  <td align="center" width="20%">🎛️<br/><b>Bend the next step</b><br/><sub>Inject instructions and watch agents react in real time.</sub></td>
  <td align="center" width="20%">🪄<br/><b>No-code setup</b><br/><sub>Configure model, scenario and agents from a browser wizard.</sub></td>
  <td align="center" width="20%">🔄<br/><b>Reset reality</b><br/><sub>One command wipes a stale run and re-seeds a clean world.</sub></td>
</tr>
</table>

## 🖼️ Screenshots

<p align="center">
  <img src="docs/assets/screenshots/01-control-room.png" alt="GOD control room" width="94%" />
</p>

<p align="center"><sub>Live control room — pixel town, step controls, targeted ask, and resident roster in one view.</sub></p>

## 🚀 Quick Start

```bash
git clone https://github.com/XiaoLuoLYG/GOD.git
cd GOD
./scripts/god.sh start
```

That's it. On first run, the script installs everything, opens a **browser-based setup wizard**, and waits for you. No `.env` editing, no command-line flags, no glue scripts.

<p align="center">
  <img src="docs/assets/screenshots/02-setup-wizard-en.png" alt="GOD setup wizard" width="100%" />
</p>


<p align="center"><sub>The Setup Wizard — five guided steps from blank machine to a live society.</sub></p>

<table>
<tr>
  <td align="center" width="20%">🔌<br/><b>1. Model</b><br/><sub>Paste an OpenAI-compatible API key, base URL, and model name.</sub></td>
  <td align="center" width="20%">🧪<br/><b>2. Scenario</b><br/><sub>Describe your world — date, weather, vibes, rules.</sub></td>
  <td align="center" width="20%">🤖<br/><b>3. Generate</b><br/><sub>The GOD agent drafts agent profiles and a step plan.</sub></td>
  <td align="center" width="20%">✏️<br/><b>4. Edit</b><br/><sub>Tweak personalities, relationships, locations, or steps.</sub></td>
  <td align="center" width="20%">▶️<br/><b>5. Launch</b><br/><sub>Save as a new experiment copy and step into the control room.</sub></td>
</tr>
</table>

Any OpenAI-compatible endpoint works. When the wizard hands off, the script prints a URL like:

```text
http://127.0.0.1:5174/pixel-replay/god_town/1
```

Full walkthrough: **[Quickstart →](QUICKSTART.md)**

## 🧩 Features

|     | Feature | What you get |
| --- | --- | --- |
| 🎬 | **Replay control** | Scrub a live or recorded run by step. Pause, jump, auto-play. |
| 💬 | **Targeted ask** | Send a natural-language question to one agent, a group, or the whole town. |
| 🎛️ | **Real-time intervention** | Inject instructions into the *next* step — the agents read them on their next turn. |
| 🪄 | **No-code setup wizard** | Browser-based: configure model + scenario, let GOD generate agents and steps, edit, then launch. |
| 🧼 | **One-command reset** | Wipe replay data and seed a clean society without leaving the terminal. |
| 🗺️ | **Pixel town world** | A live tiled map: locations, actions, messages, statuses — every step replay-friendly. |
| 🧱 | **Single config, hackable** | One `.env`, one script. No Docker. Edit, reload, ship. |

## 🏗️ How It Works

```mermaid
flowchart LR
  O["Operator"]:::operator
  UI["Control Room"]:::surface
  API["Live API"]:::core
  RT["Agent Runtime"]:::runtime
  TOWN["Pixel Town"]:::world
  CFG[["Experiment Files"]]:::data
  DB[("Replay Store")]:::data

  O --> UI
  UI <-->|"commands / updates"| API
  API -->|"prompts"| RT
  RT -->|"actions"| TOWN
  TOWN -->|"frames"| DB
  CFG -->|"scenario"| API

  classDef operator fill:#fff7ed,stroke:#f59e0b,color:#7c2d12,stroke-width:2px;
  classDef surface fill:#eef2ff,stroke:#6366f1,color:#312e81,stroke-width:2px;
  classDef core fill:#ecfeff,stroke:#0891b2,color:#164e63,stroke-width:2px;
  classDef runtime fill:#f0fdf4,stroke:#22c55e,color:#14532d,stroke-width:2px;
  classDef world fill:#fefce8,stroke:#ca8a04,color:#713f12,stroke-width:2px;
  classDef data fill:#fdf2f8,stroke:#db2777,color:#831843,stroke-width:2px;
```

GOD is intentionally local-first: the control room, backend, runtime bridge, experiment files, and replay store all run on your machine. The model endpoint is the only external service you choose.

| Layer | What it does |
| --- | --- |
| 🎮 **Control Room** | React/Vite browser UI — replay, ask, intervention, status. |
| ⚙️ **Backend** | Local FastAPI service exposing live and replay APIs. |
| 🗺️ **Pixel Town** | Replay-friendly social world: locations, actions, messages, agent status. |
| 🤖 **Agent Runtime** | Out-of-process LLM agents reached over a local WebSocket. |

## ⚙️ Commands

```bash
./scripts/god.sh start      # start the full stack (idempotent)
./scripts/god.sh configure  # open the setup wizard for a new experiment copy
./scripts/god.sh restart    # stop everything cleanly, then start again
./scripts/god.sh new-run    # wipe replay data and start a fresh session
./scripts/god.sh status     # ports, URLs, model status
./scripts/god.sh stop       # stop everything
./scripts/god.sh tail       # follow logs
./scripts/god.sh open       # open the frontend pages in the default browser
```

## 🧪 Default Experiment


### 🏘️ An ordinary weekday in The Ville

A late-spring Tuesday morning at 8:20. Sunny, 18°C, light breeze. A 200-person town with **10 residents who know each other but don't live in each other's pockets** — a slice-of-life simulation, not a quest script.

➡️ **Tweak everything from the Setup Wizard, or drop your own config into `quick_experiments/` and point `GOD_EXPERIMENT` at it.**

➡️ See [`hypothesis_god_town/experiment_1/`](agentsociety/quick_experiments/hypothesis_god_town/experiment_1/README.md) for the full breakdown of locations, profiles, and interactions.

<table>
<tr><td colspan="5" align="center"><b>🗺️ 10 Locations · 65 location-scoped interactions</b></td></tr>
<tr>
  <td align="center" width="20%">🏠<br/><b>Home</b><br/><sub>cook · sleep · tidy · read · WFH · video-call</sub></td>
  <td align="center" width="20%">🏫<br/><b>School</b><br/><sub>attend / teach class · grade · office hours</sub></td>
  <td align="center" width="20%">📚<br/><b>Library</b><br/><sub>read · study · research · borrow / return</sub></td>
  <td align="center" width="20%">☕<br/><b>Hobbs Cafe</b><br/><sub>light meal · coffee chat · cafe shift · meetup</sub></td>
  <td align="center" width="20%">🌳<br/><b>Johnson Park</b><br/><sub>walk · meet · exercise · public announcement</sub></td>
</tr>
<tr>
  <td align="center" width="20%">🛠️<br/><b>Supply Store</b><br/><sub>repair · restock · lend tools · customer service</sub></td>
  <td align="center" width="20%">🛒<br/><b>Market</b><br/><sub>buy food · haggle · deliver · chat w/ regulars</sub></td>
  <td align="center" width="20%">💊<br/><b>Pharmacy</b><br/><sub>buy medicine · refill · check BP · home visit prep</sub></td>
  <td align="center" width="20%">🍻<br/><b>Pub</b><br/><sub>socialize · watch match · host small event</sub></td>
  <td align="center" width="20%">🛏️<br/><b>Dorm</b><br/><sub>rest · self-study · common-room hangout · video call</sub></td>
</tr>
</table>

<table>
<tr><td colspan="5" align="center"><b>👥 10 residents — each with a real life</b></td></tr>
<tr>
  <td align="center" width="20%">🧭<br/><b>Alice</b> · 34<br/><sub>Neighborhood coordinator</sub></td>
  <td align="center" width="20%">🛠️<br/><b>Bob</b> · 45<br/><sub>Supply-store shopkeeper</sub></td>
  <td align="center" width="20%">📖<br/><b>Charlie</b> · 39<br/><sub>High-school history teacher</sub></td>
  <td align="center" width="20%">💊<br/><b>Dana</b> · 41<br/><sub>Pharmacy nurse</sub></td>
  <td align="center" width="20%">☕<br/><b>Elena</b> · 36<br/><sub>Cafe owner</sub></td>
</tr>
<tr>
  <td align="center" width="20%">🎒<br/><b>Farah</b> · 16<br/><sub>High-school student</sub></td>
  <td align="center" width="20%">📮<br/><b>George</b> · 68<br/><sub>Retired postman</sub></td>
  <td align="center" width="20%">💻<br/><b>Hana</b> · 28<br/><sub>Remote software engineer</sub></td>
  <td align="center" width="20%">🦺<br/><b>Ivan</b> · 52<br/><sub>Public-safety volunteer</sub></td>
  <td align="center" width="20%">🍅<br/><b>Mei</b> · 47<br/><sub>Market vegetable vendor</sub></td>
</tr>
</table>

<sub>Every resident carries a full profile: age, family, housing, economic status, health, daily routine, skills, needs, worries, secrets, social network, language style, quirks, short- & long-term goals.</sub>

## 🗺️ Pluggable Map Packages

GOD now discovers map packages automatically from `agentsociety/custom/maps/<map_id>/`. To add a map, copy [`agentsociety/custom/maps/_template/`](agentsociety/custom/maps/_template/), replace `map.yaml`, `visuals/map.json`, tileset PNGs, and optional `characters/` or `location_assets/`, then run:

```bash
cd agentsociety
uv run python scripts/validate_map_package.py custom/maps/<map_id>
```

The setup wizard will list valid packages without code changes. v1 supports Tiled JSON maps with PNG tilesets and a `Collisions` layer where `0` means walkable. See [docs/MAP_PACKAGES.md](docs/MAP_PACKAGES.md) for the full package contract.

## 🛣️ Roadmap

### ✅ Recently shipped

| | |
| --- | --- |
| 🗺️ **Pluggable map packages** | Drop a folder under `agentsociety/custom/maps/<map_id>/`, refresh the wizard, and a new world is selectable. Auto-discovered, validated, hot-swappable. See [`docs/MAP_PACKAGES.md`](docs/MAP_PACKAGES.md). |
| 🪄 **No-code setup wizard** | A 5-step browser flow that turns a blank machine into a live society — no `.env` edits, no command-line flags. |
| 🧪 **Scripted experiments** | Ship reproducible experiments as plain folders under `quick_experiments/<hypothesis>/<experiment>/`. Point `GOD_EXPERIMENT` at one and run. |

### 🛣️ Next

| | |
| --- | --- |
| 🤖 **Pluggable agent runtimes** | Swap LLM runtimes and persona templates as cleanly as we now swap maps. |
| 🧪 **Multi-experiment orchestration** | Run experiments, control groups, and repeats side-by-side. |
| 🗺️ **Live map generation** | Maps that evolve with events, repairs, blockages, crowds. |
| 🌦️ **Event-responsive worlds** | Weather, accidents, festivals, rumors, shortages. |
| 🌐 **Large-scale simulation** | AgentSociety batching, sharded runs, sampled replay. |
| 📊 **Experiment evaluation** | Cross-run metrics, behavior diffs, intervention analysis. |
| 📝 **Operator workflow** | Per-step notes, tags, bookmarks, key-event summaries. |
| 🌍 **Hosted demo & scenario sharing** | Public demo, experiment & map templates. |

Have an idea? [Open an issue or PR](#-contributing).

## 🤝 Contributing

Issues and pull requests are very welcome. To set up a dev environment:

```bash
./scripts/god.sh start
```

That installs Python and Node dependencies, brings up the full stack, creates a live session, and runs the first step so the control room opens on a populated town. From there, edit and reload.

Full guide: **[CONTRIBUTING.md →](CONTRIBUTING.md)** — branching, PR checklist, style, and how to ship a new map or experiment.

## 🙌 Acknowledgements

GOD stands on the shoulders of open research and open-source. It bundles two trimmed, integrated upstream checkouts:

- [AgentSociety](https://github.com/tsinghua-fib-lab/AgentSociety) — large-scale generative-agent simulation framework.
- [JiuwenClaw](https://github.com/openJiuwen-ai/jiuwenclaw) — out-of-process agent runtime.

And takes inspiration from [Generative Agents](https://arxiv.org/abs/2304.03442) and [OASIS](https://github.com/camel-ai/oasis).

## 📚 Citation

```bibtex
@article{piao2025agentsociety,
  title   = {AgentSociety: Large-Scale Simulation of LLM-Driven Generative Agents Advances Understanding of Human Behaviors and Society},
  author  = {Piao et al.},
  journal = {arXiv preprint arXiv:2502.08691},
  year    = {2025}
}

@misc{park2023generativeagents,
  title         = {Generative Agents: Interactive Simulacra of Human Behavior},
  author        = {Joon Sung Park and Joseph C. O'Brien and Carrie J. Cai and Meredith Ringel Morris and Percy Liang and Michael S. Bernstein},
  year          = {2023},
  eprint        = {2304.03442},
  archivePrefix = {arXiv},
  primaryClass  = {cs.HC},
  url           = {https://arxiv.org/abs/2304.03442}
}
```

## ⭐ Star History

<a href="https://star-history.com/#XiaoLuoLYG/GOD&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=XiaoLuoLYG/GOD&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=XiaoLuoLYG/GOD&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=XiaoLuoLYG/GOD&type=Date" />
  </picture>
</a>

## 📄 License

Released under the [Apache-2.0](LICENSE) license. Upstream LICENSE and NOTICE files are kept inside the integrated runtime checkouts and apply to those subtrees.

<p align="center"><sub>Built with care. ⭐ a star helps GOD grow.</sub></p>
