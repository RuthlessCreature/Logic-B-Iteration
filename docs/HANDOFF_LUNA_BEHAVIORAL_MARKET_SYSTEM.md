# Logic-B / Luna 终局 Handoff：市场参与者心理 → 市场情绪状态 → 交易系统 → AI 自迭代

**交接日期**：2026-10-15  
**受众**：Luna / Codex / 下一任开发代理（必须独立理解并实施，不要只复述方案）  
**Repository**：https://github.com/RuthlessCreature/Logic-B-Iteration  
**唯一工作分支**：research/behavioral-edge-20261013；PR #1 保持 Draft，不能修改 main、合并 PR 或 force-push  
**性质**：新工程的权威需求、边界、阶段执行说明。不是策略盈利证据。本文不授权付费、实盘交易或开启未经用户同意的第三方模型。

> **项目唯一终局目标：** 利用 2020-01-01 至 2026-06-30 A 股真实历史数据，结合 Logic A 的短线交易语义、参与者心理/赚钱亏钱效应、市场情绪与状态识别，以及一个高推理 LLM 的假设生成和反证，持续迭代出可审计的个人交易系统。每个版本必须用同一套真实价格模拟、账户资金、真实约束和税费测试；最后给用户提供可以人工 Follow 或明确 NO_FOLLOW 的规则和证据。
>
> **不是**“只预测明天还会涨停的概率”；**不是**“只做 H01/H02 行为因果论文”；**不是**“不断堆条件调出最好看的净值”；**不是**“靠大模型在收盘后解释涨停就算策略”。

---

## 0. 每次启动先检查的真实现状（不得自作聪明）

1. 先读 GitHub 最新 HEAD、PR #1 和 CI，再读本文件、根目录 AGENTS.md、README、config/research.json、src/logic_b/ 下的新代码。**不要假设手册记录的 HEAD 永远最新。**
2. **历史所有 H01/H02/B0 的代码、报告、脚本、测试、工作流原样保存在** legacy/2026-10-15-pre-reset/。可**选择性提取概念、算法、数据血缘与测试思路**，但不得整目录恢复运行；新根目录才是当前工程。
3. 新根目录已具备 collector、基于5分钟 K 的 replay、fee、symbol、strategy、research、follow、pipeline。现有 strategy.py 只实现“昨日涨停连板数量/炸板次数排序”的**简化 v0**，**并未真实复原完整逻辑 A**，不得声称已经找到总龙头或市场主线。
4. 可验证的负面样本：2020-01-02 至 2020-01-23 共16个交易日、初始1万元的模拟权益为约7702.19元（-22.98%，最大回撤约-23.81%），3组已平仓交易，5次因涨停拒买、4次因跌停拒卖。证据在 research/2020-01-initial-pilot.{md,json} / Actions #38681276157。**仅是短样本、假设Bar撮合的 v0 失败案例**，不是六年回测，更不是逻辑A长期收益。
5. 2020Q1 50日扩展 Actions #38682583105 已**失败**，BaoStock 返回 10002007，未产生有效季度收益。检查错误的请求和日期/证券/频次、增加有限重试、隔离失败区间、断点续传；**不要重复说“还在跑”**。
6. `pipeline.prepare_demand_driven` 为确定持仓而重复 replay 历史前缀，有潜在 O(N²) 放大；全期运行前应该改为真正的逐日增量账户引擎。
7. 旧的2026-07-01至2026-09-28数据是**受保护的历史留出集**，**不访问、不解锁、不传给大模型、不偷偷改成验证集**。
8. 曾讨论 **Cloudflare R2 存行情 + D1 存研究元数据**，但**尚未在本项目实际部署或得到凭据**。不可声称原始数据已经永久保存在Cloudflare；GitHub Actions默认临时磁盘，原始行情不会天然持久化。
9. **DeepSeek 需要提前预留接口，但当前默认禁用**，见第9章。主研究仍用一个高推理模型；不需要先花钱启用两个模型，更不需要多模型投票。

## 1. 用户最关心的系统行为

这不是单纯的软件开发，而是“研究－回测－打磨－Follow”的循环：

