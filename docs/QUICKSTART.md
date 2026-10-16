# Luna Goal 2025训练 / 2026H1验证 — 当前操作入口

请优先阅读 [Goal硬合同](LUNA_GOAL_2025_TRAIN_2026_VALIDATE.md)。
**活动数据窗口为2025-01-01..2026-06-30，2025仅训练、2026H1仅验证。** 原本2020年Q1采集指南只供legacy参考。

先跑纯合成可视化（不等于真实回测）：

```bash
python -m pip install -e ".[dev]"
python -m logic_b.goal --dataset examples/goal_toy_2025_2026.json \
  --config config/goal_2025_2026.json --proposals examples/proposal_example.json \
  --out runs/goal_2025_2026_demo
```

真实2025年1月来源试跑（需网络，BaoStock/选股宝历史源可能失败，需要逐分区记录和恢复）：

```bash
python -m pip install -e ".[data,dev]"
python -m logic_b.pipeline --start 2025-01-01 --end 2025-01-31 \
  --max-sessions 20 --config config/goal_2025_2026.json --out runs/real-2025-jan
```

数据根目录物理存储统计采用`src/logic_b/goal.py`；`data/`和`runs/`默认被Git忽略，没有R2连接不得称长期保存。真实月度覆盖和市场状态模型仍由Luna后续实现。

---
