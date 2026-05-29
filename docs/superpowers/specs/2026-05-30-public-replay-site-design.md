# Public Replay Site Design

Date: 2026-05-30
Project: GOD

## Goal

Build a public product site for GOD that lets users experience finished
agent-society experiments without cloning the repository.

The first release is a static GitHub Pages site. It presents GOD as a product,
hosts read-only replay archives for local runs that have already completed, and
publishes downloadable assets for maps, agents, and experiments.

## Product Boundary

The site is a product landing page plus a public archive. It is not a hosted
simulation runtime.

Users can:

- Open public replay pages for finished experiments.
- Play, pause, scrub, and inspect replay steps.
- Inspect agents, messages, runtime state, and recorded operator commands.
- Download replay bundles, map packs, agent packs, and experiment packs.
- Follow links to GitHub and developer documentation.

Users cannot in v1:

- Run a new simulation online.
- Submit new ask/intervene commands online.
- Generate maps or agents online.
- Upload or publish their own assets through the website.

GitHub Pages is enough for v1. A custom domain is optional branding, not a
technical requirement. A hosted backend is only needed later if the site grows
into online simulation, user uploads, or marketplace publishing.

## Hero Copy

Use the README voice rather than generic SaaS copy.

Badge:

```text
Govern - Observe - Direct
```

Title:

```text
GOD
```

Subtitle:

```text
Make your agents dance in a virtual Eden.
```

Supporting line:

```text
Pause time. Whisper to a soul. Bend the next step. Create your own world.
```

Primary actions:

- Watch Replay
- Browse Packs

## Visual Direction

Use a bright product-page style close to the current promo site:

- Warm off-white page background.
- Ink text and teal accents.
- Small amounts of gold, blue, and rose for category accents.
- Real PixelReplay screenshots, map previews, timeline markers, command chips,
  and download cards as the main visual language.
- No full-page dark Emergence-style theme.
- No decorative gradient blobs or abstract SVG hero art.
- No Stanford Prison example in public v1.

Borrow from Emergence World only at the structural level: short badge, large
product name, concise value sentence, clear calls to action, and a visible path
to enter the world.

## Information Architecture

Top-level navigation:

- Replay
- Map Pack
- Agent Pack
- Experiment
- Developer Docs
- GitHub

Pages:

- `/` product landing page
- `/replays/` replay list
- `/replays/<slug>/` static replay viewer
- `/map-packs/` map pack library
- `/agent-packs/` agent pack library
- `/experiments/` experiment library
- `/experiments/<slug>/` experiment detail
- `/developer/` existing developer docs
- `/zh/` Chinese landing page and localized list pages when practical

Homepage sections:

1. Hero.
2. Featured Replays: GOD Town and PKU Public Situation.
3. Product Surfaces: Replay, Map Pack, Agent Pack, Experiment as four equal
   cards.
4. Create Your Own World: local setup and developer-doc links for creating,
   running, and publishing new worlds.
5. Footer.

Do not add a separate landing-page section explaining command history. Recorded
ask/intervene commands are replay content and should appear naturally inside the
replay viewer.

Do not add a separate "asset library preview" below the four product cards. The
four product cards are the asset/product entry points.

## Product Surfaces

### Replay

The Replay surface is the core v1 no-clone experience.

Replay pages should provide a read-only version of the local PixelReplay
experience:

- Pixel map canvas.
- Play, pause, previous, next, and step slider.
- Current step and simulation time.
- Summary tab.
- Chat/messages tab.
- Residents tab with selected-agent details.
- Recorded operator commands as timeline/context content.
- Download links for the replay bundle and related packs.

Ask/intervene controls must not accept new commands in the public static viewer.
If command UI appears, it should be disabled or replaced by recorded command
history.

### Map Pack

The Map Pack surface publishes reusable maps.

v1 map packs:

- `the_ville`
- `pku`

Map pack cards/details should include:

- Preview image.
- Display name and map id.
- Location count.
- Interaction count.
- Tileset and sprite metadata.
- Related experiments/replays.
- Download link.

This is not online Map Studio. It is a published package library.

### Agent Pack

The Agent Pack surface publishes reusable casts and agent assets.

v1 can publish agent packs at the experiment-cast level:

- GOD Town cast.
- PKU cast.

Agent pack cards/details should include:

- Agent count.
- Runtime type.
- Profile metadata summary.
- Sprite coverage.
- Mounted skills summary.
- Related map/replay/experiment.
- Download link.

Future versions can add individual agent templates, skill bundles, and runtime
adapter packs.

### Experiment

The Experiment surface publishes full scenario bundles.

