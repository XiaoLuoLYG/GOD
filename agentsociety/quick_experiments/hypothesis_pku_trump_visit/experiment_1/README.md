<h1 align="center">🏫 PKU · Trump Campus Visit</h1>

<p align="center">
  <b>A scripted GOD experiment on the PKU map.</b><br/>
  <sub>Ordinary campus life, then a manually-injected public lecture event.</sub>
</p>

<p align="center">
  <a href="#-run">▶️ Run</a> ·
  <a href="#%EF%B8%8F-map">🗺️ Map</a> ·
  <a href="#-agents">👥 Agents</a> ·
  <a href="#-operator-flow">🎬 Operator Flow</a> ·
  <a href="#-validation">✅ Validation</a>
</p>

<p align="center">
  <a href="README.zh-CN.md">🌏 中文</a> ·
  <a href="OPERATOR_SCRIPT.md">📜 Operator Script (EN)</a> ·
  <a href="OPERATOR_SCRIPT.zh-CN.md">📜 操作脚本 (中文)</a>
</p>

---

> ⚠️ **What-if framing.** The experiment uses a hypothetical May 2026 China-visit
> framing only as broad background context. The campus lecture, route,
> delegation dialogue, student questions, and answers are AI experiment output.
> Do not publish them as a real itinerary, real speech, or real policy.

This GOD experiment is set on the PKU map package. It starts with ordinary
campus life, then lets the operator manually inject a public notice: Donald
Trump will visit Peking University and speak at Centennial Hall with a
delegation that includes Elon Musk, Jensen Huang, and a coordinator.

## ▶️ Run

```bash
GOD_EXPERIMENT=pku_trump_visit GOD_EXPERIMENT_RUN=1 ./scripts/god.sh new-run
```

The control room opens at:

```text
http://127.0.0.1:5174/pixel-replay/pku_trump_visit/1
```

## 🗺️ Map

- Map package: `custom/maps/pku`
- Map id: `pku`
- The PKU map package is a local asset folder and is intentionally **not
  stored** in this repository. If it is absent, GOD falls back to `the_ville`.
- Key locations: `west_gate`, `weiming_lake`, `boya_pagoda`, `library`,
  `centennial_hall`, `teaching_building`, `dormitory`, `canteen`,
  `gymnasium`, `lab_building`, `admin_building`, `campus_green`.

## 👥 Agents

The experiment defines **22 fixed-ID agents**:

| Group | Count | Examples |
| --- | --- | --- |
| 🎓 PKU campus | 18 | students, faculty, staff, media, club organizers, a visitor |
| 🛩️ Delegation | 4 | Donald Trump, Elon Musk, Jensen Huang, delegation coordinator |

> The delegation agents are **stylized fictional simulation personas**. They do
> not represent real statements by those people.

## 🎬 Operator Flow

The full step-by-step prompt sequence lives in
[`OPERATOR_SCRIPT.md`](OPERATOR_SCRIPT.md). The high-level beat is:

1. 🌱 Paste the daily-life director prompt, run the first 1–2 live steps to show
   ordinary campus life.
2. 📣 Paste the visit-notice intervention from `OPERATOR_SCRIPT.md`.
3. 💬 Run one or two steps to observe campus discussion.
4. 🚪 Paste the delegation-arrival intervention, then gather everyone to
   `centennial_hall`.
5. ❓ Use the Q&A blocks: each question is first delivered as an agent-to-agent
   `direct_message`, then followed by a targeted `Ask` for a clean answer
   suitable for screen recording.
6. 📰 Finish with the aftermath and summary prompts.

> The in-scene prompts are intentionally written in a natural campus tone. Keep
> publication disclaimers in captions, README text, or video descriptions —
> never have the characters repeat them in dialogue.

## ✅ Validation

```bash
cd agentsociety
uv run python scripts/validate_map_package.py custom/maps/pku
```

Static expectations:

- `init/init_config.json` uses `map_id: pku`.
- Every `initial_locations` entry is one of the PKU map location ids.
- `init/steps.yaml` starts at `2026-05-15T08:20:00+08:00`.
