<h1 align="center">🗺️ GOD Map Packages</h1>

<p align="center">
  <b>Drop in a folder. Refresh the wizard. Steer agents through a brand new town.</b>
</p>

<p align="center">
  <a href="../README.md">🌏 English</a> ·
  <a href="MAP_PACKAGES.zh-CN.md">🌏 中文</a>
</p>

---

GOD map packages are local folders under:

```text
agentsociety/custom/maps/<map_id>/
```

Drop a new folder there, restart or refresh the setup wizard, and the map shows up
as a selectable world — no code changes required.

## 📦 Required Layout

```text
<map_id>/
├── map.yaml                   ← semantic manifest (locations, interactions, spawn points)
├── README.md                  ← package overview
├── ATTRIBUTION.md             ← credits for tiles, sprites, icons
├── visuals/
│   ├── map.json               ← Tiled JSON map (orthogonal)
│   └── map_assets/**/*.png    ← tileset images referenced by the JSON
├── characters/                ← optional: 32×32 sprite PNGs
│   ├── atlas.json             ← optional
│   └── *.png
└── location_assets/           ← optional: location icons used by the UI
    └── *.png
```

`map.yaml` is the **semantic manifest** — it describes what locations exist, what
agents can do at each one, and how the world is wired up. `visuals/map.json` is
the **Tiled JSON map** that gives the world its pixel form. Tileset image paths
inside the Tiled JSON must be relative paths that stay inside the package folder.

## 📝 Manifest Fields

A minimal `map.yaml`:

```yaml
schema_version: 1
map_id: your_map_id
display_name: Your Map Name
tiled_map_path: visuals/map.json
tile_size: 32
character_root: characters
spawn_points:
  - id: resident_start
    location_id: plaza
locations:
  - id: plaza
    name: Plaza
    aliases: [plaza]
    anchor_tile: {x: 1, y: 1}
    interaction_ids: [wait]
interactions:
  - id: wait
    name: Wait
    allowed_location_ids: [plaza]
```

Recommended optional fields:

| Field | What it does |
| --- | --- |
| `default_location_order` | Preferred fallback order when an agent has no explicit location. |
| `bounds` | `{x, y, w, h}` region covering a location (for clicks, highlights, status). |
| `scene_type` | Compact category such as `home`, `school`, `market`. |
| `visual_asset` | Relative path to an icon in `location_assets/`. |
| `effects` | Interaction output fields: `action`, `status`, `emotion`, `latest_event`, `group_message`. |

## 🧱 Tiled JSON Rules

v1 supports only orthogonal Tiled JSON maps:

- `orientation` must be `orthogonal`.
- `tilewidth` and `tileheight` should match `tile_size`.
- The map must include a tile layer named **`Collisions`**.
- In `Collisions`, `0` means walkable and any non-zero tile means blocked.
- Tileset images must be PNG files inside the map package folder.
- TMX, external tileset files, remote images, and single-background-image maps
  are **not** supported in v1.

## ✅ Validation

```bash
cd agentsociety
uv run python scripts/validate_map_package.py custom/maps/<map_id>
```

The validator checks required fields, resource paths, Tiled JSON shape, tileset
images, the `Collisions` layer, location anchors, and interaction references.

The legacy semantic check for The Ville still exists as:

```bash
uv run python scripts/validate_the_ville_map.py
```

## 🧰 Ready-to-Copy Templates

| Package | Purpose |
| --- | --- |
| [`agentsociety/custom/maps/the_ville/`](../agentsociety/custom/maps/the_ville/README.md) | The complete working example — 10 locations, 65 interactions, real tilesets. |
| [`agentsociety/custom/maps/_template/`](../agentsociety/custom/maps/_template/README.md) | A minimal starter package. Copy, rename, and replace the assets. |

## 🚀 Five-Minute Workflow

```bash
# 1. Copy the template
cp -r agentsociety/custom/maps/_template agentsociety/custom/maps/my_town

# 2. Drop in your Tiled JSON, tileset PNGs, and (optionally) character sprites
#    Edit map.yaml: change map_id, display_name, locations, interactions

# 3. Validate
cd agentsociety
uv run python scripts/validate_map_package.py custom/maps/my_town

# 4. Restart GOD and pick the new map in the setup wizard
./scripts/god.sh restart
```

That's it — no code changes, no registry edits. The setup wizard discovers every
valid package on every refresh.
