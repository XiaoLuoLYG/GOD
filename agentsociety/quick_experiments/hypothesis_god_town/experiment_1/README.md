<h1 align="center">🏘️ GOD Town · Experiment 1</h1>

<p align="center">
  <b>The Ville · an ordinary weekday morning</b><br/>
  <sub>10 residents · 10 locations · 65 location-scoped interactions</sub>
</p>

<p align="center">
  <a href="#-run">▶️ Run</a> ·
  <a href="#-experiment-config">🧪 Config</a> ·
  <a href="#%EF%B8%8F-world--map">🗺️ World & Map</a> ·
  <a href="#-residents">👥 Residents</a> ·
  <a href="#-skills--actions">🎯 Skills & Actions</a> ·
  <a href="#%EF%B8%8F-step-plan">⏱️ Step Plan</a>
</p>

<p align="center">
  <a href="README.zh-CN.md">🌏 中文</a>
</p>

---

## ▶️ Run

```bash
# Recommended: launch through the GOD control room (wipes the previous replay)
./scripts/god.sh new-run

# Or: foreground CLI run (good for single-step debugging)
./agentsociety/quick_experiments/hypothesis_god_town/experiment_1/run.sh
```

When startup finishes, open:

```text
http://127.0.0.1:5174/pixel-replay/god_town/1
```

## 🧪 Experiment Config

The whole experiment is described by two files. The GOD control room reads them
to spin up a live session; replays follow the same contract.

| File | Purpose |
| --- | --- |
| [`init/init_config.json`](init/init_config.json) | World + agent init: map module, initial locations, 10 resident profiles, shared world context. |
| [`init/steps.yaml`](init/steps.yaml) | Step plan: starting timestamp, how many steps to auto-advance, how long each tick is. |
| [`run.sh`](run.sh) | Wires both configs into the AgentSociety CLI. |

### 🌍 Shared World (`experiment_context`)

The "world dictionary" every resident reads on every step:

```yaml
title:           GOD Town · The Ville ordinary weekday
date / weekday:  2026-05-12 · Tuesday · late_spring
weather:         sunny, 18°C, light breeze
school_in_session: true     market_day: false
shared_norms:
  - Observe first, act second — do not escalate routine moments into emergencies.
  - Respect privacy. Do not forward other people's secrets unprompted.
  - Use group chat for public/necessary information only; keep personal matters in direct_message.
  - Greetings stay short and natural. Do not pry into private matters before any work topic.
town_facts:
  - Hobbs Cafe is the neighborhood's casual meeting buffer.
  - The Willows Market and the Pharmacy share one building.
  - Johnson Park is public space and the default place for community announcements.
  - Oak Hill College hosts classrooms, the library, and the dorm.
  - The Rose and Crown Pub is mostly active in the late afternoon and evening.
language: Prefer Chinese, switch to bilingual when necessary.
```

### ⚙️ Environment Module (`env_modules`)

```yaml
PixelTownSocialEnv:
  map_manifest_path:           custom/maps/the_ville/map.yaml
  default_group_name:          The Ville Daily Life Chat
  movement_tiles_per_second:   8.0      # visual movement speed on the map
  movement_min_steps_per_trip: 3        # minimum steps consumed when crossing locations
```

The 10 residents' starting locations at `t=0`:

| Park 🌳 | Market 🛒 | School 🏫 | Pharmacy 💊 | Cafe ☕ | Supply Store 🛠️ | Home 🏠 |
| --- | --- | --- | --- | --- | --- | --- |
| Alice · George | Bob · Mei | Charlie · Farah | Dana | Elena | Ivan | Hana |

## 🗺️ World & Map

