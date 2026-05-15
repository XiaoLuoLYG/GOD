<h1 align="center">🏘️ The Ville · GOD 地图包</h1>

<p align="center">
  <b>GOD 内置的默认像素小镇世界。</b><br/>
  <sub>10 个地点 · 65 个交互 · 所有新地图的参考形态。</sub>
</p>

<p align="center">
  <a href="README.md">🌏 English</a> ·
  <a href="../../../../docs/MAP_PACKAGES.zh-CN.md">📘 地图包指南</a>
</p>

---

这是 **GOD 默认的像素小镇地图包**。当你想做自己的世界时，把这个目录当作参考样本。
复制 [`_template/`](../_template/README.zh-CN.md)、替换 `map.yaml`、`visuals/map.json`、
图块素材，以及（可选的）人物或地点资产，新地图就能加入。

## 📦 目录结构

```text
the_ville/
├── map.yaml                   ← GOD 读取的语义清单
├── README.md                  ← 你正在看
├── ATTRIBUTION.md             ← 图块素材版权归属
├── visuals/
│   ├── the_ville_jan7.json    ← Tiled JSON 地图（orthogonal 正交投影）
│   └── map_assets/**/*.png    ← 图块素材
└── characters/
    └── *.png                  ← 32×32 人物精灵
```

## 🗺️ 世界概览

| 指标 | 值 |
| --- | --- |
| Map id | `the_ville` |
| 显示名 | The Ville |
| 图块尺寸 | 32 × 32 |
| 地点 | 10 个（`home`、`school`、`library`、`cafe`、`park`、`supply_store`、`market`、`pharmacy`、`pub`、`dorm`） |
| 交互 | 65 个 location-scoped 动作 |
| Tiled JSON | `visuals/the_ville_jan7.json` |

## ✅ 校验

```bash
cd agentsociety
uv run python scripts/validate_map_package.py custom/maps/the_ville
```

## 🙏 致谢

像素图块、人物、tileset 原始作品来自
[Generative Agents](https://github.com/joonspk-research/generative_agents) 项目。
完整版权归属见 [`ATTRIBUTION.md`](ATTRIBUTION.md)。