```Xuangubao（涨停、跌停、炸板、题材、情绪） ─┐
                                          ├─> 不可篡改事实/时间血缘/存储
BaoStock（历史日K、5m、ST与停牌） ──────────┘              │
                                                           ↓
                                    D-1已知/ D09:35合法特征构造
                                                           ↓
                市场参与者心理代理 ─> MarketState / SectorState / CoreState
                                                           ↓
                           MarketGate → SectorGate → CoreGate
                                                           ↓
                           09:35确认/风险否决 → BUY / HOLD / SELL / CASH
                                                           ↓
                       1万元、A股T+1、限价拒单、历史税费、真实价格Bar假设
                                                           ↓
                          逐笔委托/拒绝/成交、资金净值/回撤/尾部分析
                                                           ↓
                 一个高推理LLM读取训练期证据 → 提出可证伪假设/参数
                                                           ↓
                          冻结版本 → 前向验证 → 保留/失败/弃用
                                                           ↓
                       人工 Follow 清单 / NO_FOLLOW（不自动下单）
```

用户更关心 **实际长期收益、可承受风险、犯错时如何迅速退出、没有机会就空仓**，而不是多少项 CI 或模型分数。重现“逻辑 A 的感觉”也不能代替记录清楚的机器规则。

## 2. 不可漂移的研究与交易参数

| 项目 | 固定规范 |
|---|---|
| 历史区间 | **2020-01-01 至 2026-06-30**。其他期段的数据不得作为本期收益 |
| 证券身份 | **交易所 + 六位代码**，不因 ST、*ST、摘帽、名称改变而换股票ID；ST为按日期变化的属性 |
| 事件源 | **选股宝 Xuangubao** 涨停、跌停、炸板及相关情绪/题材；要注明源返回字段的确切含义 |
| 价格源 | **BaoStock** 的原始不复权日K和5分钟K；其他免费源仅经显式审计后补充 |
| 本金 | **10000元人民币**，最多持有一只，目标使用可用现金买入100股整数手，空仓合法 |
| 佣金 | 买卖双方各 **0.00025（万2.5）**，每次成交至少5元 |
| 其他费 | 历史卖出印花税、沪深等适用过户费单列按历史日期计价，避免重复收费 |
| 执行 | A股T+1；涨停价格默认不能买进，跌停价格默认不能卖出，停牌不能凭空平仓 |
| 时间 | D-1 收盘完成的事实作为 D 候选；D 09:35 决策，当前默认09:45已完成5m Bar的收盘价进行**保守模型撮合**（非实盘真实成交） |
| 账户 | 现金不能为负、不能虚构融资、每日开平仓顺序固定、跌停无法卖出则延后退出 |
| 候选 | 参考昨日涨停体系，白名单最多3只，最终最多1只；核心不合格/买不到则空仓，不替代为后排 |
| 风险 | MarketGate在有明确高风险或时间/数据不可用时硬否决，大模型不能用故事覆盖 |
| 权限 | 不开启券商自动下单、不购买数据、不修改main、不读取旧保护留出集 |

**价格限制必须遵守制度和日期**：创业板2020年改革前后的差异、科创板、北交所、ST生效日期、IPO无价格限制、除权参考价、上市退市/停牌等。无法确定价限就标 `LIMIT_BAND_UNKNOWN` 并保守拒绝确定性成交。

分红、送转、拆股和复权问题必须解决后才能声称“经过历史公司行动处理的真实权益”；不能因不复权价格跳变误算巨亏/巨赚。无分钟数据不能宣称09:35实时成交。

## 3. 参与者心理学是重要研究层，但只能用事前观测代理

### 3.1 机制链（理论假设，不是已证明因果）

```近期可执行盈利/亏损、高辨识度股票表现、题材关注度
      ↓
参与者的信念更新：赚钱效应与模仿、风险偏好改变、恐惧、兑现、损失规避
      ↓
可观察的市场变化：板块扩散/收缩、涨停晋级、炸板失败、跌停扩散、承接/流动性
      ↓
  后续交易机会、不可成交风险、强势股负反馈与新的收益/损失
      ↘ 下一交易日反馈：进一步影响后续行为（严格滞后） ↗
```

公共K线和涨跌停池只看到**行为结果代理**，看不到真实交易者身份、持仓成本、主观预期、订单队列。**假想追涨群体的回测盈亏不是实际散户/游资收益。** 在无识别数据时对因果结论标 `BEHAVIORAL_CAUSALITY_NOT_IDENTIFIED`；这并不妨碍研究其预测/风控作用。

### 3.2 必须系统研究的8个心理假设（每个都能失败）

