# GOD 快速开始

从一台干净机器进入配置向导，再跑到 GOD 控制台所需的最短路径。

> English: [QUICKSTART.md](QUICKSTART.md)

---

## 1. 前置依赖

需要安装：

- Python 3.11+
- Node.js 与 `npm`
- [`uv`](https://docs.astral.sh/uv/)
- `screen`（推荐，让本地服务稳定跑在后台）

macOS：

```bash
brew install python node uv screen
```

确认环境：

```bash
python3 --version && npm --version && uv --version
```

## 2. 克隆

```bash
git clone https://github.com/XiaoLuoLYG/GOD.git
cd GOD
```

## 3. 启动

```bash
./scripts/god.sh start
```

`start` 是日常使用的一键入口；它可以重复执行，已经运行的服务会被复用。

第一次运行会自动完成：

1. 从 `.env.example` 创建 `.env`。
2. 安装 Python 和 Node 依赖。
3. 启动 setup 模式的后端/控制台。
4. 在浏览器打开 `/setup` 配置向导。
5. 等你保存模型配置，并选择启动路径。
6. 启动完整栈，创建 live session，先跑完第 1 步，并打开控制台。

<p align="center">
  <img src="docs/assets/screenshots/02-setup-wizard-zh.png" alt="GOD 实验配置向导" width="100%" />
</p>


向导里有两条路径：

- **保存模型并运行默认实验**：直接启动内置 GOD Town 默认实验。
- **保存并继续配置参数**：填写场景，生成可编辑实验草案，调整 agent/steps，最后点击 **保存并启动**。

必需的三个配置：

| 变量 | 示例 |
| :-- | :-- |
| `GOD_LLM_API_KEY` | `sk-...` |
| `GOD_LLM_API_BASE` | `https://api.openai.com/v1` |
| `GOD_LLM_MODEL` | `gpt-5.4` |

任意 OpenAI 兼容接口都可以。API key 只保存在本地 `.env`；浏览器只会拿到脱敏后的状态。

之后如果想创建另一个实验，运行：

```bash
./scripts/god.sh configure
```

## 4. 打开控制台

启动完成后，脚本会自动打开控制台，并打印类似这样的 URL：

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

`new-run` 会停止服务、清掉上一次 replay/run 状态，并开一个干净的 live session。

## 7. 日常命令

```bash
./scripts/god.sh start     # 可重复执行；已运行的服务会被复用
./scripts/god.sh setup     # 只安装/检查依赖
./scripts/god.sh configure # 通过配置向导创建新的实验副本
./scripts/god.sh restart   # 先干净停止，再重新启动
./scripts/god.sh new-run   # 清掉 replay 数据，开一个新 session
./scripts/god.sh status    # 查看 URL、端口和模型状态
./scripts/god.sh stop      # 停止所有服务
./scripts/god.sh tail      # 跟随日志
./scripts/god.sh open      # 在浏览器里打开前端页面
```
