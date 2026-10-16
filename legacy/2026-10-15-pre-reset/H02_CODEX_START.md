# H02 — 本地 Codex 执行入口（2026-10-14）

**执行入口：** [完整交接书](research/handoffs/h02-20261014/HANDOFF_H02.md) · [启动指令](research/handoffs/h02-20261014/CODEX_START_PROMPT.txt) · [补丁目录](research/handoffs/h02-20261014/patches)

给本地 Codex 的单句任务：

> 在 `research/behavioral-edge-20261013` 分支，完整读取本文件及交接书，核对 PR #1、最新 HEAD 和本地工作区；按 P0 → P1 → P2-A 的顺序推进。每个阶段先测试，再以独立 commit 非强推到同一研究分支，并核验与新 HEAD 一致的 GitHub Actions。若有缺数据、CI 失败或权限障碍，输出可复现的 BLOCKED 报告，不要编造进展。完成后由用户邀请 ChatGPT 审核提交。

## 不可违背的边界

- **禁止更改或合并 `main`；PR #1 保持 Draft**；不 force-push。
- **禁止访问、下载、计算或解锁 `2026-07-01 ~ 2026-09-28` 真实留出集**。允许仅用合成记录验证日期拒绝逻辑。
- **不更改冻结策略 `config/b0.yaml`、交易成本参数或研究阈值**；不运行参数寻优。
- **不把 D 收盘/09:35 后信息作 D 09:35 信号**；分钟有量 ≠ 真实成交证明。
- 缺官方逐股涨跌停价、PIT ST/停牌或分钟线认证时必须 BLOCKED；不生成正式 H02 费用后净值结论。
- 不得覆盖用户本地未提交工作；Token 不进仓库、不打印日志；不提交授权原始行情。

## 执行顺序

1. **P0**：检查并审阅 `patches/h02_hardening_v2_20261014.patch`，修复分钟线时间精度/非有限价格及官方涨跌停价校验；全量 `pytest`、smoke、配置校验；独立 commit → push → 新 HEAD 绿色 CI。
2. **P1**：仅在 P0 全部验收通过后，审阅 `patches/h02_portfolio_price_guard_20261014.patch`；修复非法价格污染账户、保持 T+1 和费用语义；独立 commit → 新 HEAD CI。
3. **P2-A**：仅在前两阶段完成后，做最小候选 symbol-day 数据来源/结构/PIT/成交资格覆盖矩阵。最多选择一个小样本增量；数据不全则输出缺口、来源、阻断原因，不进入收益回测。
4. 用交接书第 6 节格式交回报告：实际 SHA、具体测试/CI 链接、证据覆盖、阻断项和唯一下一步。不因任务耗时而更改目标或装作完成。

## 本次交接资料的状态

2026-10-14 交接快照：PR #1 [Draft](https://github.com/RuthlessCreature/Logic-B-Iteration/pull/1)，当时 HEAD `f0addddcd42a82cad28e1b3856721b13c9af40b8`，[旧 HEAD CI](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38420733550) 为 success。**此快照不代表此后未变化**；本地 Codex 必须重新查询。两份 patch 都是待验证候选补丁，不能把此前独立测试当成完整 CI。

**建议 Codex 从仓库根目录开始：** `git status --short` → `git fetch origin research/behavioral-edge-20261013` → `git switch research/behavioral-edge-20261013` → 阅读交接书 → 基线测试 → P0。工作区不干净则停止，切勿直接 switch。

本文件仅是入口；**以完整 [HANDOFF_H02.md](research/handoffs/h02-20261014/HANDOFF_H02.md) 的验收条件为准。**