| ID | 理论/心理过程 | 优先统计代理 | 区分的对照与反例 |
|---|---|---|---|
| H01 | **近期胜者强化**：赚钱让追涨者更愿接力 | 固定假想核心追涨策略**可成交、费后、截止D-1**的滚动收益，锁仓与未实现亏损 | 控制同期市场指数、涨停高度、波动；区分市场牛市与真正新增信息 |
| H02 | **亏钱效应/恐慌传染** | 高位股票断板后跌停或极端亏损、昨日强势股负反馈、死尸池扩大/修复速度 | 只用大盘跌幅和波动是否已经解释？ |
| H03 | **模仿与注意力扩散** | 主线板块涨停广度/持续度、非龙头参与面与成交活跃变化 | 普涨行情、题材事后改名、虚假的同资金流向推断 |
| H04 | **预期落差** | 昨日强度与D 09:35已知的竞价/早盘承接是否相符 | 缺真实09:35数据则必须标缺失；不得用D收盘 |
| H05 | **拥挤和一致预期** | 龙头持续加速、低换手一字/板块集中、换手扩大而价格反应趋弱、开板次数 | 强趋势下拥挤也可能继续涨，检验倒U关系和不稳定区间 |
| H06 | **冰点—修复—高潮—退潮的状态转换** | 赚钱/亏钱效应、涨跌停对比、晋级率、炸板率、空间压缩和多日动量 | 与简单动量/波动状态模型比较，不能假定循环有固定顺序 |
| H07 | **获利兑现与衰竭** | 长期盈利的模拟队列 + 高位一致性 + 次日可观察承接变弱 | 波动、流动性和高度本身能否解释 |
| H08 | **主线与核心辨识度的互动** | 板块容量核心/总龙头与前排同步、扩散、板块核心失败时补涨结果 | 历史板块标签修订、事后因强势才叫“核心”的后视偏差 |

每一项**必须有**：特征定义、来源、截止时刻、观测范围、缺失率、预测目标、基准对照、风险损失样本、负对照和最后 PASS/FAIL/INSUFFICIENT。不要把它们全部塞进一个神秘的“情绪综合得分”。

### 3.3 模拟参与者（cohort）要先定策略才能计盈亏

参考队列：
- `COHORT_CORE_FOLLOW`：固定的昨日核心09:35确认后尝试交易，按照同一T+1和费用模型退出。
- `COHORT_CONTINUATION`：固定连板接力结构。
- `COHORT_FAILED_CORE`：事前定义的昨日核心断板和负反馈观察池（允许不买）。
- `COHORT_MARKET_CONTROL`：同期市场价格动量/风险控制对照。

所有队列需冻结买点、卖点、候选母体、价限、手续费、融资限制、空仓条件、交易日历。每个D状态只能读取D前**已经可观察和已经完成的结果**，不可将D+1成交、盈利和锁死当作D情绪输入。

## 4. 必须产出的三层可解释市场状态

- **MarketState**（全市场）：风险偏好、赚钱效应、亏钱效应、连板生态、负反馈、回暖/退潮。
- **SectorState**（主线板块）：主题集中与扩散、持续天数、龙头与容量票强弱、板块内分歧，可能标 `SECTOR_UNKNOWN`。
- **CoreState**（候选股票）：总龙头、容量核心、最强换手前排、明确补涨核心的可观察代理，09:35是否仍被确认；代理缺失标 `PROXY_UNCERTAIN`，不许虚构身份。

### 4.1 市场状态机：五状态 + 观测不足 UNKNOWN

| Regime | 研究意义 | 新开仓许可 |
|---|---|---|
| `ATTACK` | 赚钱效应扩散、强势核心接力/承接有效，尾部风险可控 | 继续评估后续Gate，并非强制买 |
| `TRIAL` | 冰点后可能修复，证据有限 | 研究层允许评估，实盘Follow需额外审查 |
| `NEUTRAL` | 证据矛盾/一般震荡、没有明确风险收益优势 | 默认可空仓，不能催生交易 |
| `RETREAT` | 高位负反馈和晋级失败扩散、空间收缩 | **禁止新开仓** |
| `ICE` | 严重亏钱效应、跌停/锁仓风险集中 | **禁止新开仓** |
| `UNKNOWN` | 必需数据或合法时间戳缺失（质量标签，不是心理状态） | **禁止新开仓** |

计算应先输出连续基础特征，再输出状态；状态机可设历史迟滞避免噪声跳色，但阈值只能通过训练期确定并冻结。MarketGate不可仅由单一温度数值决定。

### 4.2 状态指标最小集（不得仅看当日涨停数）

