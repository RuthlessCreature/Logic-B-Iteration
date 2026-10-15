# H02-LT-20261014 — 本地 Codex 长任务：可重放证据链 / PIT 认证 / 合成执行账本

**执行分支：** research/behavioral-edge-20261013  
**PR：** https://github.com/RuthlessCreature/Logic-B-Iteration/pull/1 — 始终 Open + Draft，base=main，不合并  
**验收起点：** 0c6fa4ff50a8d18eb82e3477a4c31215edb31df2（开始前重新查远端；不可直接回退）  
**任务责任：** 本地 Codex 执行代码与实验；ChatGPT 在用户要求后做独立审查。  
**任务范畴：** 数据工程 Stage-0，不包含真实策略收益、优化、H02-R/C/X 统计检验或盲测。

## 1. 任务目标

将当前三股一天的覆盖表和硬编码 BLOCKED 的保守原型，推进成能够从固定、获许可的源数据 **离线重复重建** 的证据工程：

~~~text
合法源数据和历史候选池
    -> 原始字节快照、sha256、取得时间、许可与数据源版本
    -> 规范化分区sha256（与原始字节sha严格区分）
    -> 交易所日历、分钟时间语义、OHLC和跨源一致性
    -> 当日逐股官方涨跌停价 + ST/停牌有效时点证据
    -> 09:35 point-in-time检查
    -> T+1、满仓单票、费用、锁死和未成交的纯合成回放测试
    -> 每个symbol-day可审计覆盖矩阵、BLOCKED原因、CI证据
~~~

真正的投研目标是识别 **是否具备保守、可复现、合法的真实成交模拟输入**。不能把分钟交易量当做本人买单真的成交，必须区分 SIMULATED_FILL_ELIGIBLE 与 REAL_FILL_CERTIFIED。没有订单回报不得宣称后者。

## 2. 绝对边界（任何一条违反立即停止并标 FAIL）

- Git：只更改 research/behavioral-edge-20261013。禁止修改、merge、force-push main；禁止将 PR #1 转正、合并或关闭。每阶段独立 commit、push、检查新 HEAD CI。
- 留出集：严禁真实访问、下载、枚举、计算或解锁 2026-07-01 至 2026-09-28。仅允许**不读取实际数据**的合成日期拒绝测试。开发/探针样本必须在 2026-06-30 或以前。
- 冻结 B0：不得修改 config/b0.yaml、B0.0.3 规则、B0-P.1 的参数、09:35信号语义、E0退出、单票满仓、100股交易手数、T+1、费用默认值、Promotion门槛；不做扫参或优化。
- PIT：2020年回查于2026年的 retrieved_at 不等于 2020年当日 available_at。D日收盘数据、BaoStock EOD isST/tradestatus、D日09:35之后完成的分钟K不能参与D日09:35信号。任何不确定时间语义必须 UNKNOWN/BLOCKED。
- 交易真实：禁止补造缺失bar、猜测官方逐股限价、根据D收盘倒推买入、假装封板可以买或跌停能卖、停牌凭空成交、未来数据穿越、未经认证净值报告。
- 数据安全：不得提交Token/cookie/密钥或权限/许可证不清的完整市场原始字节到公开仓库；获许可的不可再分发输入只能写gitignored本地数据湖/有授权的私有对象或artifact。不得绕过付费墙；实际购买数据权限先问用户。
- 工作区：先 git status；若不干净且存在用户更改，不能 reset/clean/覆盖。安装留下的 egg-info 等文件不得提交。
- 范围限制：首先只做2020-01-03三股（000998.SZ、000716.SZ、600421.SH）。直到pilot严谨通过，禁止抓取多年/全市场分钟数据或大规模请求。
- 成功口径：如果官方权限缺失，仍继续所有可脱离权限的独立工程模块；返回真实 BLOCKED 并列明权限，不得自称数据认证通过。

## 3. 必须先做的基线检查（P0）

依次阅读 README、config/b0.yaml、H02_CODEX_START.md、docs/12_H02_EXECUTABLE_REINFORCEMENT_PREREGISTRATION.md、research/experiments/h02-stage0-20261013/、源文件和tests：
- src/logic_b/h02_coverage_matrix.py
- src/logic_b/h02_certification.py
- src/logic_b/h02_minute_audit.py
- src/logic_b/h02_independent_daily.py
- src/logic_b/providers/xuangubao_market.py
- src/logic_b/storage.py、portfolio.py、costs.py
- tests/test_h02_coverage_matrix.py、test_h02_certification.py、test_costs.py

