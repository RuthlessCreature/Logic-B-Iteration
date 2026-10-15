# Logic-B — 离线研究大脑 vs 在线运行大脑（Luna 必须遵守）

**2026-10-15 用户纠正 / 高优先级架构决策。** 此文是 [Luna 总 Handoff](HANDOFF_LUNA_BEHAVIORAL_MARKET_SYSTEM.md) 的角色权威解释，后续代理以本架构为准，不可把 DeepSeek / Jev 当作 Codex 的“研究备用模型”，也不可因现在未接入就将它们从未来生产架构删除。

## 0. 用户真实诉求（不可误解）

**研发期**：OpenAI **Codex** 是主研究/工程 Agent，利用历史市场数据、参与者心理假设、Logic A 语义与真实价格回测，不停生成候选规则、运行实验、剔除失败模型和打磨系统。实验运行于 GitHub Actions / 本地 / 独立训练计算环境。

**工程应用/运行期**：当一个策略版本通过历史复现和前向观察后，**日常每个交易日自动执行的分析服务不能依赖 Codex 在聊天里临时推理**。应由轻量、低延迟、成本可控、可部署的独立 Runtime 来工作；**DeepSeek 和 TypeSafe AI Jev 是规划中的两类运行时 AI 推理组件**，按实际任务决定是否启用/怎样组合。必须预留可实际接入的API与服务边界，而非只有“备用模型”的空配置。

**运行时≠自动实盘交易**：生产级日常信号可供人工 Follow。用户未单独明确授权之前，不允许连接券商自动下单或付费调用第三方 API。当前 DeepSeek/Jev 均 DISABLED / RESERVED；架构以未来正常投入生产为设计目标。

## 1. 两个独立子系统，不得混为一谈

```
┌────────────────────── OFFLINE RESEARCH / TRAINING ──────────────────────┐
│ 2020-01-01..2026-06-30 历史事实 + Logic A 人类交易语义 + 心理机制假设   │
│        → OpenAI Codex 设计假设/工程实现/测试/反证/真实价格回测          │
│        → 策略迭代/参数选择/交易成本与T+1审计/时间前向评估             │
│        → 冻结版本：strategy.json + feature_schema + thresholds        │
│                  + risk_policy + model_route + data_manifest + sha    │
└────────────────────────────┬───────────────────────────────────────────┘
                             │ 审核/人工批准/可回滚版本发布
                             ▼
┌───────────────────── DAILY RUNTIME / INFERENCE ─────────────────────────┐
│ 供应商实时/日内合法可见证据 → 固定时间戳特征 → 状态引擎/候选排序       │
│             ├── deterministic baseline/hard RiskGate（必须存在）       │
│             ├── Jev typed decision: choice / score / noul（未来启用） │
│             └── DeepSeek contextual inference / concise explanation   │
│                                      / anomalies（未来启用）          │
│                 → 只允许使用部署的冻结版本＋特征协议                   │
│                 → 09:35结果 / HOLD / SELL / CASH / NO_FOLLOW           │
│                 → 人工审阅、行情/风险确认、纸面交易与日志记录           │
│                  （券商真实自动下单：未授权，不在当前项目范围）         │
└────────────────────────────┬───────────────────────────────────────────┘
                             │ 自然产生的新事实、日终真实结果
                             ▼
       Store（私有R2 Parquet行情 / 可选D1研究元数据 / 回测和决策日志）
                             │
                             └── 后续 Offline Codex 批量复盘迭代
```

### 绝对区分

