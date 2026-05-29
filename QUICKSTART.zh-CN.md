# GOD 快速开始

从一台干净机器进入配置向导，再跑到 GOD 控制台所需的最短路径。

> English: [QUICKSTART.md](QUICKSTART.md)

---

## 1. 前置依赖

需要安装：

- macOS/Linux：Python 3.11+、Node.js 与 `npm`、[`uv`](https://docs.astral.sh/uv/) 和 `screen`
- Windows：PowerShell 5.1+ 和 `winget`；启动脚本会补齐缺失的 Git、Node.js LTS/npm 与 `uv`

macOS：

```bash
brew install python node uv screen
```

Windows 如果还不能执行 `git clone`，先运行 `winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements` 安装 Git，或直接下载仓库 ZIP。

## 2. 克隆

```bash
git clone https://github.com/XiaoLuoLYG/GOD.git
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

`start` 是日常使用的一键入口；它可以重复执行，已经运行的服务会被复用。

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


向导里有三条路径：

- **打开 GOD Town**：直接启动内置 The Ville 小镇实验。
- **打开 PKU Trump Visit**：直接启动内置北大校园实验。
- **新建自定义实验**：填写场景，生成可编辑实验草案，调整 agent/steps，最后点击 **保存并启动**。

必需的三个配置：

| 变量 | 示例 |
| :-- | :-- |
| `GOD_LLM_API_KEY` | `sk-...` |
| `GOD_LLM_API_BASE` | `https://api.openai.com/v1` |
| `GOD_LLM_MODEL` | `gpt-5.4` |

任意 OpenAI 兼容接口都可以。API key 只保存在本地 `.env`；浏览器只会拿到脱敏后的状态。实验选择单独保存在 `.god/current_experiment.json`，所以 `.env` 不再控制启动哪个实验或哪张地图。

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

所有服务都应显示 `up`。

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
