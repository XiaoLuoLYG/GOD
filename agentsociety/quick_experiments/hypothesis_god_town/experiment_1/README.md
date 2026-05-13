<h1 align="center">🏘️ GOD Town · Experiment 1</h1>

<p align="center">
  <b>The Ville · 一个普通工作日的日常切片</b><br/>
  <sub>10 位居民 · 10 个地点 · 65 个 location-scoped 交互</sub>
</p>

<p align="center">
  <a href="#-run">▶️ Run</a> ·
  <a href="#-experiment-config">🧪 Config</a> ·
  <a href="#%EF%B8%8F-world--map">🗺️ World & Map</a> ·
  <a href="#-residents">👥 Residents</a> ·
  <a href="#-skills--actions">🎯 Skills & Actions</a> ·
  <a href="#-step-plan">⏱️ Step Plan</a>
</p>

---

## ▶️ Run

```bash
# 推荐：通过 GOD 控制台启动（会清掉旧 replay）
./scripts/god.sh new-run

# 或者：前台 CLI 跑（适合调试单步）
./agentsociety/quick_experiments/hypothesis_god_town/experiment_1/run.sh
```

启动完成后打开：

```text
http://127.0.0.1:5174/pixel-replay/god_town/1
```

## 🧪 Experiment Config

整个实验由两份文件描述。GOD 控制台读它们启动 live session，replay 也基于同一份契约。

| 文件 | 作用 |
| --- | --- |
| [`init/init_config.json`](init/init_config.json) | 世界 + Agent 初始化：地图模块、初始位置、10 位居民 profile、shared 世界上下文。 |
| [`init/steps.yaml`](init/steps.yaml) | Step 计划：从哪个时间点开始，自动推几步、每步多长 tick。 |
| [`run.sh`](run.sh) | 用 AgentSociety CLI 把上面两份配置拼到一起跑起来。 |

### 🌍 共享世界 (`experiment_context`)

每位居民每一步都看得到的「世界字典」：

```yaml
title:           GOD Town · The Ville 普通工作日
date / weekday:  2026-05-12 · Tuesday · late_spring
weather:         晴, 18°C, 微风
school_in_session: true     market_day: false
shared_norms:
  - 先观察再行动，不要把日常都升级成紧急事件
  - 尊重隐私，不主动转述他人秘密
  - 群消息只发公共/必要信息，私事走 direct_message
  - 见面打招呼简短自然，不进入工作话题前不要追问私事
town_facts:
  - Hobbs Cafe 是大家碰头的缓冲地
  - The Willows Market 和 Pharmacy 共用一栋建筑
  - Johnson Park 是公共空间，也是社区公告首选地
  - Oak Hill College 既有教室也有图书馆和宿舍
  - The Rose and Crown Pub 主要在傍晚和晚上活跃
language: 优先中文，必要时双语补充
```

### ⚙️ 环境模块 (`env_modules`)

```yaml
PixelTownSocialEnv:
  map_manifest_path:           custom/maps/the_ville/town.yaml
  default_group_name:          The Ville Daily Life Chat
  movement_tiles_per_second:   8.0      # 角色在地图上的视觉移动速度
  movement_min_steps_per_trip: 3        # 跨地点最少占多少 step
```

10 位居民在 t=0 时的初始位置：

| 公园 🌳 | 市场 🛒 | 学校 🏫 | 药房 💊 | 咖啡馆 ☕ | 供给店 🛠️ | 家 🏠 |
| --- | --- | --- | --- | --- | --- | --- |
| Alice · George | Bob · Mei | Charlie · Farah | Dana | Elena | Ivan | Hana |

## 🗺️ World & Map

