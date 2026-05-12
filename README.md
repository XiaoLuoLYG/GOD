<h1 align="center">
  <img src="docs/assets/brand/logo.png" alt="GOD logo" height="32" />
  GOD · Govern · Observe · Direct
</h1>

<p align="center">
  <img src="docs/assets/screenshots/00-hero.png" alt="GOD — Govern · Observe · Direct" width="100%" />
</p>

<p align="center">
  <b>A real-time control room for agent societies.</b><br/>
  Watch a live pixel-town of LLM agents. Ask any of them. Steer the simulation step by step.
</p>

<p align="center">
  <a href="#-quick-start"><b>Quick Start</b></a> ·
  <a href="#-highlights">Highlights</a> ·
  <a href="#-features">Features</a> ·
  <a href="#%EF%B8%8F-how-it-works">How it works</a> ·
  <a href="#%EF%B8%8F-roadmap">Roadmap</a> ·
  <a href="README.zh-CN.md">中文</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img alt="React" src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black" />
  <img alt="Vite" src="https://img.shields.io/badge/Vite-6-646CFF?style=flat-square&logo=vite&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square" />
  <img alt="PRs welcome" src="https://img.shields.io/badge/PRs-welcome-14b8a6?style=flat-square" />
  <img alt="Status" src="https://img.shields.io/badge/status-alpha-orange?style=flat-square" />
</p>

---

> Most generative-agent projects ship great research and great replays.
> **GOD is the missing operator console** — a single screen where you can pause, ask, intervene, and reset a society of LLM agents while it is alive.

## ✨ Highlights

- 🎮 &nbsp;**Live pixel-town control room** — replay any step, pause, fast-forward, or auto-run.
- 💬 &nbsp;**Ask any agent anything** — targeted questions to one resident or to the whole town, mid-simulation.
- 🎛️ &nbsp;**Direct interventions** — inject new instructions into upcoming steps and watch the agents react.
- 🔄 &nbsp;**One-command reset** — wipe stale replay data and start a clean experiment.
- 🧱 &nbsp;**Local, hackable, single-config** — one `.env`, one script, no Docker required.

## 🖼️ Screenshots

<p align="center">
  <img src="docs/assets/screenshots/01-control-room.png" alt="GOD control room" width="94%" />
</p>

<p align="center"><sub>Live control room: pixel town, step controls, targeted ask, and resident roster — all in one view.</sub></p>

## 🚀 Quick Start

```bash
git clone https://github.com/XiaoLuoLYG/GOD.git
cd GOD
./scripts/god.sh start
```

On the first run, GOD opens the setup wizard at `/setup` before creating a live session. The wizard lets you configure model settings, describe a scenario, ask the GOD agent to generate an experiment draft, edit the generated profiles/steps, and then save a new experiment copy.

| Variable | Example |
| --- | --- |
| `GOD_LLM_API_KEY` | `sk-...` |
| `GOD_LLM_API_BASE` | `https://api.openai.com/v1` |
| `GOD_LLM_MODEL` | `gpt-5.4` |

Any OpenAI-compatible endpoint works. When the stack is ready, open the URL printed by the script, for example:

```
http://127.0.0.1:5174/pixel-replay/god_town/1
```

Full walkthrough: **[Quickstart →](QUICKSTART.md)**

## 🧩 Features

|     | Feature | Why it matters |
| --- | --- | --- |
| 🎬 | **Replay control** | Scrub a live or recorded experiment by step, pause, auto-run. |
| 💬 | **Targeted ask** | Direct natural-language questions to one agent or to everyone. |
| 🎛️ | **Step interventions** | Inject instructions for the next step; the simulation reacts immediately. |
| 🧪 | **Experiment setup wizard** | Configure models and scenarios in the browser, generate editable agent profiles, then launch a new experiment copy. |
| 🧼 | **Fresh runs** | One command to wipe a stale run and re-seed a clean simulation. |
| 🗺️ | **Pixel town world** | Locations, actions, messages, and agent status, all replay-friendly. |
| 🛠️ | **Single config** | One `.env`, one script, sane defaults. |

## 🏗️ How It Works

```mermaid
flowchart LR
  Op["Operator"] --> UI["Control Room<br/>React + Vite"]
  UI <--> Backend["GOD Backend<br/>FastAPI · live + replay"]
  Backend --> Town["Pixel Town<br/>init config + step plan"]
  Backend --> Store[("Replay Store")]
  Backend <--> Runtime["Agent Runtime<br/>LLM-backed agents"]
```

| Layer | What it does |
| --- | --- |
| **Control Room** | React/Vite UI for replay, ask, intervention, and status. |
| **Backend** | Local FastAPI service exposing live and replay APIs. |
| **Pixel Town** | Replay-friendly social world: locations, actions, messages, agent status. |
| **Agent Runtime** | Out-of-process LLM agents reached over a local WebSocket. |

## ⚙️ Commands

```bash
./scripts/god.sh start      # start the full stack (idempotent)
./scripts/god.sh configure  # open the setup wizard for a new experiment copy
./scripts/god.sh restart    # stop everything cleanly, then start again
./scripts/god.sh new-run    # wipe replay data and start a fresh session
./scripts/god.sh status     # ports, URLs, model status
./scripts/god.sh stop       # stop everything
./scripts/god.sh tail       # follow logs
./scripts/god.sh open       # open the control room in the default browser
```

## 🧪 Default Experiment

```text
god_town · The Ville ordinary weekday baseline
├── environment: The Ville pixel town with 10 places (home / school / library / cafe /
│   park / supply store / market / pharmacy / pub / dorm) and 65 location-scoped interactions
├── shared world: experiment_context with title, background, date/weather/school-calendar,
│   shared norms, town facts, and language preferences, injected into every step prompt
├── personas: 10 residents, each profile has age / gender / family / housing /
│   economic_status / health / needs / worries / secrets / social_network /
│   emotional_baseline / language_style / detailed_routine / inventory /
│   recent_history / triggers / dislikes / short_term_goals / long_term_goal /
│   quirks / skills (JiuwenClaw-style ids)
└── step plan: an experiment script you can intervene, branch, or replay at any step
```

To run your own experiment, drop a new config under `quick_experiments/` and point `GOD_EXPERIMENT` at it.

## 🛣️ Roadmap

- [ ] Multi-experiment orchestration: run experiments, control groups, and repeated trials in one control room.
- [ ] Live map generation: update the map as events, resources, repairs, blocked roads, and crowds evolve.
- [ ] Event-responsive worlds: weather, accidents, festivals, conflicts, rumors, and shortages affect decisions.
- [ ] Pluggable agents: swap LLM runtimes, persona templates, skill packs, and decision policies.
- [ ] Pluggable maps: load map manifests, place semantics, interactive objects, and navigation rules.
- [ ] More realistic defaults: add needs, jobs, families, social networks, economic limits, emotion, and memory.
- [ ] Large-scale simulation: integrate AgentSociety batching, sharded runs, sampled replay, and aggregate metrics.
- [ ] Experiment evaluation: cross-run metrics, behavior diffs, intervention analysis, and reproducible snapshots.
- [ ] Operator workflow: per-step notes, tags, bookmarks, and key-event summaries.
- [ ] Hosted demo and scenario sharing: public demo, experiment templates, map templates, and reusable config packs.

Have an idea? Open an issue or PR — see [Contributing](#-contributing).

## 🤝 Contributing

Issues and pull requests are very welcome. To set up a dev environment:

```bash
./scripts/god.sh start
```

That installs Python and Node dependencies, brings up the full stack, creates a live session, and runs the first step so the control room opens on a populated town. From there, edit and reload.

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