v1 experiments:

- GOD Town / The Ville.
- PKU Public Situation.

Experiment detail pages should include:

- Hypothesis/scenario summary.
- Map and cast references.
- Steps/init config summary.
- Operator notes link or excerpt.
- Related replay.
- Related map pack and agent pack.
- Download link.

The experiment pack is meant to be downloaded and reproduced or modified in a
local GOD checkout.

## Static Replay Bundle

Add an export flow that converts a finished local experiment run into static
files that GitHub Pages can serve.

Suggested bundle shape:

```text
replays/<slug>/
  manifest.json
  info.json
  timeline.json
  commands.json
  steps/
    000.json
    001.json
  agents/
    profiles.json
    runtime-state/
      <agent_id>.json
  map/
    map.json
    assets/
    characters/
    location-assets/
  downloads/
    replay-bundle.zip
    experiment-pack.zip
    map-pack.zip
    agent-pack.zip
```

The public site should read a unified catalog manifest that links:

- replay id
- experiment id
- map pack id
- agent pack ids
- screenshots/previews
- static data URLs
- download URLs
- tags and language metadata

The current hand-written `docs/site/data/experiments.js` should evolve toward
this manifest-driven model so future publishing does not require page-specific
edits.

## Command History

Future live ask/intervene commands should become first-class replay data.

Add a replay dataset:

```text
dataset_id: core.operator_command
kind: event_stream
capabilities: ["operator_command", "event_stream", "timeseries"]
```

Minimum columns:

- `command_id`
- `type` (`ask` or `intervene`)
- `step`
- `simulation_time`
- `prompt`
- `target_json`
- `result`
- `artifact_name`
- `status`
- `created_at`

Continue writing Markdown artifacts under `run/artifacts/` because they are
useful for human-readable downloads.

The exporter must support artifact backfill for existing runs. If
`core.operator_command` is missing, parse `run/artifacts/*.md`:

- Use YAML frontmatter for question/instruction and target.
- Use filename patterns for command type, step, and simulation time.
- Use Markdown body as the result.
- Emit normalized `commands.json`.

This lets existing GOD Town and PKU replay artifacts appear in public replay
without rerunning those experiments.

## Static Viewer Architecture

Prefer reusing PixelReplay instead of rebuilding a separate replay UI from
scratch.

Add a data-source boundary:

- Local mode: existing FastAPI replay endpoints.
- Static archive mode: static bundle JSON and assets.

The UI should consume the same normalized concepts in both modes:

- replay info
- timeline
- step bundle
- map info
- agent profiles
- agent runtime state
- operator commands

The public viewer must be read-only. Static mode should not open live WebSocket
connections or call `/api/v1/live-experiments`.

## Error Handling

Public pages should fail clearly:

- Missing replay manifest: show "Replay not found" with a link back to replay
  list.
- Missing step bundle: keep the page usable and show a step-specific error.
- Missing map asset: show a visible map loading error instead of a blank canvas.
- Missing command history: omit the command section or show "No recorded
  operator commands for this replay."
- Broken download link: surface it during verification; do not hide it in UI.

The exporter should fail fast on:

- Missing `sqlite.db`.
- Missing map package.
- Missing required Tiled map or tileset.
- Absolute paths or local secrets in generated public JSON.

## Privacy And Safety

Public exports must not include:

- `.env` values.
- API keys.
- Local absolute paths.
- Private backend logs unrelated to replay.
- Temporary files.
- Unreviewed generated drafts.

Runtime state exports should be intentionally scoped. Include data that helps
users inspect agents and replay behavior, but avoid dumping unrelated local
tooling/session data if it contains machine-specific paths or secrets.

## Verification

Implementation must include real browser validation after frontend/site changes.

Required checks:

- Build the frontend if PixelReplay code changes:

```bash
npm run build --prefix agentsociety/frontend
```

- Build or smoke-check the static site and developer docs so Pages is not
  broken.
- Export bundles for GOD Town and PKU.
- Open the local site in a browser and verify:
  - homepage loads
  - hero text wraps cleanly
  - navigation does not overlap
  - four product cards wrap correctly
  - featured replay cards keep stable image ratios
  - replay viewer map is nonblank
  - timeline controls work
  - resident details are readable
  - command history from artifact backfill is visible
  - download links resolve
- Check at least desktop and mobile viewport widths.
- Run `git diff --check`.

## Out Of Scope For V1

- Online simulation runtime.
- Online ask/intervene execution.
- User uploads.
- Hosted Map Studio.
- Hosted Agent Studio.
- Account system.
- Payments or marketplace transactions.
- Custom domain migration as a blocker.