1. 涨停、跌停、炸板数量与比率（分母要正确）。
2. 首板/连板、各高度晋级率、最高板高度/断板/空间压缩。
3. 昨日强势股票的次日溢价、失败率，及高位负反馈向中位的扩散。
4. 死尸池：历史曾强势而最近遭遇明显负反馈的**事前、可机器重放名单**及其恢复占比。
5. 板块广度、主线集中度、板块核心/容量股/换手前排相对强度。
6. 最近3/5日状态变化速度、昨日亏钱效应是否突变。
7. 高位股不利时段里真实可成交退出占比及涨跌停锁单比例。
8. 隔夜整体市场风险、指数收益/波动（可得时），保证不是简单大盘效应误当心理学。
9. 情绪状态与真实账户**净收益/负尾部/回撤/空仓**的统计关系（结果不得回填当天状态）。
10. 时间与覆盖：日终数据最早于**下一个具备有效可得性证明的决策时刻**使用；不假装D日09:35已看到D日15:00涨停池。

要有 `FeatureObservation`：`feature_id, symbol(optional), event_time, available_at, decision_at, source, quality, population, value, lineage_sha256`。必须验证 `available_at <= decision_at`，缺失为 `null`而不是0。对于没有当时可见证据的题材标签，标 `EOD_ONLY/UNVERIFIED`，只用可安全滞后的版本或不使用。

### 4.3 否决链与空仓（不可补买后排）

```D-1候选池 → MarketGate → SectorGate → CoreGate
→ D09:35 ConfirmationGate（数据若缺，fail closed）
→ TradabilityGate → BUY_CORE 或 CASH
→ T+1之后按照冻结ExitRule 卖出或持有被锁仓
```

`MarketGate` 给出 `state, scores, evidence_ids, source_quality, veto_reason, last_state, transition_reason`；
`SectorGate` 输出主线是否真实存在；
`CoreGate` 输出程序代理类型并给出与人工Logic A语义差异；
`ConfirmationGate` 必须由当时分钟事实确认承接/板块证据，不得以“收盘仍涨停”代替。
不同退出规则单独版本测试，不能与入场规则一起任意修改掩盖风险。

## 5. Logic A 的研究地位

**逻辑 A = 人类交易语义，B0-H；新 v0 当前程序并不等于它。**

旧参考原则（仅提取思想，别重启旧工程）：
- 昨日涨停体系构成候选宇宙。
- 核心优先：**总龙头 → 板块容量核心 → 最强换手前排 → 明确补涨核心**。
- 市场退潮/冰点空仓。死尸池修复、证据股和板块确认可研究为观测条件，但不能凭故事放开红灯。
- 最多3个白名单候选，只选择真正核心；买不到/确认失败不转向次优股。
- 退出规则单独版本化：固定次日退出、确认失败退出、核心地位丢失、结构破位、涨停维持/开板退出。
- 用户更希望改善风险厌恶、过早止盈和冲动开仓引发的偏差。Follow必须显示**事前规则、禁止追单、拒单原因、空仓决策、明确退出与违规复盘**；不把个人心理等同市场因果。

必须有 `B0_H_REFERENCE`（人工复盘例子/规则注释）与 `B0_P_PROXY`（机器化证据）两层。程序代理和人类判断不一致就记录 `PROXY_MISMATCH`，不能根据未来收益反向调整人工“真值”。

## 6. 数据与存储：Cloudflare R2/D1 只是推荐方案，未获凭据不得宣称上线

```XGB供应商池 + BaoStock历史OHLC
→ 本地增量缓存（可重试/可续采，按年月股票分区）
→ 内容sha256 + dataset_manifest（原始响应及规范化版本）
→ 私有R2：长期存 JSON/压缩Parquet、历史快照
→ 可选D1：策略与实验元数据、数据索引、任务检查点
→ Python/DuckDB：读取固定版本做回测
→ GitHub：仅保存代码、哈希/统计、研究报告；不公开受限制原始数据
```

**未获R2/D1密钥时**：实现抽象 `MarketStore` + `LocalFileStore` + `R2Store` 预留与mock测试，不能付费开通或伪造成功；本地 `data/` 在GitHub Actions默认是临时空间，不能当永久数据仓库。

**当前明确痛点**：2020Q1 BaoStock `10002007` 失败，不能每次重跑所有数据。
- 明确记录失败的股票、日期、周期、参数和异常码；
- 单请求有限重试＋退避，超限记录失败分区、继续其他可处理分区；
- 原始行与规范化后行均有SHA、条数、日期范围、时间语义；
- 缓存连续跨两个独立Job/执行环境能复用后才称“持久化成功”；
- 聚合分析不只存某候选股数据就称“全市场情绪”；计算全市场比例必须有真实全市场分母。
- 历史数据使用许可需遵守，云端私有存储与公开分发不等同。