运行：

~~~bash
git status --short
git branch --show-current
git fetch origin research/behavioral-edge-20261013
git rev-parse HEAD
git rev-parse origin/research/behavioral-edge-20261013
python -m pytest -q
logic-b smoke
logic-b validate-config config/b0.yaml
~~~

GitHub验收基线为 0c6fa4ff，Actions https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38510766188 （224 passed）。如果远端已有新提交先审阅差异，再衔接，不要覆盖；如本地树脏先处理安全停机。

## 4. 工作包（每包独立 commit、push、验新SHA的CI）

### P1 先修覆盖矩阵中的假认证统计

观察到：h02_coverage_matrix.py 对执行 READY 固定阻断是安全的，但 aggregate.PIT_certified_rows 仍按上游布尔值计数，会在伪造的数据里报告错误的认证人数/行数。

验收：
1. 保持既有 v1 JSON 输入兼容；新增或更名 claimed_PIT_rows 与 independently_verified_PIT_rows。后者须经过真正证据检验；当前没有核验器时必须0。其他被上游声称的 official_limit_rows、fill 等亦应明确区分 claimed/present 与 VERIFIED。
2. 强制校验 scope.sample_size_symbol_days 与真实行数、scope.sample_symbols 与逐行symbol集合一致；候选日/交易日/受保护日期前置检查；重复、缺列、非法类型 Fail Closed。
3. 所有源自上游的 PIT/成交 true、假SHA（包括64位全0）、假的来源标签不得使 verified>0 或总闸门 READY。
4. 完整负向与正常合成测试，且保留与当前 P2A_COVERAGE_MATRIX_20261014.json 相容。

独立提交示例：fix(h02): separate evidence claims from verified metrics

### P2 原始数据 envelope + hash + 固定输入离线重放

建立小型 H02EvidenceEnvelope 合约及离线 builder，不依赖联网才能重算。必须至少覆盖：
- dataset/trade_date/symbol/provider/method/非敏感query参数/数据源版本；
- retrieved_at_utc（真实检索UTC时点）与 historical_available_at（**默认null**，只有可核验证据才可填）；
- exchange_timezone、minute_bar_label_semantics（START/END/UNKNOWN）与时间区间；
- raw_kind、raw_sha256（只有原始字节真被保留才填）、normalized_sha256、row_count、schema_version；
- source_run_or_url、license/redistribution status、is_eod_reference、original_file_path；
- 认证等级 SOURCE_PRESENT / STRUCTURALLY_VALID / EOD_REFERENCE / PIT_UNVERIFIED / PIT_VERIFIED 或 BLOCKED原因。

约束：
- 不得用 Pandas转换后的JSON SHA冒充原始响应字节 SHA。
- 写本地不可变分区，manifest 与源字节hash绑定；校验 tamper、row count、源/日期/证券代码不一致；断点重试、原子写入、不可静默覆盖更权威已有数据。
- 提供少量**合成**原始输入fixture和离线重放命令；同一固定原始字节稳定输出；被破坏的一个字节必失败。公开仓库不得纳入真实付费行情。
- 网络抓取与重放彻底分离。若许可证不允许保留原始响应，就明确 SUMMARY_ONLY / RAW_UNAVAILABLE，不可以声称已离线完整复现。

交付模块 + pytest + docs/H02_EVIDENCE_CONTRACT.md（或等价）+ CLI / 可执行脚本 + 固定输入重放证明。

### P3 历史1分钟时间语义与跨源异常

仅围绕2020-01-03三股：
- 000998.SZ、000716.SZ 各245根；旧供应商结果各有11:31–11:35五根，不在常规连续竞价时段。调查原始Unix tick_at、时区、供应商分钟标注究竟是开头还是结束时刻、上海/深圳交易所午间规则、可能的撮合/分钟编码特例。不能直接删除、重标签或放宽session门让它PASS；存疑状态 UNRESOLVED。
- 必须证明“09:35标记的一分钟bar在09:35已完整且可获”。如果源定义为09:35—09:36，则不能当09:35信号；没有文档/原始证据则标 UNKNOWN 和 BLOCKED。
- 000716.SZ BaoStock日线与分钟open、low差人民币0.02；分别研究集合竞价、首根bar开盘口径和未复权价格差。**不得修改0.011容差来掩盖差异**；记录精确差、来源和不确定性。
- 600421.SH 为历史ST参考、148根分钟，不可因数量不足就定性为停牌/坏记录。
- 输出 P3_MINUTE_TIMESTAMP_AND_CROSS_SOURCE_AUDIT.md + machine-readable JSON + 测试与追溯。来源不明则如实 BLOCKED，不用结论填空。

