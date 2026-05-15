<h1 align="center">📐 GOD 地图包模板</h1>

<p align="center">
  <b>最小起步模板 —— 复制、改名、放入你的素材即可。</b>
</p>

<p align="center">
  <a href="README.md">🌏 English</a> ·
  <a href="../../../../docs/MAP_PACKAGES.zh-CN.md">📘 地图包指南</a>
</p>

---

把这个目录复制到 `agentsociety/custom/maps/<your_map_id>/`、改名，然后替换
`map.yaml`、`visuals/map.json` 与素材。

v1 约定要求一份 Tiled JSON 地图，并带一个名为 **`Collisions`** 的瓦片层。
在该层中，`0` 表示可走，任何非零图块表示阻挡。

## 🚀 三步上手

```bash
# 1. 复制模板
cp -r agentsociety/custom/maps/_template agentsociety/custom/maps/my_town

# 2. 编辑 map.yaml，放入你的 Tiled JSON 和图块

# 3. 校验
cd agentsociety
uv run python scripts/validate_map_package.py custom/maps/my_town
```

校验通过后，重启 GOD，新地图就会出现在配置向导里。

完整包契约见 [`docs/MAP_PACKAGES.zh-CN.md`](../../../../docs/MAP_PACKAGES.zh-CN.md)，
完整可运行的范例见 [`the_ville/`](../the_ville/README.zh-CN.md)。
