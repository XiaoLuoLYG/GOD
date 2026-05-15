<h1 align="center">🏘️ The Ville · GOD Map Package</h1>

<p align="center">
  <b>The default pixel-town world that ships with GOD.</b><br/>
  <sub>10 locations · 65 interactions · the reference shape for every new map.</sub>
</p>

<p align="center">
  <a href="README.zh-CN.md">🌏 中文</a> ·
  <a href="../../../../docs/MAP_PACKAGES.md">📘 Map Packages Guide</a>
</p>

---

This is the **default GOD pixel-town map package**. Use this directory as the
reference shape when you build your own world. A new map can be added by
copying [`_template/`](../_template/README.md), replacing `map.yaml`,
`visuals/map.json`, the tileset images, and (optionally) character or location
assets.

## 📦 Layout

```text
the_ville/
├── map.yaml                   ← semantic manifest used by GOD
├── README.md                  ← you are here
├── ATTRIBUTION.md             ← visual asset credits
├── visuals/
│   ├── the_ville_jan7.json    ← Tiled JSON map (orthogonal)
│   └── map_assets/**/*.png    ← tileset images
└── characters/
    └── *.png                  ← 32×32 character sprites
```

## 🗺️ World

| Stat | Value |
| --- | --- |
| Map id | `the_ville` |
| Display name | The Ville |
| Tile size | 32 × 32 |
| Locations | 10 (`home`, `school`, `library`, `cafe`, `park`, `supply_store`, `market`, `pharmacy`, `pub`, `dorm`) |
| Interactions | 65 location-scoped actions |
| Tiled JSON | `visuals/the_ville_jan7.json` |

## ✅ Validation

```bash
cd agentsociety
uv run python scripts/validate_map_package.py custom/maps/the_ville
```

## 🙏 Credits

The pixel tiles, characters, and tilesets were originally produced for the
[Generative Agents](https://github.com/joonspk-research/generative_agents)
project. Full attribution lives in [`ATTRIBUTION.md`](ATTRIBUTION.md).