### P4 官方逐股限价/ST/停牌/PIT数据权限双路线

权限分支：先只检查是否存在 TUSHARE_TOKEN，不显示Token；在授权且接口可读时仅获取2020-01-03三个样本的官方 up_limit、down_limit、ST/停牌历史状态。每一项需校验逐股逐日唯一性、有限正数、板块/ST/IPO特殊规则、价格单位、是否复权、生效/公示时间。

无权限分支：基于合法授权公开来源探查能否获得**真实逐股逐日**官方或等同权威证据。不能用固定5%/10%/20%带替代。未找到就写 BLOCKED_NO_AUTHORIZED_OFFICIAL_LIMIT_SOURCE，交付 provider contract + 合成fixture + 能明确拒绝来源推断的测试，并继续 P5/P6。

ST/suspend由BaoStock EOD给出的历史标签只标 HISTORICAL_EOD_REFERENCE，直到另有盘前生效证据才能 PIT_VERIFIED。付费采购或绕过源访问限制均禁止。

交付 source capability / licensing / permissions matrix（不得泄漏凭证）、三股逐股比对或明确阻碍文件。

### P5 证据驱动Verifier（不能凭上游声明认证）

让 h02_coverage_matrix.py 只做统计与序列化，单独实现 h02_evidence_verifier.py（或等价），必须读取实际缓存源字节及可信清单并核对，得出：
SOURCE_PRESENT -> BYTE_REPLAY_VERIFIED -> REFERENCE_CROSSCHECKED -> PIT_INPUT_VALIDATED -> SIMULATED_EXECUTION_INPUTS_READY，或可枚举的BLOCKED原因。

必须防御：伪SHA/全0SHA、原始文件变更、伪PIT、D日收盘反填09:35、分钟END/START时钟不明、缺官方限价、重复股日、ST与IPO异常、异常现金或手续费、空或坏来源、时间跨日/重复分钟、受保护真实日期请求。未经核实的来源不可把 filled/ready直接置true。

注意：“一分钟正成交量”最多说明该分钟出现市场交易，绝不等于模拟委托确定成交。没有真实订单回报不得输出 REAL_FILL_CERTIFIED。

提供可运行的 CLI 或 python -m 模块输出固定 JSON 的每层认证原因。全部合成测试PASS不等于真实源认证PASS。

### P6 合成 T+1 / 手续费 / 锁死执行账本

**仅synthetic输入；当前三股真实样本不具备可认证成交输入。**
- 单票满仓目标、100股整数手；T+1当日不许卖；09:35用作信号的bar不能同时成交。
- 涨停封死无法买、跌停锁死无法卖、停牌继续持仓、复牌后继续处理、分钟数据空/价格无穷/量无效、部分成交或不成交原因。最低佣金/券商费/过户/卖出印花税在账本独立列出，不改变冻结默认费率。
- 余额/持仓/equity需保持有限，费用合法；执行状态变迁和下一交易日行为可复核。
- 使用已有B0执行器，避免创建不兼容的第二套策略含义；没有真实券商订单流不得宣称真实成交已证明。
- 输出小型 synthetic_execution_ledger.json、单元/属性测试与误差理由，不生成历史收益曲线。

### P7 离线三股样本矩阵重放 + 允许条件下扩量

从许可允许保存的不可变源文件重放所有七层：
calendar / candidate D-1 / independent daily D / historical ST D / historical halt D / official limits D / candidate minute 1m D，附来源、sha、时间有效性、认证等级、PIT及成交资格、阻断原因和分母。

先处理三股；必要证据缺失就明确 BLOCKED，不能以“3/3 fetched”写“3/3 tradable”。如果原始许可与timestamp没法解决，无需硬扩量。

仅在三股原始字节重放/语义认证通过后，可按checkpoint分片有限扩至2020年1月，以之前2020年1月声称985个候选symbol-days作为待核对分母（不直接硬编码为事实）。这属于数据覆盖研究，不属于2024—2026开发集收益拟合。不得获取2016、2026保护留出集等其他范围。

