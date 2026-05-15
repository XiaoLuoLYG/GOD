<h1 align="center">🤝 Contributing to GOD</h1>

<p align="center">
  <b>Issues and pull requests are very welcome.</b><br/>
  <sub>Whether you're fixing a typo, shipping a new map, or rewiring the runtime — thank you.</sub>
</p>

<p align="center">
  <a href="CONTRIBUTING.zh-CN.md">🌏 中文</a>
</p>

---

## 🧭 Ways to contribute

| | |
| --- | --- |
| 🐛 **Report a bug** | Open an [issue](https://github.com/XiaoLuoLYG/GOD/issues/new) with reproduction steps, screenshots, and the output of `./scripts/god.sh status`. |
| 💡 **Propose a feature** | Open an issue first. A short description + a one-paragraph use case is enough. |
| 🗺️ **Add a new map** | Drop a folder under `agentsociety/custom/maps/<your_map_id>/` and follow [`docs/MAP_PACKAGES.md`](docs/MAP_PACKAGES.md). PRs welcome. |
| 🧪 **Add a new experiment** | Drop a folder under `agentsociety/quick_experiments/<your_hypothesis>/<your_experiment>/`. See [`hypothesis_god_town/experiment_1/`](agentsociety/quick_experiments/hypothesis_god_town/experiment_1/README.md) as the reference shape. |
| ✏️ **Improve docs** | Fix translations, polish wording, add screenshots, add diagrams. |
| 🔌 **Wire in a runtime** | Adapter PRs for new LLM runtimes or persona templates are very welcome — see `agentsociety/custom/agents/`. |

## 🚀 Dev environment

```bash
git clone https://github.com/XiaoLuoLYG/GOD.git
cd GOD
./scripts/god.sh start
```

That installs Python and Node dependencies, brings up the full stack, creates a
live session, and runs the first step so the control room opens on a populated
town. From there, edit and reload.

Useful day-to-day commands:

```bash
./scripts/god.sh restart    # stop everything cleanly, then start again
./scripts/god.sh new-run    # wipe replay data and start a fresh session
./scripts/god.sh status     # check ports, URLs, model status
./scripts/god.sh tail       # follow logs
./scripts/god.sh stop       # stop everything
```

## 🌳 Branching & PR flow

1. Fork the repo and create a topic branch off `main`.
2. Keep PRs **small and focused** — one logical change per PR.
3. Run the validators you've touched:

   ```bash
   # If you changed a map package
   cd agentsociety
   uv run python scripts/validate_map_package.py custom/maps/<map_id>

   # If you changed Python services
   cd agentsociety/packages/agentsociety2
   uv run pytest
   ```

4. Open the PR against `main`. Describe **what** changed and **why** in the
   body. Screenshots and short clips go a long way for UI changes.
5. Be patient — the reviewer might be in another time zone.

## 📝 Style

- **Python:** 4-space indent, type hints where they help, no unused imports.
  We don't enforce a single formatter yet; match the surrounding code.
- **TypeScript / React:** match the surrounding component style.
- **Line width:** keep lines under **120 characters** where reasonable.
- **No forward declarations** (per project rule).
- **Comments** should explain non-obvious intent, not narrate the code.
- **Commits:** present tense, short subject (~60 chars), longer body if needed.
- **Docs:** when you change a Markdown doc with both `.md` and `.zh-CN.md`,
  update both. Use idiomatic English and Chinese — not literal translations.

## 🗺️ Adding a new map package — checklist

- [ ] Folder named `agentsociety/custom/maps/<map_id>/`
- [ ] `map.yaml`, `README.md`, `ATTRIBUTION.md` present
- [ ] Tiled JSON has a `Collisions` layer
- [ ] All tileset images resolve inside the package folder
- [ ] `uv run python scripts/validate_map_package.py custom/maps/<map_id>` passes
- [ ] At least one screenshot in the PR description

## 🧪 Adding a new experiment — checklist

- [ ] Folder under `agentsociety/quick_experiments/<hypothesis>/<experiment>/`
- [ ] `README.md` (English) + `README.zh-CN.md` (Chinese)
- [ ] `init/init_config.json` + `init/steps.yaml`
- [ ] A `run.sh` that boots the experiment via the AgentSociety CLI
- [ ] Manual run notes if there's an operator script (see PKU Trump experiment for the pattern)

## 📜 License

By contributing to GOD you agree that your contributions will be licensed under
the [Apache License 2.0](LICENSE). Upstream LICENSE and NOTICE files are kept
inside the integrated runtime checkouts (`agentsociety/`, `jiuwenclaw/`) and
apply to those subtrees.

## 🛡️ Be kind

GOD is a small open-source project. Be patient, be specific, and give the kind
of feedback you'd want to receive. We're here to build a town of agents — and
hopefully a small, warm community of humans around it.

---

<p align="center"><sub>Thank you for making GOD better. ⭐</sub></p>