地图源自经典 [The Ville](https://github.com/joonspk-research/generative_agents) 像素小镇，被裁剪为 **10 个语义地点 + 65 个交互**。地图清单见 [`custom/maps/the_ville/town.yaml`](../../../custom/maps/the_ville/town.yaml)。

<table>
<tr>
  <td align="center" width="20%">🏠<br/><b>家</b><br/><sub>9 个交互</sub><br/><sub><i>做饭 · 在家吃饭 · 睡觉 · 居家休息 · 整理家务 · 在家阅读 · 居家办公 · 视频家人 · 浇花</i></sub></td>
  <td align="center" width="20%">🏫<br/><b>学校教室</b><br/><sub>7 个交互</sub><br/><sub><i>上课 · 教书 · 课后学习 · 备课 · 批改作业 · 课后答疑 · 教研例会</i></sub></td>
  <td align="center" width="20%">📚<br/><b>学校图书馆</b><br/><sub>6 个交互</sub><br/><sub><i>阅读 · 图书馆学习 · 资料查阅 · 借书 · 还书 · 安静办公</i></sub></td>
  <td align="center" width="20%">☕<br/><b>Hobbs Cafe</b><br/><sub>7 个交互</sub><br/><sub><i>简餐 · 咖啡聊天 · 咖啡馆值班 · 点咖啡 · 外带 · 随性碰头 · 整理咖啡馆</i></sub></td>
  <td align="center" width="20%">🌳<br/><b>Johnson Park</b><br/><sub>8 个交互</sub><br/><sub><i>散步 · 见朋友 · 长椅休息 · 公园碰头 · 晨练 · 观鸟 · 简单野餐 · 公共播报</i></sub></td>
</tr>
<tr>
  <td align="center" width="20%">🛠️<br/><b>Harvey Oak 供给店</b><br/><sub>6 个交互</sub><br/><sub><i>清点货架 · 准备用品 · 修理工具 · 上货 · 顾客接待 · 借出工具</i></sub></td>
  <td align="center" width="20%">🛒<br/><b>Willows Market</b><br/><sub>6 个交互</sub><br/><sub><i>买食物 · 店铺值班 · 蔬果补货 · 议价 · 送单 · 和老客闲聊</i></sub></td>
  <td align="center" width="20%">💊<br/><b>Willows Pharmacy</b><br/><sub>6 个交互</sub><br/><sub><i>买药 · 药房咨询 · 续方 · 量血压 · 整理药架 · 上门准备</i></sub></td>
  <td align="center" width="20%">🍻<br/><b>Rose and Crown Pub</b><br/><sub>5 个交互</sub><br/><sub><i>酒馆社交 · 酒馆用餐 · 看比赛 · 晚间闲聊 · 主持小活动</i></sub></td>
  <td align="center" width="20%">🛏️<br/><b>Oak Hill 宿舍</b><br/><sub>5 个交互</sub><br/><sub><i>宿舍休息 · 宿舍用餐 · 宿舍自习 · 公共区休闲 · 视频家里</i></sub></td>
</tr>
</table>

<sub>每个交互都是结构化的：`allowed_location_ids` 限定能在哪里发生，`effects` 决定动作描述、状态、情绪和发到群里的消息。</sub>

#### 🎬 一条交互长这样

```yaml
- id: public_announcement
  name: 公共播报
  description: 在 Johnson Park 向群组发布公共公告或提醒。
  allowed_location_ids: [park]
  effects:
    action:        "{agent_name} 正在公园发布一条公共公告"
    status:        socializing
    emotion:       focused
    latest_event:  "{agent_name} 在公园发出了一条公共公告。"
    group_message: "{agent_name} 在公园通知大家：{message}"
```

## 👥 Residents

10 位居民共享 5 个维度的设定，但每个人物性格、节奏、负担都不同：

<table>
<tr>
  <td align="center" width="20%">🧭<br/><b>Jiuwen Alice</b><br/><sub>♀ · 34 · 社区协调员</sub><br/><sub>温和、守时、责任心强</sub></td>
  <td align="center" width="20%">🛠️<br/><b>Jiuwen Bob</b><br/><sub>♂ · 45 · 五金店主</sub><br/><sub>务实、嘴短心软</sub></td>
  <td align="center" width="20%">📖<br/><b>Jiuwen Charlie</b><br/><sub>♂ · 39 · 中学历史老师</sub><br/><sub>耐心、克制、爱讲故事</sub></td>
  <td align="center" width="20%">💊<br/><b>Jiuwen Dana</b><br/><sub>♀ · 41 · 药房护理员</sub><br/><sub>专业、温和、谨慎</sub></td>
  <td align="center" width="20%">☕<br/><b>Jiuwen Elena</b><br/><sub>♀ · 36 · 咖啡馆老板</sub><br/><sub>外向、热情、有分寸</sub></td>
</tr>
<tr>
  <td align="center" width="20%">🎒<br/><b>Jiuwen Farah</b><br/><sub>♀ · 16 · 高中学生</sub><br/><sub>好奇、敏捷、社交略紧张</sub></td>
  <td align="center" width="20%">📮<br/><b>Jiuwen George</b><br/><sub>♂ · 68 · 退休邮递员</sub><br/><sub>慢热、幽默、记忆好</sub></td>
  <td align="center" width="20%">💻<br/><b>Jiuwen Hana</b><br/><sub>♀ · 28 · 远程工程师</sub><br/><sub>安静、严谨、新搬来</sub></td>
  <td align="center" width="20%">🦺<br/><b>Jiuwen Ivan</b><br/><sub>♂ · 52 · 安全志愿者</sub><br/><sub>稳重、克制、爱观察</sub></td>
  <td align="center" width="20%">🍅<br/><b>Jiuwen Mei</b><br/><sub>♀ · 47 · 蔬果摊主</sub><br/><sub>风风火火、爱开玩笑</sub></td>
</tr>
</table>

### 🧬 Profile 字段（每个居民都有）

| 维度 | 字段 |
| --- | --- |
| 🪪 **身份** | `age` · `gender` · `role` · `family` · `housing` · `economic_status` · `health` |
| 🧠 **心智** | `persona` · `emotional_baseline` · `language_style` · `quirks` · `triggers` · `dislikes` |
| 📅 **节奏** | `daily_routine` · `detailed_routine` (morning · late_morning · noon · afternoon · evening · night) |
| 🤝 **关系** | `relationships` · `social_network` (9 条名->标签) |
| 🎯 **目标** | `needs` · `worries` · `secrets` · `short_term_goals` · `long_term_goal` · `goal` · `constraints` |
| 🎒 **状态** | `inventory` · `recent_history` · `skills` |

### 🪟 Profile 速写示例 · Alice

```yaml
role:               社区协调员 / neighborhood coordinator
emotional_baseline: calm, attentive
language_style:     温和、简短，先问候再切入事项；不爱使用感叹号
inventory:          [手机, 钥匙, 小笔记本, 签字笔, 一瓶水]
needs:              [完成今日邻里巡看, 确认 George 状况, 回 Bob 关于公告的消息]
worries:            [周末活动场地未敲定, George 最近少出门]
secrets:            [前任也是社区志愿者, 月初家里出过一次小漏水自己修的]
quirks:             [写小纸条贴在咖啡馆柜台留言, 习惯说『好的、我记一下』]
long_term_goal:     让镇上常规事务不依赖她个人也能稳定运转
```

完整 profile 见 [`init_config.json`](init/init_config.json) ·
其他 9 位居民同样精细，包括秘密、小怪癖和最近的小事。

## 🎯 Skills & Actions

每位居民有 5 个 **JiuwenClaw 风格的 skill id**。这些 id 不是装饰 —— `skill_runtime` 关闭时它们作为人物画像让 LLM 知道「能做什么」，开启后会被注册为实际可调用的工具。


🧭 **Alice** · 社区协调
```text
community.coordinate
conflict.mediate
first_aid.basic
notice.write
messaging.group
```

🛠️ **Bob** · 工具与维修
```text
tools.repair
inventory.count
route.localmap
ledger.basic
neighbor.support
```

.... 详见 <a href="init/init_config.json"><code>init_config.json</code></a>

## ⏱️ Step Plan

实验默认从早晨 8:20 开始，每个 step 推进半小时模拟时间：

```yaml
start_t: "2026-05-11T08:20:00+08:00"
steps:
  - type: run
    num_steps: 4         # 自动推 4 个 step（约两小时）
    tick: 1800           # 1800 秒 / step = 30 分钟
```

之后你随时可以从控制台 **暂停 / 提问 / 干预 / 继续推进**，整个过程依然遵循同一份初始 config —— GOD 只是在合适的时机改写下一步而已。

## 📂 Files

```text
experiment_1/
├── README.md              ← 你在看
├── run.sh                 ← AgentSociety CLI 入口
└── init/
    ├── init_config.json   ← 10 位居民 + 共享世界 + 环境模块
    └── steps.yaml         ← 起始时间 + step 计划
```

> 自定义自己的实验？复制整个 `experiment_1/`，改完丢到 `quick_experiments/<your_hypothesis>/<your_experiment>/`，把 `GOD_EXPERIMENT` 指过去就行。或者从 GOD 控制台的 **Setup Wizard** 一键生成新副本。