交付 P7_EVIDENCE_REPLAY_REPORT.md、JSON、脚本命令、实际源/许可/剩余阻断说明。

## 5. DAG与持续自主执行

~~~text
P0 基线
 ├─ P1 指标与claim分离（完全离线）
 ├─ P2 hash快照与离线可复现系统（合成）
 │   ├─ P3 时间标签/源差异调查（限额真实查证）
 │   ├─ P4 官方数据源权限（可BLOCKED）
 │   └─ P5 verifier（合成先完成，真实不可越门）
 ├─ P6 合成执行账本（无真实外部权限）
 └─ P7 三股小样本实测/报告（不能取得数据则BLOCKED）
~~~

**不准因为P4缺Token就停止P1/P2/P5合成/P6。** 每包提交后CI核对，保存进度到 research/experiments/h02-stage0-20261013/H02_LONG_TASK_PROGRESS.md。可以跨本地Codex会话续跑，但不许在报告里把未运行任务写成已完成。GitHub不可访问时只可保存安全本地commit，说明失败，不得声称已经push。

## 6. 最小验收硬门

| Gate | 能判PASS的证据 | 不足则 |
| --- | --- | --- |
| G0 Git边界 | 全部提交仅研究分支；PR始终Draft、base=main；未访问保护数据 | FAIL |
| G1 claim/verified | 任何上游虚假PIT/成交/哈希无法使认证计数>0/READY | FAIL |
| G2 原始复现 | 固定真实或合成原始byte源，SHA、schema、行数验证，可离线重算 | PARTIAL/BLOCKED |
| G3 timestamp | 09:35结束语义和午间bar解释有证据；否则明确UNKNOWN | BLOCKED |
| G4 逐股官方限价与ST | 合法独立来源、2020有效性与历史可用时点证据 | BLOCKED |
| G5 合成执行 | T+1/费用/锁死/不可成交/无效行情全测试PASS | FAIL |
| G6 真实可成交 | 未完整获得数据严禁发真实策略净值，缺门就阻断 | BLOCKED |
| G7 CI | 每新HEAD对应CI通过，真实日志含pytest/smoke/config结果 | FAIL/PARTIAL |

任何阶段的实验失败必须保留。不能调整校验阈值使报告变绿，不能通过小样本优化策略。不能报告H02-R/C/X显著性，也不能把合成账本收益当历史真实净值。

## 7. 交接报告格式

每包完成必须在GitHub记录进度：
stage / PASS-PARTIAL-BLOCKED-FAIL / exact commit SHA / CI URL / pytest实际数量 / 新证据 / 许可状态 / 输入SHA / 不确定假设 / 阻断 / 下一步。

最终返回：

~~~markdown
# H02-LT LOCAL CODEX REPORT
基准/最终HEAD、PR状态、工作区状态
P1..P7 逐阶段PASS/PARTIAL/BLOCKED/FAIL和每次提交CI
每层输入数据证据（原始SHA vs 规范化SHA、检索时点 vs 历史可获时点、许可证）
三股样本异常调查：11:31-11:35、000716.SZ差0.02、600421.SH稀疏bar、官方限价/ST/停牌
合成订单T+1/费用/锁死结果（不是实盘收益）
确认证据覆盖分子/分母、剩余BLOCKED项
策略冻结/main/holdout未触及的核对证据
唯一下一步及验证命令
~~~

用户随后让ChatGPT“验收 H02 长任务”时，ChatGPT重新从GitHub核验，不采信仅由Codex自报的 PASS。

## 8. 任务依据

- 上轮P2A: https://github.com/RuthlessCreature/Logic-B-Iteration/commit/1e787f2c925136a95af27df87e4bfd19e0e8ea77
- 本轮P2B基准: https://github.com/RuthlessCreature/Logic-B-Iteration/commit/0c6fa4ff50a8d18eb82e3477a4c31215edb31df2
- 224 passed CI: https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38510766188
- 官方数据凭证缺失历史探针: https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38403924915
- PR: https://github.com/RuthlessCreature/Logic-B-Iteration/pull/1

**任务一经开始，必须重新检查当前远端HEAD、现有文件和GitHub Actions，不得以本文件为最新事实的保证。**