## 7. Luna 工程执行阶段及真实完成证据

### Phase 1 — 修好行情与执行可信度（优先级最高）

**要实际修改代码，不只写本文：**
- 修复 BaoStock 10002007：分页/日期分块、重试与故障隔离、断点续跑；出现失败隔离时输出缺口矩阵而非全部宣告成功。
- `pipeline.prepare_demand_driven` 目前反复对历史前缀 replay，改为增量账户状态机，单程处理一交易日只一次，并保证结果与批量 replay 相同。
- 确认5m时间戳、零成交、涨停拒买/跌停拒卖、T+1、停牌、当日ST、非交易时段、IPO/板块涨跌幅、公司行动与标记价的一致性。
- 2020年1月16日v0负收益要作为固定负对照保留；修bug引起数值变化，报告差异原因，不能悄悄覆盖原报告。
- 2020年先完成连续覆盖和按日资金账本，再逐年扩大到2026-06-30；**跨年不能重置1万元再拼接**。
- 产出 `source_coverage_by_month.csv`、`trades`、`orders_and_rejections`、`daily_equity`、`yearly_metrics`、`run_manifest`，资金与交易数字有统一哈希。

**验收**：真实日期范围、证券样本、数据缺失率、公司行动数量、买卖成交/拒单理由、最大回撤都能通过相同数据快照复算。未解决公司行动时收益标 `UNVERIFIED`，不要继续报精确长期年化。

### Phase 2 — 市场心理可观察代理、Regime V1（不是先做深度模型）

新增建议目录（可细调，但接口必须稳定）：

```src/logic_b/market/
  observations.py        # 观测量、有效时间、质量与缺失理由
  asof.py                # D 09:35合法性校验
  breadth.py             # 全市场涨跌停广度/炸板
  negative_feedback.py   # 昨强负反馈、死尸池
  continuation.py        # 晋级率/空间/连板生态
  themes.py              # 板块持续/扩散/集中（若有历史合法题材）
  cohorts.py             # 固定参与者队列的含费盈亏代理
  regime.py              # ATTACK/TRIAL/NEUTRAL/RETREAT/ICE + UNKNOWN
  gate.py                # 不可绕过的风险否决与结构化理由
config/market_state_v1.json
tests/test_market_*.py
```

首先产出**逐日 MarketEvidence 与 MarketState 可解释轨迹**，即使没有赚到钱也必须能证实“状态定义时没有用未来值”。冻结阈值仅在训练段选择；逐日落 `regime_trace.csv` 与 `features_manifest.json`。
**负控制**：纯大盘动量/波动，纯涨停家数，乱序/滞后错配/随机主题；MarketRegime 加入后必须能证明增量或给出负结论。

### Phase 3 — Logic A 机器化与对照回测

只能有清晰的单变量/单规则差分版本：
- `V0_SIMPLE_STREAK`：现有昨日涨停强势优先（固定负面对照）。
- `V1_MARKET_STATE_GATE`：V0 + 仅MarketGate状态拒单。
- `V2_NEGATIVE_FEEDBACK_VETO`：V1 + 高位负反馈拒单。
- `V3_SECTOR_CORE`：增加主线和核心辨识代理（不足则 `PROXY_UNCERTAIN`）。
- `V4_CONFIRMATION`：只有当09:35早盘分钟事实已合法取得才加入承接确认。
- `V5_EXIT_VARIANTS`：分别测试退出逻辑（不和其它新变量打包）。

对比时相同历史、同一数据版本、相同资金、手数、费用、价限与成交逻辑；报告回测盈利/亏损、尾部、空仓成本、成交失败及最坏时段。禁止只用更高涨停延续率做胜利宣告。

### Phase 4 — AI 提案—反证—冻结—再迭代

模型是**研究助手，不是行情神谕**。
训练期 2020-01-01..2024-12-31；开发验证期 2025-01-01..2026-06-30。后者已被多次研究看过，**不能声称完全未触及的盲测**。因反复选择造成的数据污染要建试验日志；未来真正外部样本须另行保留并经用户授权。