The map is sourced from the classic [The Ville](https://github.com/joonspk-research/generative_agents)
pixel town, repackaged as a pluggable GOD map and trimmed to **10 semantic
locations + 65 interactions**. The manifest lives at
[`custom/maps/the_ville/map.yaml`](../../../custom/maps/the_ville/map.yaml).

<table>
<tr>
  <td align="center" width="20%">🏠<br/><b>Home</b><br/><sub>9 interactions</sub><br/><sub><i>cook · eat at home · sleep · rest · tidy · read at home · WFH · video-call family · water plants</i></sub></td>
  <td align="center" width="20%">🏫<br/><b>Classroom</b><br/><sub>7 interactions</sub><br/><sub><i>attend class · teach · after-class study · lesson prep · grade · office hours · faculty meeting</i></sub></td>
  <td align="center" width="20%">📚<br/><b>Library</b><br/><sub>6 interactions</sub><br/><sub><i>read · study · research · borrow · return · quiet work</i></sub></td>
  <td align="center" width="20%">☕<br/><b>Hobbs Cafe</b><br/><sub>7 interactions</sub><br/><sub><i>light meal · coffee chat · barista shift · order coffee · takeaway · casual meetup · tidy cafe</i></sub></td>
  <td align="center" width="20%">🌳<br/><b>Johnson Park</b><br/><sub>8 interactions</sub><br/><sub><i>walk · meet friend · bench rest · park meetup · morning exercise · birdwatch · light picnic · public announcement</i></sub></td>
</tr>
<tr>
  <td align="center" width="20%">🛠️<br/><b>Harvey Oak Supply</b><br/><sub>6 interactions</sub><br/><sub><i>stock check · prep supplies · repair tools · restock · customer service · lend tools</i></sub></td>
  <td align="center" width="20%">🛒<br/><b>Willows Market</b><br/><sub>6 interactions</sub><br/><sub><i>buy food · shop shift · restock produce · haggle · deliver · chat with regulars</i></sub></td>
  <td align="center" width="20%">💊<br/><b>Willows Pharmacy</b><br/><sub>6 interactions</sub><br/><sub><i>buy medicine · pharmacy consult · refill · check BP · tidy shelves · home-visit prep</i></sub></td>
  <td align="center" width="20%">🍻<br/><b>Rose and Crown Pub</b><br/><sub>5 interactions</sub><br/><sub><i>pub socialize · pub meal · watch the match · evening chatter · host small event</i></sub></td>
  <td align="center" width="20%">🛏️<br/><b>Oak Hill Dorm</b><br/><sub>5 interactions</sub><br/><sub><i>dorm rest · dorm meal · dorm self-study · common-room hangout · video-call home</i></sub></td>
</tr>
</table>

<sub>Every interaction is structured: <code>allowed_location_ids</code> constrains where it can happen, and <code>effects</code> drive the action description, status, emotion, and the group-chat message.</sub>

#### 🎬 What one interaction looks like

```yaml
- id: public_announcement
  name: Public Announcement
  description: Post a public notice or reminder to the group from Johnson Park.
  allowed_location_ids: [park]
  effects:
    action:        "{agent_name} is posting a public announcement in the park"
    status:        socializing
    emotion:       focused
    latest_event:  "{agent_name} just posted a public announcement in the park."
    group_message: "{agent_name} announces from the park: {message}"
```

## 👥 Residents

10 residents share five profile dimensions, but each one has a different
personality, pace, and life weight:

<table>
<tr>
  <td align="center" width="20%">🧭<br/><b>Jiuwen Alice</b><br/><sub>♀ · 34 · Neighborhood coordinator</sub><br/><sub>gentle, punctual, responsible</sub></td>
  <td align="center" width="20%">🛠️<br/><b>Jiuwen Bob</b><br/><sub>♂ · 45 · Supply-store owner</sub><br/><sub>pragmatic, soft-hearted under a gruff voice</sub></td>
  <td align="center" width="20%">📖<br/><b>Jiuwen Charlie</b><br/><sub>♂ · 39 · High-school history teacher</sub><br/><sub>patient, restrained, a born storyteller</sub></td>
  <td align="center" width="20%">💊<br/><b>Jiuwen Dana</b><br/><sub>♀ · 41 · Pharmacy nurse</sub><br/><sub>professional, gentle, careful</sub></td>
  <td align="center" width="20%">☕<br/><b>Jiuwen Elena</b><br/><sub>♀ · 36 · Cafe owner</sub><br/><sub>extroverted, warm, knows when to back off</sub></td>
</tr>
<tr>
  <td align="center" width="20%">🎒<br/><b>Jiuwen Farah</b><br/><sub>♀ · 16 · High-school student</sub><br/><sub>curious, quick, slightly socially anxious</sub></td>
  <td align="center" width="20%">📮<br/><b>Jiuwen George</b><br/><sub>♂ · 68 · Retired postman</sub><br/><sub>slow-warming, funny, sharp memory</sub></td>
  <td align="center" width="20%">💻<br/><b>Jiuwen Hana</b><br/><sub>♀ · 28 · Remote software engineer</sub><br/><sub>quiet, rigorous, newly moved in</sub></td>
  <td align="center" width="20%">🦺<br/><b>Jiuwen Ivan</b><br/><sub>♂ · 52 · Public-safety volunteer</sub><br/><sub>steady, restrained, observant</sub></td>
  <td align="center" width="20%">🍅<br/><b>Jiuwen Mei</b><br/><sub>♀ · 47 · Market vegetable vendor</sub><br/><sub>boisterous, loves to joke</sub></td>
</tr>
</table>

### 🧬 Profile fields (every resident has them)

| Dimension | Fields |
| --- | --- |
| 🪪 **Identity** | `age` · `gender` · `role` · `family` · `housing` · `economic_status` · `health` |
| 🧠 **Mind** | `persona` · `emotional_baseline` · `language_style` · `quirks` · `triggers` · `dislikes` |
| 📅 **Rhythm** | `daily_routine` · `detailed_routine` (morning · late_morning · noon · afternoon · evening · night) |
| 🤝 **Ties** | `relationships` · `social_network` (9 name → label entries) |
| 🎯 **Goals** | `needs` · `worries` · `secrets` · `short_term_goals` · `long_term_goal` · `goal` · `constraints` |
| 🎒 **State** | `inventory` · `recent_history` · `skills` |

### 🪟 Profile snippet · Alice

```yaml
role:               neighborhood coordinator
emotional_baseline: calm, attentive
language_style:     warm and short; greets before getting to the point; rarely uses exclamation marks
inventory:          [phone, keys, small notebook, pen, water bottle]
needs:              [finish today's neighborhood walk, check in on George, reply to Bob about the notice]
worries:            [weekend event venue still undecided, George has been going out less lately]
secrets:            [ex-partner was also a community volunteer, quietly fixed a small leak at home this month]
quirks:             [leaves sticky notes on the cafe counter, says "okay, let me write that down"]
long_term_goal:     get the town's routine work to run smoothly without depending on her personally
```

Full profile lives in [`init_config.json`](init/init_config.json) — the other
nine residents are just as detailed, including secrets, quirks, and what's been
going on lately.

## 🎯 Skills & Actions

Every resident carries 5 **JiuwenClaw-style skill IDs**. They are not decorative
— with `skill_runtime` off they act as character cues that tell the LLM what
the resident "can do"; with `skill_runtime` on they are registered as actual
callable tools.

🧭 **Alice** · community coordination
```text
community.coordinate
conflict.mediate
first_aid.basic
notice.write
messaging.group
```

🛠️ **Bob** · tools & repair
```text
tools.repair
inventory.count
route.localmap
ledger.basic
neighbor.support
```

... see <a href="init/init_config.json"><code>init_config.json</code></a> for the rest.

## ⏱️ Step Plan

The experiment starts at 8:20 in the morning and advances 30 minutes of in-world
time per step:

```yaml
start_t: "2026-05-11T08:20:00+08:00"
steps:
  - type: run
    num_steps: 4         # auto-advance 4 steps (~2 in-world hours)
    tick: 1800           # 1800 seconds / step = 30 minutes
```

From there, **pause / ask / intervene / continue** at will from the control
room. The whole run still obeys the same init config — GOD only rewrites the
*next* step at the right moment.

## 📂 Files

```text
experiment_1/
├── README.md              ← you are here
├── run.sh                 ← AgentSociety CLI entry point
└── init/
    ├── init_config.json   ← 10 residents + shared world + environment module
    └── steps.yaml         ← starting time + step plan
```

> Want your own experiment? Copy the whole `experiment_1/` folder, edit it, drop
> it under `quick_experiments/<your_hypothesis>/<your_experiment>/`, and point
> `GOD_EXPERIMENT` at it. Or just spin up a new copy from the **Setup Wizard**
> in the GOD control room.
