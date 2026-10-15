# Logic-B / Luna 研究执行检查点

**最后手工交接**：2026-10-15。本文是交接状态，不代表异步代理已在继续执行。恢复工作前先刷新 GitHub 最新 HEAD、CI 及数据存储状态。

**唯一权威 handoff**：[`docs/HANDOFF_LUNA_BEHAVIORAL_MARKET_SYSTEM.md`](../docs/HANDOFF_LUNA_BEHAVIORAL_MARKET_SYSTEM.md)。**首先阅读 handoff 第0/2/3/4/7/9/11章，再执行**，不要恢复 legacy 旧研究流。

## 目前已确定事实

- 研究分支 `research/behavioral-edge-20261013`；PR #1 Draft / main 未合并。
- 旧 H01/H02 冻结快照：`legacy/2026-10-15-pre-reset/`。
- 当前日期窗口2020-01-01至2026-06-30，本金1万元，佣金买卖各万2.5/每笔最低5元，历史税费另算，T+1，涨停不买/跌停不卖，单票满仓/空仓有效。
- 证券ID为交易所+六位代码，ST/改名只变属性，不能换ID。
- 2020年1月16日历史试跑 `research/2020-01-initial-pilot.md`：v0阶段 -22.98%，**不是全期或真实可成交收益**。
- 2020Q1 50个交易日 Actions #38682583105 后来失败：**BaoStock 10002007**。不得说“正在运行”或有季度绩效。
- 工程存在 `collect.py`、`pipeline.py`、`replay.py`、`research.py`、`strategy.py`、`follow.py`。当前 `strategy.py` 是昨日涨停连板排序v0，**不是完整逻辑A**。
- 心理机制与Regime的完整 handoff 已完成，**策略层还未实际接入该状态机**。
- DeepSeek 的 `config/llm_providers.json` 与 `src/logic_b/llm_providers.py` 接口已预留，**disabled / not connected / no cost / no network calls**。当前主路径仍为既有OpenAI研究接口；不能宣称已把整个研究CLI迁移到可热切换的统一多Provider框架。
- R2/D1尚无实际凭据、未真正持久化到云；GitHub Actions临时缓存不是永久保存。

## Luna 下次执行顺序（任务必须有实际可运行的证据）

| 优先级 | 工作 | 阻塞 / 当前状态 | 最小验收 |
|---|---|---|---|
| P0 | 查清/修复 BaoStock 10002007 并缓存断点重试 | 2020Q1 CI失败 | 失败可定位股票+日期+API参数；单股票失败不会冲毁其他已采集分区 |
| P0 | `pipeline.prepare_demand_driven` → 增量账户状态机，消除重复整段 replay | 目前 O(N²) 风险 | streaming 与批量 replay 逐日权益相同的单元测试 |
| P0 | 除权/分红与不复权价差、锁单、退市、停牌、ST历史核算 | 经济收益可信度未完备 | 无公司行动确认时回报必须 null/UNVERIFIED，不允许虚构资金曲线 |
| P1 | R2持久层的可选Adapter + LocalStore接口 +数据清单 | 没有R2凭据 | 离线mock、自带校验恢复，不宣称已连网 |
| P1 | MarketEvidence/as-of/MarketState负反馈 v1 | 只有研究规范，没有代码 | 每天带时间合法证据ID的状态/UNKNOWN与MarketGate；不可未来泄漏 |
| P1 | V0 vs 仅加MarketGate的V1，相同费用/数据比较 | 尚无足够全期价格 | 交易账本、拒单、空仓、尾部风险、年净值并排比较；负结果保留 |
| P2 | 扩展板块状态/核心确认/队列强化假设与反证 | 需要补齐数据 | 不假称观察真实投资者账户盈亏，独立基准与负控制 |
| P2 | LLM唯一主研究者提出有边界的版本迭代，人工Follow | 现有CLI只有3个v0参数 | 只读训练事实，固定版本，有数据哈希和风险/拒单/年结果，NO_FOLLOW可接受 |

## 每次提交后在此文件追加

- UTC/中国时间与最新commit SHA及成功/失败Actions URL
- 数据源、日期范围、已采集与缺失的交易日/股票分钟分区，版本哈希
- 测试通过/失败及真正的回测收入/风险结果
- 本次完成的工程功能与仍未得到证据的市场/心理猜想
- 下个可执行动作，明确的阻断或需要用户授予的权限

**禁止**：按测试数量宣布盈利优势；用户不在场时购买服务；访问2026-07-01..09-28保护留出集；未经允许自动下单；不经时间审计就给心理因果命名。