| 维度 | **Offline Research：OpenAI Codex** | **Daily Runtime：DeepSeek / Jev + deterministic** |
|---|---|---|
| 目的 | 想清楚策略能否赚钱、验证心理机制、设计并迭代策略 | 执行已批准、已冻结的决策协议，生成可审阅日常信号 |
| 输入 | 历史分段数据、已完成的资金交易、失败案例 | **当时刻已可见**的行情、状态、仓位、冻结模型版本 |
| 可修改策略/实验 | **可**提交新研究版本，不覆盖基准；充分回测 | **不可**修改策略、阈值、风控、交易规则 |
| 推理预算 | 大、异步任务/批处理，不要求09:35毫秒级结果 | 小、明确截止时刻/延迟与成本预算，可熔断 |
| 后端 | Codex Agent / CI / GitHub /研究工作站 | 独立 Python service / scheduler / 可迁移的 Worker |
| 输出 | 版本包+证据、历史回测、实验结论、发布建议 | 当日状态、候选、硬闸、辅助信号、审阅决定与日志 |
| 失败处理 | 保留失败实验，定位并重跑 | 模型超时/失效按明确退化路径；高风险、数据缺失则 NO_FOLLOW |
| 可复现 | 每次代码、数据、版本、种子、测试/CI | 每次输入快照、策略sha、模型响应与调用时间可重放 |
| 是否必需 | 当前研发主力 | **规划中必需的工程能力**，但未授权前仅预留/离线mock |

**“训练”一词**：这里主要指 Codex 负责假设、特征、统计模型拟合、回测优化和策略版本冻结，不表示必然要微调一个LLM；DeepSeek/Jev 的 Runtime 可直接用 API 推理，不假设必须训练参数。

## 2. Runtime 严格分工：不是把三个模型塞进同一个 prompt

**确定性市场/风控引擎（必要、无模型时可独立运转）**：
- 数据清洗、来源核对、staleness/PIT截止时刻、交易日历、ST与代码映射、价限/IPO/停牌。
- 计算 MarketBreadth、昨日强势股负反馈、死亡池/修复、板块结构、MarketState 核心物理特征。
- 从前一日涨停体系生成最多3只候选、确认最多1个核心或 CASH。
- 强制 MarketGate、T+1、1万元目标本金、买卖各万2.5单笔最低5元、手续费/税、涨停拒买、跌停拒卖、空仓与人工Follow。
- 任何AI提供的建议都不能改写真实行情、风险闸门、成交规则、券商委托。

**Jev / TypeSafe DecisionProvider（未来的 *runtime 小推理器*）**：
- `choice`：基于固定合法 MarketEvidence 的 ATTACK/TRIAL/NEUTRAL/RETREAT/ICE 状态**辅助判断**。
- `score`：负尾部/连跌锁仓的结构化风险分。
- `noul`：前期核心负反馈是否扩大/修复的概率判断。
- 返回**类型约束的概率/评分**供规则调用；未完成特定A股数据校准前只做shadow指标列，不是投资者真实心理测量；只允许收紧风控，不允许解除确定性硬闸。
- Provider 协议：`src/logic_b/decision_providers.py`；配置：`config/decision_providers.json`。

**DeepSeek / RuntimeLLMProvider（未来的 *runtime 语境分析器*）**：
- 从**已经标准化且时间合法的**市场快照中，辅助判断板块叙事变化、风险异常、候选之间的证据冲突，输出**严格结构化**的 `context_tags, risk_flags, supporting_feature_ids, confidence, rationale_short`。
- 可以为人类Follow形成**可追溯的解释**，但未经测试不能用未验证叙事覆盖数值特征，更不能凭语言打通硬风控。
- 请求有固定schema、字符/Token上限、最大等待、费用预算，结果必须有 `asof, input_sha256, provider/model/version, response_sha256, status`。
- 未来用 `DEEPSEEK_API_KEY` 经安全存储启用，不准把 DeepSeek 作为“Codex做不好研究时自动fallback的智力替代品”。
- 既有 `src/logic_b/llm_providers.py` 当前只定义研究文本提案适配；**须新增单独 RuntimeLLM 协议**，不能直接把 research.py 里的训练期摘要 schema 用于盘中推理。
- Runtime 不依赖 OpenAI API 才能执行日常信号；Codex的职责是把模型路线和冻结规则离线测试好并发布，不承担日常同步决策。

**模型融合（原则）**：不是模型投票。以用户批准的版本Manifest指定每个Provider负责哪一个*typed output*，先确定性硬闸，后辅助解释/评分；研究期明确比较纯确定性、+Jev、+DeepSeek、两者协同的**边际经济贡献**，在未证明收益前不能自动叠加。缺少Provider结果时，`NO_FOLLOW`还是降级到已验证的纯规则路径，由事先冻结的 `degraded_mode` 明确规定；默认 **NO_FOLLOW**。

