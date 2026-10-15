# Logic-B · Luna Goal（当前训练/验证窗口）

**最新 Goal 唯一使用：2025全年训练（2025-01-01—2025-12-31），2026上半年开发验证（2026-01-01—2026-06-30）。** 旧2020年测试记录和`config/research.json`保留用于历史回归，不属于本轮模型训练或策略选择。历史受保护区间2026-07-01—09-28不得访问。

[**Luna 新 Goal 执行规范**](docs/LUNA_GOAL_2025_TRAIN_2026_VALIDATE.md) · [**可直接复制的 Goal 提示词**](docs/LUNA_GOAL_PROMPT_2025_2026.md) · [心理和Logic A交接](docs/HANDOFF_LUNA_BEHAVIORAL_MARKET_SYSTEM.md) · [离线Codex / 未来Runtime DeepSeek+Jev架构](docs/RESEARCH_VS_RUNTIME_ARCHITECTURE.md)

**研究系统**：Codex/OpenAI探索赚钱/亏钱效应、冰点修复、市场情绪和Logic A核心交易逻辑；使用选股宝事件和BaoStock日K/5分钟K，按真实日期/T+1/费用/涨跌停拒单模拟1万元账户。每轮保存假设、参数差异、训练权益曲线、最大回撤与失败原因。训练完冻结一版，2026H1只用于评价，不得反向调参。

**未来工程Runtime**：DeepSeek负责结构化盘中语境，TypeSafe Jev负责分类/风险评分，确定性引擎负责硬闸和Follow。二者目前DISABLED、未连接、未付费，不进行自动实盘交易。R2/D1也尚未连接，GitHub Actions磁盘为临时的。

## 当前已经实现的可见仪表板（纯合成演示，**不是实际交易成绩**）

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m logic_b.goal --dataset examples/goal_toy_2025_2026.json \
  --config config/goal_2025_2026.json \
  --proposals examples/proposal_example.json \
  --data-root data --out runs/goal_2025_2026_demo
```

在本地打开`runs/goal_2025_2026_demo/dashboard.html`；同时有 `training_equity.svg`、`validation_equity.svg`、`iteration_history.csv/json`、`storage_inventory.json`、冻结训练冠军信息及两个独立1万元账户的数据曲线。

[GitHub Actions 演示（含可下载HTML/SVG/CSV/JSON附件）](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38709918043) — **只用合成数据，绝不等同于实际2025训练或2026验证**。

## 真实数据入口（需正常获取与缓存2025/2026行情）

```bash
# 2025年1月最多20交易日的分区试跑
python -m logic_b.pipeline --start 2025-01-01 --end 2025-01-31 \
  --max-sessions 20 --config config/goal_2025_2026.json \
  --out runs/real-2025-jan

# 2026年1月类似执行；全窗口需要月分区累积、稳定存储和两个样本集整合
```

**真实训练/验证整个窗口的获取、公司行动/数据缺口修复及长期存储尚未完成。** 失败的数据分区需要按源代码记录并重试，禁止未经证据显示全期正收益。详见最新 Goal 规范。

## 验收只看真实交付

1. 实际XGB/BaoStock数据覆盖 + 每月实际存储文件数/字节数，R2是否真正连上。
2. 2025训练：V0和每次心理/状态/核心规则的差异、收益、回撤、成本、失败/拒单和可视资金曲线。
3. 训练冻结前不看2026结果；冻结后2026上半年开发验证的独立曲线和风险。
4. 可复现数据及代码SHA、GitHub Actions附件、能否人工Follow或NO_FOLLOW。

[执行检查点](research/GOAL_CHECKPOINT.md)；旧代码及H01/H02原文保存在 `legacy/2026-10-15-pre-reset/`。
