<h1 align="center">🏫 北大 · 特朗普访校剧情实验</h1>

<p align="center">
  <b>跑在 PKU 地图上的剧情化 GOD 实验。</b><br/>
  <sub>从普通的校园日常开始，由操作员手动注入一场公开演讲事件。</sub>
</p>

<p align="center">
  <a href="#-run">▶️ 运行</a> ·
  <a href="#%EF%B8%8F-map">🗺️ 地图</a> ·
  <a href="#-agents">👥 Agent</a> ·
  <a href="#-operator-flow">🎬 操作流程</a> ·
  <a href="#-validation">✅ 校验</a>
</p>

<p align="center">
  <a href="README.md">🌏 English</a> ·
  <a href="OPERATOR_SCRIPT.zh-CN.md">📜 操作脚本（中文）</a> ·
  <a href="OPERATOR_SCRIPT.md">📜 Operator Script (EN)</a>
</p>

---

> ⚠️ **What-if 实验框架。** 实验以 2026 年 5 月的假设性访华为背景上下文。
> 校园演讲、路线、代表团对话、学生提问与回答均为 AI 实验产出。
> 不要把它们当作真实行程、真实演讲或真实政策对外发布。

这是一个跑在 PKU 地图包上的 GOD 剧情化实验。开场是普通校园日常，随后由操作员手动
注入一份公开通知：Donald Trump 将率代表团访问北京大学，在百周年纪念讲堂面向学生
进行公开交流；代表团包括 Elon Musk、Jensen Huang 和一位协调员。

## ▶️ Run

```bash
GOD_EXPERIMENT=pku_trump_visit GOD_EXPERIMENT_RUN=1 ./scripts/god.sh new-run
```

控制台地址：

```text
http://127.0.0.1:5174/pixel-replay/pku_trump_visit/1
```

## 🗺️ Map

- 地图包：`custom/maps/pku`
- Map id：`pku`
- PKU 地图包是本地素材目录，**不入仓**。如果缺失，GOD 会回退到 `the_ville`。
- 关键地点：`west_gate`、`weiming_lake`、`boya_pagoda`、`library`、
  `centennial_hall`、`teaching_building`、`dormitory`、`canteen`、
  `gymnasium`、`lab_building`、`admin_building`、`campus_green`。

## 👥 Agents

实验定义 **22 个固定编号 Agent**：

| 群体 | 数量 | 代表角色 |
| --- | --- | --- |
| 🎓 北大校园 | 18 | 学生、教职、行政、校媒、社团组织者、访客 |
| 🛩️ 代表团 | 4 | Donald Trump、Elon Musk、Jensen Huang、代表团协调员 |

> 代表团 agent 是 **风格化的虚构模拟人物**，不代表真实人物的真实表态。

## 🎬 Operator Flow

完整的逐步提示词序列见 [`OPERATOR_SCRIPT.zh-CN.md`](OPERATOR_SCRIPT.zh-CN.md)。
高层节奏：

1. 🌱 粘贴日常导演提示，跑前 1–2 个 step，呈现普通校园日常。
2. 📣 粘贴访问通知 intervention（来自 `OPERATOR_SCRIPT.zh-CN.md`）。
3. 💬 跑 1–2 个 step，观察校园讨论。
4. 🚪 粘贴代表团抵达 intervention，再让全员集合到 `centennial_hall`。
5. ❓ 使用 Q&A 段落：每个问题先以 `direct_message` 送达对应 agent，再用 `Ask`
   拿一段干净文案，方便录屏。
6. 📰 用扩散讨论和总结提示收尾。

> 场内台词刻意写得自然，像真的校园交流。发布免责声明请放在视频简介、字幕角标或
> repo README 里 —— 不要让角色在台词里念出场外说明。

## ✅ Validation

```bash
cd agentsociety
uv run python scripts/validate_map_package.py custom/maps/pku
```

静态约束：

- `init/init_config.json` 使用 `map_id: pku`。
- 所有 `initial_locations` 都是 PKU 地图中的合法地点 id。
- `init/steps.yaml` 从 `2026-05-15T08:20:00+08:00` 开始。