## 3. 冻结策略交付包 / Research → Runtime Promotion Contract

只有离线实验完成后才允许发布新候选版本，不能因为 Codex 写了一个 prompt 就发布：

```
strategies/<version>/
  strategy.json            # 明确 universe/时点/排名/空仓/退出
  feature_schema.json      # 与历史训练特征完全同定义
  regime_thresholds.json   # MARKET_GATE状态机及规则，训练期冻结
  risk_policy.json         # 日内停止/数据失效/退出锁单
  routing.json             # 规则主路径+可选Jev/DeepSeek任务及退化行为
  model_manifest.json      # 供应商、模型、prompt_hash/版本/温度
  eval_summary.json        # 按年度费后收益、MDD、压力/拒单、数据覆盖
  data_manifest.json       # 来源、截止、SHA/实采比例
  approval.json            # 默认未批准；批准责任为用户
```

部署只能读取已批准且**不可变**的Manifest SHA；无法提供特征或版本不匹配→ FAIL CLOSED。Runtime不得为“适应盘面”自动编辑阈值、实验数据或利润假设。回滚选择上一个**已验证**版本，或 CASH/NO_FOLLOW，不按模型自信程度越权。

## 4. Runtime 运行阶段（不是现在直接花钱上生产）

1. `RESEARCH`：Codex 离线迭代，历史2020-2026，执行器不联网券商；模型API可由单独授权的研究预算管理。
2. `SHADOW`：实际行情时间推进，Jev/DeepSeek未来可先在用户授权后**只读推理**，输出与确定性引擎的差异，不改变当天选择。
3. `PAPER`：按真实到达时刻生成模拟委托、延迟和拒单，持续检查因果可得性、延迟/费用。
4. `LIVE_REVIEW`：形成每天可供用户 Follow 的提示；默认需要用户确认；不自动向券商发送委托。
5. `LIVE_EXECUTION`：**未授权/未实现**。若未来要自动执行，需独立授权、券商/API合规审核、生产风控及kill-switch，不能靠修改一个开关无审计地开通。

历史样本截止 2026-06-30 只是**离线训练/回测范围**；后续运行时会有当前真实交易日，不能把`FIRST..LAST`硬编码到全部Runtime API，导致2027年以后无法用。**但也绝不能因此打开原有2026-07-01..09-28受保护历史留出集**：历史回测读取与新前向采集必须分开建门禁；任何试图重放受保护窗口的请求一律拒绝，真实新日期需通过独立实时源并按时序保全。

## 5. 日常 09:35 一次完整决策的接口约束

输入 `RuntimeSnapshot`（由确定性数据层完成）：
- `decision_at`（Asia/Shanghai时区）、`trade_date`、交易日历合法性、前一日完成事件。
- `market_evidence`、`sector_evidence`、`core_candidates[<=3]` 每字段 `event_at, available_at, quality, source, sha256`。
- `portfolio` 的真实可得现金和T+1锁仓状况（账户信息仅本地，**不发送给第三方模型**）。
- `strategy_version`、`policy_sha`、`feature_schema_sha`、`market_data_snapshot_sha`。
- `provider_mode`（`DISABLED|SHADOW|ADVISORY`）以及配置版本；`AI_STATUS`可为 `OK/TIMEOUT/INVALID_SCHEMA/STALE/UNAVAILABLE/DISABLED`。
输出 `RuntimeDecision`：
- `action=CASH|HOLD|SELL|BUY_CORE`（仅依已冻结策略+硬闸的许可）；
- `review_status=NO_FOLLOW|MANUAL_REVIEW_ONLY`；
- `selected_core`、拒绝候选及理由、市场状态、风险标记、可得性；
- `jev` typed evidence和`deepseek`结构化解释**若启用**；
- `decision_at, computed_at, elapsed_ms, deadline_met, fallback_reason, provider_calls, model_version, snapshot_sha, policy_sha`；
- `orders_transmitted=0`（当前所有模式）。