研究引擎每轮做：
```固定数据快照与资本规则
→ 训练期资金/风险/市场状态证据包
→ 单个高推理LLM提出 ONE 个可反证假设（心理机制/状态/风险闸门/入场/退出之一）
→ 审核：输入是否合法、参数可得、规则能否执行、是否只改一类条件
→ 固定新版本和SHA、训练期试验
→ 按日期展开验证、与BASELINE/现金比较
→ 时间稳健性、极端尾部、税费与未成交敏感性
→ PASS / FAIL / INSUFFICIENT / BLOCKED
→ Follow审阅资格或 NO_FOLLOW
```

每个候选必须写下**失败条件**；保存失败的版本，限制搜索次数，不追着验证区间无限调参。LLM本身不直接填写收益、成交价、标签或替代程序的财务计算。允许研究证明心理指标无增益，也允许长期输出NO_FOLLOW。

### Phase 5 — 人类可 Follow，不自动下单

`follow.json` 和说明应包含：
`asof, strategy_version, data_snapshot_sha, market_state, market_evidence,
sector_state, core_candidate[<=3], chosen_symbol_or_CASH,
decision_time, confirmation, entry_eligibility, blocked_reason,
target_position, exit_rule, fees, max_known_risk, evaluation_status,
order_transmitted=0`。

没有跨年份足够数据、合法早盘特征、稳健费后收益、明确退出规则和可承受风险，就标 `NO_FOLLOW`。禁止因为用户“希望有票可买”而生造买点。

## 8. 实验验收、硬性反证、边界

- **禁止未来数据**：当日收盘涨停池不能成为09:35已知信号；不能用D+2的收益解释D早盘“赚钱效应”。
- **禁止偷换分母**：若仅下载昨天涨停池候选，只能称“候选队列负反馈”，不声称“全市场负反馈”。
- **不能在未完成成交约束下认定赢家**：涨停锁单、跌停锁仓、停牌、旧仓未退出、没有100股资金都要进账本。
- **不能靠模型叙事突破风险门**：市场退潮/冰点/UNKNOWN情况下不增加实盘跟随候选。
- **时间分段且测试污染可见**：连续开发期间的验证集被多次访问，就写“开发验证”，不许假装新独立样本。
- **心理因果性**：没有真实群体交易身份/收益资料，`BEHAVIORAL_CAUSALITY_NOT_IDENTIFIED` 是合法、准确的最终结论。
- **成本优先**：1万元账户，万2.5而最低5元导致多数组合买卖佣金约10元起，另有税费和滑点；要压住过度交易。
- **数据安全**：凭据从env/secrets加载、从不提交或输出；原始行情不上传公开repo，R2/D1没有授权前只做mock。
- **实盘边界**：用户人工审核后才能Follow；任何自动交易/付费连接都需单独明确授权。

## 9. 重要新增要求：预留 DeepSeek Provider，但现在绝不使用

用户已明确：**今后可能接入 DeepSeek，但暂时不用。现在必须把接口与配置位置留好，不影响现有唯一主研究模型。**

### 9.1 不要混淆“预留接口”和“已经接通服务”

设计 `LLMProvider` 抽象协议，输入与输出统一，默认主模型仍为现有OpenAI研究通道：
```
src/logic_b/llm_providers.py
  ProposalRequest  (run_id, train_only_payload, schema_version, max_budget, no_future_data)
  ProposalResponse (provider, model, content, request_hash, usage, provenance)
  LLMProvider      (generate_proposal)
  OpenAIProvider   (以后从当前 research.py 显式迁入/复用)
  DeepSeekProvider (先预留可注入实现或禁用占位)
config/llm_providers.json
  primary: openai
  providers:
    openai: enabled/credential_env/endpoint/model
    deepseek: enabled=false/credential_env=DEEPSEEK_API_KEY/endpoint/model=null
```

DeepSeek 已有官方 `POST /chat/completions` API；待启用时可用 `https://api.deepseek.com/chat/completions`、独立 `DEEPSEEK_API_KEY` 和**启用时从官方可用模型列表确认**的具体模型ID。模型名、价格和接口细节可能更新，不得把某个过期模型字符串永久硬编码。官方资料：https://api-docs.deepseek.com/api/create-chat-completion/ 和 https://api-docs.deepseek.com/api/list-models/ 。

