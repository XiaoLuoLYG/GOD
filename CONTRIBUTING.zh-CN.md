<h1 align="center">🤝 为 GOD 做贡献</h1>

<p align="center">
  <b>欢迎提 issue 与 PR。</b><br/>
  <sub>无论是修一个错别字、加一张地图，还是重写一段 runtime —— 谢谢你。</sub>
</p>

<p align="center">
  <a href="CONTRIBUTING.md">🌏 English</a>
</p>

---

## 🧭 你可以怎么贡献

| | |
| --- | --- |
| 🐛 **报 bug** | 提一个 [issue](https://github.com/XiaoLuoLYG/GOD/issues/new)，附上复现步骤、截图，以及 `./scripts/god.sh status` 的输出。 |
| 💡 **提需求** | 先提一个 issue，简短描述 + 一段使用场景就够。 |
| 🗺️ **加新地图** | 把文件夹丢到 `agentsociety/custom/maps/<your_map_id>/`，遵循 [`docs/MAP_PACKAGES.zh-CN.md`](docs/MAP_PACKAGES.zh-CN.md)。欢迎 PR。 |
| 🧪 **加新实验** | 把文件夹丢到 `agentsociety/quick_experiments/<your_hypothesis>/<your_experiment>/`。参考 [`hypothesis_god_town/experiment_1/`](agentsociety/quick_experiments/hypothesis_god_town/experiment_1/README.zh-CN.md) 的形态。 |
| ✏️ **改文档** | 修翻译、打磨措辞、加截图、加图示。 |
| 🔌 **接 Runtime** | 欢迎为新的 LLM runtime 或 persona 模板提 adapter PR —— 见 `agentsociety/custom/agents/`。 |

## 🚀 开发环境

```bash
git clone https://github.com/XiaoLuoLYG/GOD.git
cd GOD
./scripts/god.sh start
```

会自动装好 Python 和 Node 依赖，启动完整栈，创建 live session，先跑完第 1 步，
让控制台打开时就是已初始化的小镇。改完代码刷新即可。

常用命令：

```bash
./scripts/god.sh restart    # 先干净停止，再重新启动
./scripts/god.sh new-run    # 清掉 replay 数据，开一个新 session
./scripts/god.sh status     # 查看端口、URL、模型状态
./scripts/god.sh tail       # 跟随日志
./scripts/god.sh stop       # 停止所有服务
```

## 🌳 分支与 PR 流程

1. Fork 仓库，从 `main` 拉一个 topic 分支。
2. PR 要 **小而聚焦** —— 每个 PR 只做一件事。
3. 跑你改过部分的校验器：

   ```bash
   # 改过地图包
   cd agentsociety
   uv run python scripts/validate_map_package.py custom/maps/<map_id>

   # 改过 Python 服务
   cd agentsociety/packages/agentsociety2
   uv run pytest
   ```

4. 把 PR 提到 `main`。正文里写清楚 **改了什么** 和 **为什么**。UI 改动配上截图或短视频效果更好。
5. 耐心等等 —— reviewer 可能在另一个时区。

## 📝 代码风格

- **Python:** 4 空格缩进，必要的地方加类型注解，不要留无用 import。
  目前没有强制统一 formatter，跟周围代码风格一致即可。
- **TypeScript / React:** 跟周围组件风格保持一致。
- **行宽:** 合理的地方控制在 **120 字符以内**。
- **不使用前置声明**（项目规则）。
- **注释** 只解释非显然的意图，不要复述代码做了什么。
- **Commit:** 现在时、短主题（约 60 字符）、需要再加正文。
- **文档:** 同时存在 `.md` 和 `.zh-CN.md` 的，改一个就两个都改。
  请用地道的中英文，不要直译。

## 🗺️ 提交新地图包 · 检查表

- [ ] 目录名 `agentsociety/custom/maps/<map_id>/`
- [ ] 含 `map.yaml`、`README.md`、`ATTRIBUTION.md`
- [ ] Tiled JSON 包含 `Collisions` 层
- [ ] 所有图块素材路径都落在地图包内
- [ ] `uv run python scripts/validate_map_package.py custom/maps/<map_id>` 通过
- [ ] PR 正文至少附一张截图

## 🧪 提交新实验 · 检查表

- [ ] 目录在 `agentsociety/quick_experiments/<hypothesis>/<experiment>/`
- [ ] `README.md`（英文）+ `README.zh-CN.md`（中文）
- [ ] `init/init_config.json` + `init/steps.yaml`
- [ ] `run.sh` 能用 AgentSociety CLI 拉起实验
- [ ] 如果有操作员脚本，补一份手动运行说明（参考 PKU Trump 实验的模式）

## 📜 License

向 GOD 贡献内容，即表示你同意按 [Apache License 2.0](LICENSE) 授权你的贡献。
集成的上游代码（`agentsociety/`、`jiuwenclaw/`）各自保留了它们的 LICENSE / NOTICE，
对应子树仍受其约束。

## 🛡️ 友善些

GOD 是一个小型开源项目。请保持耐心、具体描述，给出你也愿意收到的那种反馈。
我们要做的是一座由 Agent 组成的小镇 —— 也希望围绕它，慢慢长出一个温暖的小社区。

---

<p align="center"><sub>谢谢你让 GOD 变得更好。⭐</sub></p>