**硬超时**：截止09:35前的证据如果来不及生成，则用显式 `NO_FOLLOW`，不能借后续09:45结果假称是09:35已知。先定义服务预算与数据量测，再从真实shadow延迟分布确定timeout，不要拍脑袋承诺特定毫秒SLA。记录超时、API失败与实际付费次数。盘后单独跑的汇总不能逆填当日09:35推理。

## 6. 运行时最小工程分层和测试

```
src/logic_b/
  research.py                   # Offline OpenAI proposal/adjudication（现有）
  llm_providers.py              # 研究Provider接口（现有）
  decision_providers.py         # Jev typed runtime decision（现有，禁用）
  runtime/
    schemas.py                  # RuntimeSnapshot, RuntimeDecision, ModelAdvice
    provider_deepseek.py        # 结构化RuntimeLLM接口；最初禁用+mock
    provider_jev.py             # 包装已存在的DecisionProvider；禁用+mock
    features.py                 # PIT Market/Sector/Core features
    policy.py                   # 冻结策略Manifest读取、hard gate和fallback
    runner.py                   # 单次交易时段可重放的运行时决策编排
    audit.py                    # hash/provenance+成本/延迟/模型快照
config/runtime.json             # 默认研究/影子模式、third-party调用关闭
tests/test_runtime_*.py         # 不能自动调用外部API、冻结模型、超时、保护期、硬闸
```

**实施次序：** 首先实现统一 RuntimeSnapshot/ModelAdvice/决策编排、确定性门禁和离线mock，不增加任何付费调用；之后补真实历史与心理State/LogicA代理；只有历史实验显示它们可能提供增量、用户确认运行时API权限和预算后，再开发并启用真实DeepSeek/Jev HTTP适配。不要让一个“disabled”占位类成为最终生产完工证据。

## 7. 从此更正旧Handoff中的几句不准确表述

- 原“DeepSeek作为备用研究模型”：**更正为：DeepSeek是优先考虑的 *未来 Runtime contextual inference* Provider，也可以单独做成本对照，但绝不是 Codex研究工作的默认替代者**。
- 原“Jev只能做研究性辅助、不属于生产”：**更正为：Jev预留作为未来 Runtime结构化决策/评分服务**，在上线初期必须先经过研究和影子运行验证；即使正式使用，也只能在冻结授权的边界内发挥作用，不可突破硬风控。
- “现在禁用/未接通”是**当前实施状态**，不是“不需要工程应用”。
- Codex负责**发现/迭代/研究/发布**，DeepSeek/Jev负责未来**高频日常的受控推理**；规则引擎负责**必达约束/最终能否Follow**；用户负责**是否实盘采用/是否授权服务和支出**。
- 2020—2026的历史研究与真实时间前向运行边界是两种不同数据域，不要用一个 `LAST=2026-06-30` 锁住线上服务。

## 8. Luna 下一步硬交付（给用户看实际效果）

- [ ] 在 Handoff/README/AGENTS 明确 OFFLINE → PROMOTION → RUNTIME 的两个系统。
- [ ] `config/runtime.json` 明确三方角色：`codex=OFFLINE_ONLY`、`deepseek=RUNTIME_RESERVED_DISABLED`、`jev=RUNTIME_RESERVED_DISABLED`、`deterministic=RUNTIME_REQUIRED`。
- [ ] 一个真实可执行的**无网络** runtime dry-run：模拟MarketGate红灯=>CASH；数据过期=>NO_FOLLOW；Jev/DeepSeek禁用=>无外部调用；不能用AI输出改写涨跌停与T+1规则。
- [ ] 统一数据快照、策略/模型版本和决策日志SHA；MockProvider独立测试时间泄漏、模型异常、超时/fallback、硬风险约束。
- [ ] 真实API/在线交易与任何费用都需要用户单独批准；Luna不能通过自动化自行开通。
- [ ] 将Phase 1数据完整性/2020Q1 BaoStock 10002007纠错保持优先级，避免只画架构不跑实际回测。

**真正成功判据：** Codex可以离线研究并冻结策略；日常Runtime在用户授权后即使完全不用Codex，也能读当时数据按固定版本出稳定、可审计、成本有界、不可越过风险闸门的Follow信号。没有验证的运行时AI应该主动降级和拒绝，而不是为了输出买点就乱推理。
