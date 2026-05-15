<h1 align="center">📐 GOD Map Package Template</h1>

<p align="center">
  <b>Minimal starter — copy, rename, drop in your assets.</b>
</p>

<p align="center">
  <a href="README.zh-CN.md">🌏 中文</a> ·
  <a href="../../../../docs/MAP_PACKAGES.md">📘 Map Packages Guide</a>
</p>

---

Copy this directory to `agentsociety/custom/maps/<your_map_id>/`, rename it, and
replace `map.yaml`, `visuals/map.json`, and the assets.

The v1 contract expects a Tiled JSON map with a tile layer named **`Collisions`**.
In that layer, `0` means walkable and any non-zero tile means blocked.

## 🚀 Three-step Start

```bash
# 1. Copy this template
cp -r agentsociety/custom/maps/_template agentsociety/custom/maps/my_town

# 2. Edit map.yaml, drop in your Tiled JSON and tilesets

# 3. Validate
cd agentsociety
uv run python scripts/validate_map_package.py custom/maps/my_town
```

When validation passes, restart GOD and the new map appears in the setup wizard.

See [`docs/MAP_PACKAGES.md`](../../../../docs/MAP_PACKAGES.md) for the full
package contract and [`the_ville/`](../the_ville/README.md) for a complete
working example.
