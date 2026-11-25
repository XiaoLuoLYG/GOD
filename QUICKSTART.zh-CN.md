# GOD 快速开始

从一台干净机器进入配置向导，再跑到 GOD 控制台所需的最短路径。

> English: [QUICKSTART.md](QUICKSTART.md)

---

## 1. 前置依赖

需要安装：

- macOS/Linux：Python 3.11+、Node.js 与 `npm`、[`uv`](https://docs.astral.sh/uv/)、`screen`、`lsof` 和 `curl`
- Windows：PowerShell 5.1+ 和 `winget`；启动脚本会补齐缺失的 Git、Node.js LTS/npm 与 `uv`

macOS：

```bash
brew install python node uv screen
```

Windows 如果还不能执行 `git clone`，先运行 `winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements` 安装 Git，或直接下载仓库 ZIP。

## 2. 克隆

```bash
git clone --depth 1 https://github.com/XiaoLuoLYG/GOD.git
cd GOD
```

## 3. 启动

macOS/Linux：

```bash
./scripts/god.sh start
```

Windows PowerShell：

```powershell
.\scripts\god.cmd start
```

`start` 会复用当前仓库目录启动的服务。如果端口已被其他应用占用，终端会提示端口和要在 `.env` 中修改的配置项。修改后再运行 `start`。

如果正在使用内置 JiuwenClaw 的旧版 GOD，请在更新代码前先运行 `stop`。升级到 JiuwenSwarm 后，首次启动会沿用原有的运行时实例工作区，并将其中的智能体数据复制到新目录。

第一次运行会自动完成：

1. 从 `.env.example` 创建 `.env`。
2. 安装 Python 和 Node 依赖。
3. 启动 setup 模式的后端/控制台。
4. 在浏览器打开 `/setup` 配置向导。
5. 等你保存模型配置，并选择要打开的实验。
6. 为这个当前实验启动完整栈，创建 live session，先跑完第 1 步，并打开控制台。

<p align="center">
  <img src="docs/assets/screenshots/02-setup-wizard-zh.png" alt="GOD 实验配置向导" width="100%" />
</p>


在向导的 **模型** 页选择居民运行时，填写下表的 GOD 模型配置，再点 **测试连接**。向导会发一条短消息验证模型能回复。选了 Codex 时，向导还会用一个临时 Codex 会话发测试消息。

点 **保存并选择实验**，打开 **浏览内置实验**，在 GOD 小镇或北大访问实验旁点 **一键启动**。第一帧完成后会自动打开控制台。可以从 [GitHub 发行包](https://github.com/XiaoLuoLYG/GOD/releases/tag/public-site-packs) 或 [AtomGit 发行包](https://atomgit.com/yigeluo/GOD/releases) 下载实验包，再在同一页点 **导入实验 Zip**。也可以进入草案编辑器创建自己的实验。

| 变量 | 示例 |
| :-- | :-- |
| `GOD_LLM_API_KEY` | `sk-...` |
| `GOD_LLM_API_BASE` | `https://api.openai.com/v1` |
| `GOD_LLM_MODEL` | `gpt-5.4` |

服务地址和所选模型需要支持 OpenAI 兼容的聊天补全接口。密钥保存在本地 `.env`，请求会发给你配置的模型服务。实验选择保存在 `.god/current_experiment.json`。还没有模型账户时，可以先体验 [GOD 小镇浏览器回放](https://xiaoluolyg.github.io/GOD/replays/god-town/)。

之后如果想切换两个内置实验，或创建另一个实验，运行：

```bash
./scripts/god.sh configure
```

## 4. 打开控制台

启动完成后，脚本会自动打开当前实验的控制台，并打印类似这样的 URL：

```text
http://127.0.0.1:5174/pixel-replay/god_town/1
```

如果浏览器没有自动打开，手动打开这个 URL。你应该能看到像素小镇、居民列表、step 控制条和实时控制台。

## 5. 验证

```bash
./scripts/god.sh status
```

后端和控制台应显示 `up`。当有居民使用内置运行时选技能或回答 Ask 时，启动器会启用 JiuwenSwarm 服务。

### 选择 Agent 后端

运行 `./scripts/god.sh configure`（Windows 用 `.\scripts\god.cmd configure`）可以更改 **默认居民运行时**。

| 向导选项 | 需要准备什么 |
| --- | --- |
| **JiuwenSwarm** | 运行时随 GOD 提供，启动器会在首次使用时安装依赖。填写模型服务配置即可。 |
| **OpenAI 兼容 API** | 准备服务地址、密钥和模型名。可以连接在线服务，或已在本机运行的兼容服务。 |
| **Codex** | 需要较新的 Codex CLI 和本机登录。按向导提示在终端运行 `codex login`。GOD 的实验草案和全局摘要仍使用 GOD 模型配置。[安装 Codex CLI](https://learn.chatgpt.com/docs/codex/cli) |

本机缺少 Codex 或尚未登录时，向导会给出安装和登录指引。也可以选另外两种运行时继续。若想在当前实验应用新配置，点 **保存并继续当前实验**。

仿真推进时，居民收到的消息、环境变化和待处理的干预会发到该居民的 Codex 会话。点名 Ask 也会发到同一个会话。Codex 保存对话历史，GOD 继续保存世界状态、技能记忆和回放，并把上一轮技能执行结果带回会话。`restart` 会续接当前 run 的会话，`new-run` 会开始新的会话。对于实验中关闭记忆的居民，Codex 每次使用临时会话。

实验可在 `init/init_config.json` 中用 `agent_backend` 覆盖向导默认值，单个居民还可以用 `kwargs.brain` 覆盖实验设置。已有的 `JiuwenClawAgent` 记录同样适用。

```json
{
  "agent_backend": {"type": "jev", "ask_backend": "openai_compat"}
}
```

| 后端 | 本机配置 | 能力 |
| --- | --- | --- |
| `jiuwenclaw` | GOD 的常规模型配置 | 技能选择和 Ask |
| `codex` | 本机 Codex 登录 | 独立的居民会话，接收世界消息、干预和点名 Ask |
| `openai_compat` | `GOD_LLM_API_BASE`、`GOD_LLM_API_KEY`、`GOD_LLM_MODEL` | 技能选择和 Ask |
| `command` | `GOD_AGENT_COMMANDS`，用 JSON 对象把命令配置名映射到参数数组 | 技能选择和 Ask |
| `jev` | `TYPESAFE_API_KEY` | 技能选择 |
| `decision_api` | 兼容 System One 的 `GOD_DECISION_API_URL`、`GOD_DECISION_API_KEY`、`GOD_DECISION_MODEL` | 技能选择 |
| `openai_decisions` | 官方接口用 `OPENAI_API_KEY`，兼容接口用 `GOD_OPENAI_DECISIONS_URL` 和 `GOD_OPENAI_DECISIONS_API_KEY` | 技能选择 |

只做决策的后端从已挂载且没有必填参数的技能里选。可以通过 `ask_backend` 或本机的 `GOD_AGENT_ASK_BACKEND` 单独指定问答后端。GOD 执行技能，并在运行记录中保存 `decision_backend` 和是否触发后备选择。

把服务地址、密钥和命令参数留在本机 `.env`。例如 `{"type":"command","profile":"local-agent"}` 会从本机的 `GOD_AGENT_COMMANDS` 选择命令。受信任的包装脚本从 stdin 读提示词，从 stdout 输出含 `selected_skill_id` 和 `args` 的 JSON，或输出 Ask 的纯文本答案。只需选择和问答时，在包装脚本中禁用工具。

本机已安装并登录 Claude Code 或 Cursor CLI 时，可将下面一行加入本地 `.env`。在实验的 `agent_backend` 中填 `{"type":"command","profile":"claude"}`，使用 Cursor 时改成 `"profile":"cursor"`。每次选技能或 Ask 都启动一个新进程。Cursor 的 `--trust` 针对 GOD 为这次调用创建的空临时目录。

```dotenv
GOD_AGENT_COMMANDS='{"claude":["claude","-p","--tools=","--disable-slash-commands","--no-session-persistence","--output-format","text"],"cursor":["cursor-agent","-p","--trust","--mode","ask","--sandbox","enabled","--output-format","text"]}'
```

更改后端设置后，运行 `./scripts/god.sh restart`。

## 6. 重启或重新开跑

如果只是想干净重启进程，但保留当前 run：

```bash
./scripts/god.sh restart
```

如果 UI 里还显示旧的 replay 数据，或你想开一个全新的 live session：

```bash
./scripts/god.sh new-run
```

`new-run` 会先打印当前实验的 run 目录，停止服务，只清掉当前实验的 replay/run 状态，并开一个干净的 live session。

## 7. 日常命令

```bash
./scripts/god.sh start     # 可重复执行；已运行的服务会被复用
./scripts/god.sh setup     # 只安装/检查依赖
./scripts/god.sh configure # 切换内置实验，或创建自定义实验
./scripts/god.sh restart   # 先干净停止，再重新启动
./scripts/god.sh new-run   # 清空当前实验 run，并开一个新 session
./scripts/god.sh status    # 查看 URL、端口和模型状态
./scripts/god.sh stop      # 停止所有服务
./scripts/god.sh tail      # 跟随日志
./scripts/god.sh open      # 在浏览器里打开前端页面
```

Windows 下把 `./scripts/god.sh` 替换成 `.\scripts\god.cmd` 即可。
