# Luna Goal 执行检查点 — 当前2025训练 / 2026H1验证

**2026-10-15用户最后一次重新锁定样本。** [权威规格](../docs/LUNA_GOAL_2025_TRAIN_2026_VALIDATE.md)；[完整Goal提示词](../docs/LUNA_GOAL_PROMPT_2025_2026.md)。旧2020-2026实验内容在文件下方的历史注释中，不再主导当前执行。

- **TRAIN=2025-01-01..2025-12-31; VALIDATION=2026-01-01..2026-06-30**，两个独立1万元账户，验证只用于最终冻结后的评估。
- **当前已编码：** `config/goal_2025_2026.json`；`src/logic_b/replay.py` 可识别新时期与旧回归；`research.py` 同理；`src/logic_b/goal.py` 导出每轮训练对比、训练/验证资金曲线的SVG、HTML仪表板、实际本地文件字节清单。
- **CI已证明：** [合成Goal Demo #38709918043](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38709918043)，并生成HTML/CSV/SVG/JSON附件。它是演示数据，不是2025/2026真实行情。
- **尚未完成：** 真实2025/2026H1行情持续存储、按月份数据大小/Parquet、全年训练/验证逐笔账本、心理状态/Logic A迭代和最终真实验证、R2/D1连接。
- **仍须优先修复：** BaoStock按股票/日期/频次请求错误`10002007`；历史数据失败重试和存储持久化；增量单遍组合回测与公司行动。
- **严格边界：** `legacy/`及2020年旧实验不进入本轮训练；受保护2026-07-01..09-28不访问；未经授权不调用DeepSeek/Jev或开付费云API，也不下单。
- **迭代可视化：** 每轮记录`iteration/strategy_sha/hypothesis/train_cash_equity/train_mdd/trades/taxes_and_fees/veto/KEEP_OR_REJECT/git_sha/run_url`；**验证仅训练冠军冻结之后打开一次**，不可反向选择。

下一步：逐月采真实2025和2026H1数据，给每个月的文件数/实际字节、数据源失败分区及缓存命中数量；完整训练V0与第一个MarketState版本的同口径净值曲线；最终再跑验证，不要在合成Demo后停工。

---

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


## 2026-10-15 追加：Jev / TypeSafe DecisionProvider

用户明确要预留 **Jev by TypeSafe AI**。官方 `POST https://api.typesafe.ai/v1/systemone`（`choice/score/noul`）；官方 `GET /v1/models`，不是第三方托管的 `decide` 网关。已建立 `config/decision_providers.json` + `src/logic_b/decision_providers.py` + `tests/test_decision_providers.py`，状态 **RESERVED / DISABLED / NOT_CONNECTED / NOT_BILLED**。它与禁用的DeepSeek文本Provider相互独立。决策主路径仍是确定性证据+MarketGate；Jev未来也只能作为研究性辅助，不允许买卖下单/放开风险硬否决。详见 `docs/JEV_TYPESAFE_RESERVED_API.md` 和 Handoff 第12章。


## 2026-10-15 用户再次明确：**离线研究与生产Runtime不是一回事**

现在优先读 [Codex研究→Runtime上线架构](../docs/RESEARCH_VS_RUNTIME_ARCHITECTURE.md)。OpenAI Codex负责**离线探索、训练、回测、优化、规则版本冻结**。**DeepSeek与Jev将来用于实际生产系统的日常运行时推理**，前者分析结构化市场上下文与风险线索，后者做类型化状态分类、尾部风险、负反馈评分，均不能突破确定性MarketGate/成交规则。现在均 DISABLED / NOT_CONNECTED，用户未授权费用和API，不可擅自调用。已建立 `config/runtime.json`、`src/logic_b/runtime.py`、`tests/test_runtime.py` 作为无网络骨架。Luna要以 *研究发布包→shadow→paper→人工Follow* 为工程目标，不允许将两者当作两个可随时替换的聊天模型。历史研究只到2026-06-30，实时生产日期独立前进，不得触碰2026-07-01..09-28的历史受保护样本。

## 2026-10-15 最终分层工程校验（后续Luna务必读）

- **当前真正入口**：`docs/RESEARCH_VS_RUNTIME_ARCHITECTURE.md`；Codex离线历史训练/研究/实验/回测/策略版本发布 vs DeepSeek/Jev**将来真正部署的生产Runtime推理**，不是三个科研Agent。
- `config/runtime.json` / `src/logic_b/runtime.py` / `src/logic_b/runtime_cli.py`：离线运行时影子决策，确定性MarketGate、合法证据时间、事件前日约束、模型默认禁用、策略未批准返回NO_FOLLOW。演示：
  `python -m logic_b.runtime_cli --snapshot examples/runtime_shadow_snapshot.json --out runs/runtime-shadow/decision.json`。
- `src/logic_b/runtime_deepseek.py`：**独立于research.py**的未来生产上下文推理协议，输入仅许可的实时状态、输出严格的标签/证据ID/风险/解释，默认禁用且无真实HTTP传输/不产生调用费。
- `src/logic_b/decision_providers.py`：Jev类型化Runtime适配，额外支持 `scope=forward_live` 日期域；原2026-07-01..09-28历史保护不变。Jev尚未连接API。
- `src/logic_b/llm_providers.py` 的旧研究提案形状**不能当生产Runtime的DeepSeek协议**；OpenAI仍是Codex主研究通道。
- 已通过 [GitHub Actions #38704176111](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38704176111)：**65 tests passed**，历史合成账户烟测通过，Runtime dry-run输出`NO_FOLLOW / STRATEGY_NOT_PROMOTED / model_calls_executed=0 / orders_transmitted=0`。
- **不要误报“DeepSeek/Jev已经实用”**：两者只是接口、未来运行角色及离线mock，可选真实网络激活尚未授权；后续在策略历史验证/心理市场状态构建之后，按Shadow→Paper→人工Follow逐步兑现Runtime职责。
- 仍须优先处理 BaoStock 10002007、持久数据存储、真实全期回测、市场心理/状态机的可验证特征，不能因为Runtime骨架单测通过就停止主工程。