要求：
1. `deepseek.enabled=false` 为默认，**无任何生产路径请求DeepSeek，不创建账户、花钱、输出密钥、不静默fallback**。
2. 禁用时调用 DeepSeek Adapter 必须报清晰 `PROVIDER_DISABLED`；未配置key/模型不得暗中切换OpenAI。
3. 待有明确用户授权时，启用 DeepSeek 只应更改配置/环境，不需要重写回测、市场状态或实验引擎；统一JSON提案schema与确定性验证器。
4. 不同Provider输出保存 `provider, model, prompt_hash, parameter_hash, response_hash, token_usage(if known), cost(if known)`；**不把不同模型的建议混合投票，不让低成本模型自行改动硬闸门**。
5. Provider只能收到训练期/当时可见的研究证据包，不得收到受保护留出集、API密钥或私人交易账户资料。
6. 可为未来“同证据同问题 A/B 比较”预留 `provider_comparison`，但当前不启用也不当作主线任务；LLM输出差异 ≠ 可执行收益优势。
7. 用mock Provider写无需联网的测试：disabled拒绝、未授权无网络访问、统一schema、缺密钥拒绝、provider来源和SHA记录。**不得为预留插件而拖慢历史数据/市场状态的核心工作。**

### 9.2 DeepSeek 验收口径

完成“预留”只能宣称：
`DeepSeek adapter RESERVED / DISABLED / NOT CONNECTED / NOT BILLED`。

只有用户另行授权、提供密钥、执行实际网络联通测试且写出运行/费用记录之后，才可称 `CONNECTED`。**现在不用完成联网、跑模型或性能PK。**

## 10. 具体交付文件、检查点、完成定义

至少形成：
```
docs/HANDOFF_LUNA_BEHAVIORAL_MARKET_SYSTEM.md      # 本文，单一新目标执行依据
AGENTS.md                                           # 指向本文的第一入口
config/research.json                                # 既有资金/日期/规则合同
config/llm_providers.json                           # 预留DeepSeek OFF
src/logic_b/llm_providers.py                        # 统一预留协议/mock防误用
research/GOAL_CHECKPOINT.md                         # 下一个执行者明确从哪里继续
research/data_coverage/                             # 年月真实覆盖率与失败请求
research/market_state/                              # 情绪特征/状态轨迹/反证
research/strategies/<strategy_version>/             # 每个固定版本输入/交易/年净值/拒单
research/follow/                                     # 人工可读Follow或NO_FOLLOW
```

Luna 按阶段实际提交代码、测试与 CI，不要一次性填满占位报告然后宣称完成。每个阶段日志必含：
`HEAD, baseline_sha, data_snapshot_sha, tested_date_window, coverage, input_feature_asof,
strategy_version, closed_trades, fees, rejections, annual_pnl, max_drawdown,
test_count, errors, unresolved_flags, next_action`。
不存在的数据写 `NOT_AVAILABLE`，不存在的历史收益写 `NOT_ESTABLISHED`，不编造数值。研究进度长期写入 checkpoint。

### 最终用户能看懂的“决策摘要”要直接回答

1. **这段市场到底是 ATTACK、TRIAL、NEUTRAL、RETREAT、ICE 还是 UNKNOWN，证据是什么？**
2. **赚钱/亏钱效应、死尸池、主线和核心发生了什么变化？哪些是事前能看到的？**
3. **昨天涨停核心中是否有真正可成交、值得关注的候选？为什么其他人被排除？**
4. **如果交易一万元，因手续费、不可成交、跌停锁仓、空仓决策会出现什么真实差别？**
5. **策略版本A与版本B在2020..2026逐年费后表现怎样？最差年份/最大回撤/极端风险怎样？**
6. **大模型为什么提出这次修改？它如何被历史反例推翻或保留？**
7. **最终人工Follow还是NO_FOLLOW？哪些数据/验证仍不足？**

**完成标准**：用户可读的策略规则+真实价格模拟账本+心理状态结构化证据+可复现跨年比较+明确风险否决；不因亏损而无限追求新版本，也不因所有单测通过便草率宣布赚钱策略已形成。

---

## 11. Luna 收到本Handoff后立即执行，而不是重新规划6轮

依次：
1. 检查最新HEAD/CI；建立或更新 `research/GOAL_CHECKPOINT.md`。
2. 创建默认禁用的 `LLMProvider / DeepSeekProvider` 预留接口及防误用mock测试，**不要连接DeepSeek**。
3. 执行 Phase 1：修复 BaoStock 10002007 和按需行情分区失败重试；把O(N²)历史重放改为增量；先保证完整1万元账本的可信度。
4. 并行建最小可解释的 P02 负反馈与 P06 市场状态特征，用2020训练段可得字段，不用验证段调阈值。
5. 做`V0_SIMPLE_STREAK`与`V1_MARKET_STATE_GATE`第一个同口径前向比较；呈现成功/失败与费后资金曲线、最大回撤、空仓差异。
6. 维护 checkpoint，写实际 commit/CI/数据哈希。用户不需要每20分钟发“继续”；但不能承诺自己没法执行的异步工作，也不能把未经用户授权的联网、密钥或实盘操作当成默认权力。

