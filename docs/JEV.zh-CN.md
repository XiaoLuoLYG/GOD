# Jev 技能选择对照

GOD 可以在 JiuwenClaw 决策的同时，询问 [TypeSafe Jev](https://docs.typesafe.ai/api) 应选择哪个已挂载技能。这是需要主动开启的实验：记录 Jev 的答案，实际执行的技能、参数、理由和摘要仍来自 JiuwenClaw。它尚不能证明提速，也不改变 Ask/Intervene 行为。

在仓库根目录 `.env` 中配置：

```dotenv
GOD_JEV_SHADOW=1
TYPESAFE_API_KEY=your-key
GOD_JEV_MODEL=jev-latest
```

重启 GOD，再运行一个仿真 step。开启后会将 Agent 档案、实验背景、观察、待处理干预和技能描述发送给 TypeSafe，并产生 API 用量。默认关闭。需要复现实验时，将 `GOD_JEV_MODEL` 固定为 API 实际返回的模型版本。

现有 Agent 快照和 step 日志中的 `last_skill_decision.jev_shadow` 会记录状态、选择、置信度、概率分布、模型、token 用量、请求耗时，以及是否与最终选择的技能一致。原有 JiuwenClaw 请求耗时仍在后端日志中。选择一致率不代表正确率。

两个请求并行运行。对照请求最多等待五秒，因此 JiuwenClaw 更早完成时，可能增加这段等待。缺少 key 或技能数量不在 1–255 范围时记录为跳过；超时、HTTP 失败和无效响应记录为错误。它们不会替换原有决定或既有后备逻辑。错误记录不包含响应正文或密钥。

无需启动小镇即可做一次真实连通性检查，在 `agentsociety/` 下运行：

```bash
uv run python scripts/check_jev.py
# 隔离工作区可以使用已有本地配置：
uv run python scripts/check_jev.py --env-file /path/to/GOD/.env
```

该命令通过同一个生产客户端发送一个包含两个技能的虚构示例。退出码 0 表示响应有效，不代表行为质量已经验证。没有 key 时会以 `missing_api_key` 和退出码 1 结束。本地 HTTP 测试覆盖协议、失败情况和原决策保留；真实质量、延迟和成本仍需实际 API key 验证。

无需新增依赖。设置 `GOD_JEV_SHADOW=0` 并重启即可关闭。
