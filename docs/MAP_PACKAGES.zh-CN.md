<h1 align="center">🗺️ GOD 地图包</h1>

<p align="center">
  <b>新建一个文件夹，刷新向导，Agent 立刻进入一座全新小镇。</b>
</p>

<p align="center">
  <a href="MAP_PACKAGES.md">🌏 English</a> ·
  <a href="../README.zh-CN.md">🌏 中文</a>
</p>

---

GOD 地图包是放在以下路径里的本地文件夹：

```text
agentsociety/custom/maps/<map_id>/
```

新建一个文件夹丢进去，重启或刷新配置向导，新地图就会作为可选世界出现 ——
不需要改任何代码。

## 📦 标准目录结构

```text
<map_id>/
├── map.yaml                   ← 语义清单（地点、交互、出生点）
├── README.md                  ← 地图包简介
├── ATTRIBUTION.md             ← 图块、人物、图标的版权归属
├── visuals/
│   ├── map.json               ← Tiled JSON 地图（orthogonal 正交投影）
│   └── map_assets/**/*.png    ← JSON 里引用的图块素材
├── characters/                ← 可选：32×32 像素人物精灵图
│   ├── atlas.json             ← 可选
│   └── *.png
└── location_assets/           ← 可选：UI 用的地点图标
    └── *.png
```

`map.yaml` 是 **语义清单** —— 描述地图上有哪些地点、Agent 可以在每个地点做什么、世界怎么串起来。
`visuals/map.json` 是 **Tiled JSON 地图**，赋予世界像素外观。
Tiled JSON 里的图块路径必须是相对路径，且不能跳出地图包目录。

## 📝 清单字段

最小可用的 `map.yaml`：

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

推荐的可选字段：

| 字段 | 作用 |
| --- | --- |
| `default_location_order` | Agent 没有指定地点时的兜底优先级。 |
| `bounds` | `{x, y, w, h}`，覆盖某个地点的矩形区域（点击、高亮、状态显示用）。 |
| `scene_type` | 紧凑分类，如 `home`、`school`、`market`。 |
| `visual_asset` | `location_assets/` 下的图标相对路径。 |
| `effects` | 交互产出字段：`action`、`status`、`emotion`、`latest_event`、`group_message`。 |

运行时多语言字段是可选且兼容旧清单的。保留现有 `display_name`、`name`、`description`
作为后端/运行时默认值，只在 `localized.en` 与 `localized.zh` 中补前端展示文本：

```yaml
localized:
  en:
    display_name: Your Map Name
  zh:
    display_name: 你的地图名
locations:
  - id: plaza
    name: Plaza
    localized:
      en:
        name: Plaza
      zh:
        name: 广场
interactions:
  - id: wait
    name: Wait
    description: Wait in place.
    localized:
      en:
        name: Wait
        description: Wait in place.
      zh:
        name: 等待
        description: 原地等待。
```

## 🧱 Tiled JSON 规则

v1 仅支持正交（orthogonal）Tiled JSON 地图：

- `orientation` 必须为 `orthogonal`。
- `tilewidth` 与 `tileheight` 应等于 `tile_size`。
- 地图必须包含一个名为 **`Collisions`** 的瓦片层。
- 在 `Collisions` 中，`0` 表示可走，任何非零图块表示阻挡。
- 图块素材必须是 PNG 文件，且位于地图包目录内。
- v1 **不支持** TMX、外部 tileset 文件、远程图片、单张背景图地图。

## ✅ 校验

```bash
cd agentsociety
uv run python scripts/validate_map_package.py custom/maps/<map_id>
```

校验器会检查必填字段、资源路径、Tiled JSON 结构、图块素材、`Collisions` 层、
地点锚点、交互引用是否对得上。

历史遗留的 The Ville 语义检查也仍然保留：

```bash
uv run python scripts/validate_the_ville_map.py
```

## 🧰 即用即抄的模板

| 包 | 用途 |
| --- | --- |
| [`agentsociety/custom/maps/the_ville/`](../agentsociety/custom/maps/the_ville/README.zh-CN.md) | 完整范例 —— 10 个地点、65 个交互、真实图块素材。 |
| [`agentsociety/custom/maps/_template/`](../agentsociety/custom/maps/_template/README.zh-CN.md) | 最小起步模板，复制一份、改名、替换素材即可。 |

## 🚀 五分钟上手流程

```bash
# 1. 复制模板
cp -r agentsociety/custom/maps/_template agentsociety/custom/maps/my_town

# 2. 放入你的 Tiled JSON、图块 PNG、人物精灵（可选）
#    编辑 map.yaml：修改 map_id、display_name、locations、interactions

# 3. 校验
cd agentsociety
uv run python scripts/validate_map_package.py custom/maps/my_town

# 4. 重启 GOD，在配置向导里选择新地图
./scripts/god.sh restart
```

就这么简单 —— 不用改代码，也不用动注册表。配置向导每次刷新都会自动发现所有合法地图包。