**不做**：复活旧H01/H02流水线、继续争论是否必须Tushare收费接口、为了强行证明“心理强化已被识别”而陷入无限认证、靠未经时间审计的文本叙事挑票、开启DeepSeek调用、修改main或实盘自动买卖。

**遇到失败就保留负面证据；得不出正收益也可以如实结项。用户需要的是能不断复算、升级、懂得空仓和风险约束的研究能力，而不是漂亮的幻觉。**


---

## 12. 用户新增要求：TypeSafe AI Jev 作为 **独立 DecisionProvider** 预留

**特别重要：Jev/TypeSafe 不等于 DeepSeek，更不是普通聊天LLM的另一个 model 名称。** 这是2026-10-15用户追加的第三类模型能力：Jev 是 TypeSafe AI 的 **System One 模型**，用于返回指定类型的结构化决策及概率，不负责长篇研究推理和写自然语言。不能将它随意接到 `research.py` 的 OpenAI / DeepSeek 文本提案接口。

官方来源（2026-10-15核对）：  
- TypeSafe 官网：https://typesafe.ai/  
- 官方 OpenAPI：https://api.typesafe.ai/openapi.json  
- 官方 API 文档：https://api.typesafe.ai/docs  
- 官方 POST：`https://api.typesafe.ai/v1/systemone`  
- 官方模型发现：`GET https://api.typesafe.ai/v1/models`（需要账户授权）。  
- 载荷核心：`{"model": "...", "state": {...}, "questions": {...}}`；回答用同样问题名返回。类型 `choice`、`score`、`noul`。不要采用非官方第三方托管站的 `/api/v1/decide` 作为默认endpoint；第三方钥匙与官方 TypeSafe 钥匙不通用。

已落地的**代码级预留**：
- `config/decision_providers.json`：`active_provider=deterministic`，`jev_typesafe.enabled=false`，`allow_external_calls=false`，`model=null`。
- `src/logic_b/decision_providers.py`：标准化 `DecisionRequest/DecisionResponse`、校验历史截止时间、官方问题模板、JevAdapter。**目前不含真实HTTP传输，只接受授权之后的注入transport**。
- `tests/test_decision_providers.py`：禁用不联网、无凭据不调用、受保护日期被拒、时间泄漏禁止、mock协议/输出检查。
- `docs/JEV_TYPESAFE_RESERVED_API.md`：正式独立说明与未来激活验收。

**定位：Jev 可以有帮助，但必须证明。** 未来若用户授权，考虑在**规则计算好的同一份合法证据**上，让Jev辅助完成：
1. 市场状态分类 `ATTACK/TRIAL/NEUTRAL/RETREAT/ICE`（choice）；
2. 下行尾部与跌停锁仓风险分级（score）；
3. 昨日核心的负反馈是否正在扩散（noul）。
这些输出首先只能作为研究**诊断列**，与纯规则状态机、简单统计、单一高推理LLM候选研究做配对实验，评估日期分块准确率、对数损失、校准和费后拒单价值。官方声称“校准概率”并不等于在A股市场已校准；历史性能必须另行验证。

**绝对权限与失败规则：**
- 不接实盘，不替代 MarketGate 硬否决，不单独决定买卖，不能在风险红灯时放行。
- 缺认证 `TYPESAFE_API_KEY`、没有经确认的模型ID、源数据时刻不明或用户没有明确授权 → 禁用/拒绝。
- 不自动执行 `GET /v1/models`、不申请/使用密钥、不发送受保护期间价格与个人账户信息，不产生付费请求。
- **启用时必须双开关 + 明确外部调用授权 + 审计过的 transport 实现**。连通成功且有真实账单记录以后才能标为 CONNECTED。
- 与 DeepSeek 一样，**“接口预留”不是已接入**；DeepSeek属可选语言模型Provider；Jev属独立结构化DecisionProvider；当前实际决策还是确定性规则与主研究LLM。

Luna 未来不要把“Jev直接输出5状态”当成模型已验证或已可跟随。它适合做大量、便宜、格式统一的判断任务的**候选工具**，先离线实验再判断能否提供额外经济价值。
