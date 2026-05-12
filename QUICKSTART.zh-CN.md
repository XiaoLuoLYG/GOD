# GOD 快速开始

从一台干净机器跑到 GOD 控制台所需的最短路径。

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

第一次运行会自动完成：

1. 从 `.env.example` 创建 `.env`。
2. 询问 LLM API key、API base URL、模型名。
3. 安装 Python 和 Node 依赖。
4. 启动完整栈，创建 live session，并先跑完第 1 步。

需要的三个配置：

| 变量 | 示例 |
| --- | --- |
| `GOD_LLM_API_KEY` | `sk-...` |
| `GOD_LLM_API_BASE` | `https://api.openai.com/v1` |
| `GOD_LLM_MODEL` | `gpt-5.4` |

任意 OpenAI 兼容接口都可以。

## 4. 打开控制台

启动完成后，脚本会打印类似这样的 URL：

```text
http://127.0.0.1:5174/pixel-replay/god_town/1
```

打开它，你应该能看到像素小镇、居民列表、step 控制条和实时控制台。

## 5. 验证

```bash
./scripts/god.sh status
```

所有服务都应显示 `up`。

## 6. 跑一个新实验

如果 UI 里还显示旧的 replay 数据，清掉重来：

```bash
./scripts/god.sh new-run
```

它会删除上一次的 run，并开一个干净的 live session。

## 7. 日常命令

```bash
./scripts/god.sh start    # 可重复执行；已运行的服务会被复用
./scripts/god.sh restart  # 先干净停止，再重新启动
./scripts/god.sh stop     # 停止所有服务
./scripts/god.sh tail     # 跟随日志
./scripts/god.sh open     # 在浏览器里打开控制台
```
