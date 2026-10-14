# Logic-B-Iteration / H02 本地 Codex 工程交接书

> **交接版本**：H02-HANDOFF-2026-10-14 / v1.0  
> **目标执行者**：本地 Codex（可独立阅读、修改、测试和推送代码，但不得自行变更研究边界）  
> **仓库**：https://github.com/RuthlessCreature/Logic-B-Iteration  
> **唯一允许推送的分支**：`research/behavioral-edge-20261013`  
> **既有 PR**：https://github.com/RuthlessCreature/Logic-B-Iteration/pull/1（Draft；不要合并）  
> **交接原则**：验证优先、一次只做一个可复现增量、失败即阻断，不输出未经认证的净值或超额收益。

---

## 0. 给执行代理的最高优先级指令（必须逐条遵守）

1. **不得修改、切换后提交、合并、重写、强推 `main`。只允许在 `research/behavioral-edge-20261013` 上进行非强制推送。** 不得创建或合并新 PR 代替既有 PR #1，除非用户另外授权。
2. **禁止读取、下载、跑回测、调参或解锁 `2026-07-01` 至 `2026-09-28` 的保护留出集。** 不允许 `--unlock-holdout`、不允许以测试为名绕过日期硬门。此禁令包括 CI 工作流、脚本、临时数据和新的调用路径。测试可以用合成日期验证程序会拒绝留出集，但不得访问该区间的真实行情。
3. 本轮优先级只做 **P0：合入 H02 分钟线及官方涨跌停价结构校验补丁**；P0 成功并记录绿色 CI 后，方可考虑 **P1：账户非法价格校验补丁**。**禁止同时改策略、扩大研究范围或跑收益优化**。
4. 不得修改 `config/b0.yaml` 的冻结策略参数、窗口、成本、默认成交口径、市场状态门槛和验证阈值。不得以修测试为名降低约束或删除失败用例。
5. 数据层一定要区分 `存在`、`结构有效`、`来源可追溯`、`09:35前可用`、`可成交`、`交易后净值可信` 六个证据层级；前一层成功绝不推出后一层成功。
6. 只使用时间点上已发布、可观测的信号输入。**绝不能把 D 当日盘后 OHLC、当日最终涨停名单、未来复权数据、09:35 以后交易量用于 D 日 09:35 选股。** 09:35 之后的分钟条仅用于模拟后续执行，不得反向成为选股特征。
7. 遇到数据缺失、Token 不足、样本不一致、CI 红灯或不可重现，返回 `BLOCKED` 并附证据；不得生成填补后的虚构数据，不得把年化收益留空的结果说成赚钱，也不得因为 GitHub Action 总状态成功就认定数据可用。
8. 本地有用户已有的未提交变更时，**停止并报告**；禁止 `git reset --hard`、`git clean -fdx`、覆盖用户文件或强行 `git stash`。需要保存现场的动作先请求用户确认。
9. 每次 commit 必须包含本地完整测试命令与结果，并在推送后确认 GitHub PR HEAD 确实变化、Actions 对应的是**新 HEAD**；旧绿色 CI 不算本轮通过。
10. 涉及密钥，不打印、不写日志、不写文档、不提交 `.env`、Token 或完整受许可原始行情。数据和临时实验产物必须留在 Git 忽略目录或 CI artifact（按许可与到期政策）。

## 1. 已确认事实与证据快照（2026-10-14 读取 GitHub）

| 项目 | 实测/证据 | 不得误读成 |
|---|---|---|
| PR #1 | `open`、`draft=true`、`head_sha=f0addddcd42a82cad28e1b3856721b13c9af40b8`、63 commits、base=`main` | PR 已就绪可合并 |
| GitHub 权限 | 已连接的 GitHub 身份对仓库显示 `push=true` | 本地机器一定登录了 gh 或一定有推送权 |
| 最近核验的 HEAD CI | [Run 38420733550](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38420733550) `success`；pytest / smoke / config 验证均成功 | 新补丁已合入或已测试 |
| 分钟线源文件 | [`src/logic_b/h02_minute_audit.py`](https://github.com/RuthlessCreature/Logic-B-Iteration/blob/research/behavioral-edge-20261013/src/logic_b/h02_minute_audit.py) 仍未拒绝部分非有限 OHLC / 亚分钟时间戳 | 远程已修复 |
| 官方价认证源文件 | [`src/logic_b/h02_certification.py`](https://github.com/RuthlessCreature/Logic-B-Iteration/blob/research/behavioral-edge-20261013/src/logic_b/h02_certification.py) 按代码出现与否判断逐股覆盖，未充分验证价格数值 | 有效的官方逐股价格已齐备 |
| 账户源文件 | [`src/logic_b/portfolio.py`](https://github.com/RuthlessCreature/Logic-B-Iteration/blob/research/behavioral-edge-20261013/src/logic_b/portfolio.py) 有 T+1 基础限制，但非法卖出价可能污染现金 | 全链路账户模型已认证 |
| 2020-01 历史独立日线 | 上轮报告 985/985 候选 symbol-day；源任务 [Run 38404221537](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38404221537)；**交接时未下载其 artifact 逐行重算** | PIT 09:35 ST/停牌状态已认证 |
| 官方价权限 | [Run 38403924915](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38403924915) 记录 `BLOCKED_MISSING_TUSHARE_TOKEN` | 工作流 status 绿色就代表接口可读 |
| 2020 单日分钟线 | 2020-01-03 历史 94/94 候选返回分钟集，89/94 满足当时暂设 >=180 条阈值；详见 [Stage-0 证据](https://github.com/RuthlessCreature/Logic-B-Iteration/blob/research/behavioral-edge-20261013/research/experiments/h02-stage0-20261013/FEASIBILITY_AND_DATA_GATES.md) | 六年分钟线覆盖或分钟数少即停牌 |
| H02 总体 | `BLOCKED`：未完成价格权威性、分钟来源时效性、真实可成交和联合成本审计 | 有合法净值结果 |

**必须重验**：上述快照可能在本地接手前变化。先用 `gh pr view` / `git fetch` 查真实 HEAD；若 HEAD 不等于 `f0adddd...`，停止直接套补丁，改为人工 review 补丁与新代码的差异。上轮本地专项测试通过不等于本地整仓测试或 CI 通过。PR 描述正文可能落后于当前 HEAD，不可把它当作最新任务状态。

### 补丁清单（由交接方附带）

- `patches/h02_hardening_v2_20261014.patch`：对 `h02_minute_audit.py` 和 `h02_certification.py` 做输入校验强化；新增 `tests/test_h02_hardening.py`；上轮报告本地 20/20 专项通过，**尚未合入远程**。
- `patches/h02_portfolio_price_guard_20261014.patch`：修复 `portfolio.py` 买入、卖出、估值中的非法价格；新增 `tests/test_h02_portfolio_price_validation.py`；上轮报告本地 16/16 专项通过，**尚未合入远程**。
- 旧版 `h02_minute_audit_hardening.patch` 与 v2 内容重叠，**不要叠加**。两个已附补丁没有重叠修改文件，但仍必须各自审查和完整回归。

**补丁是候选修改，不是可信任的最终代码**：先读 diff，核对当前数据接口和 tests，按有意义的单独 commit 推进；如有冲突，手工实现等价行为并添加等价测试，不能为了应用而强行三方覆盖。

## 2. 本轮唯一主任务：P0 结构数据校验修复并推送绿色 CI

### 2.1 P0 背景

当前 `audit_h02_minute_execution()` 对时间戳仅要求整秒，未拒绝非零微秒/纳秒；对 OHLC 仅 `notna()` 与 `>0`，允许正无穷。`inspect_h02_executable_provenance()` 原实现若 `limit_prices.ts_code` 存在，则即使 `up_limit/down_limit` 是 NaN/0/逆序，仍可能计入“有该股票官方价”。这些属于**数据认证漏洞**，不是策略优化。

### 2.2 P0 正确行为

1. 对所审分钟线的全部 `open/high/low/close`：要求可转为数值、`isfinite`、`>0`、`high>=max(open,low,close)` 且 `low<=min(open,high,close)`。
2. 时间必须是正确交易日、交易所本地无歧义时间、严格单调且唯一、合法交易时段的**整数分钟**：秒、微秒和纳秒均为 0；拒绝乱序、重复、越界/错误日期。
3. 09:35 检查点必须存在；至少有一根**严格晚于 09:35** 的分钟记录且存在正成交量；满足上述条件仅输出 `STRUCTURALLY_VALID`，不得输出 `FILLED` 或 `net_equity_validated=true`。
4. 官方逐股价表必须拥有 `ts_code/up_limit/down_limit`，证券码合法且唯一，价格有限正值且 `up_limit>down_limit`；重复代码双方均不能获得通过。缺值/格式异常/源不在白名单必须 `BLOCKED`，保留原因计数。
5. 禁止凭计算 5%/10%/20% 推导价格替代官方逐股行情，并声称已获官方认证。`source=...` 是**来源标签**，不是 PIT 公开时间证明。
6. 对候选集计算 `missing` 与 `invalid` 不能重复错算；一个 symbol-day 只能有一个最终认证状态，必须保留异常追溯。
7. 保持旧版有效数据行为、返回 key 兼容性与封闭状态语义；不降低任何已有断言。

### 2.3 P0 操作（按顺序，不跳步）

**A. 本地现场核验**（Windows PowerShell 中执行；必须在克隆仓库根目录）：

```powershell
$ErrorActionPreference = 'Stop'
git status --short
git remote -v
git fetch origin research/behavioral-edge-20261013 main
git switch research/behavioral-edge-20261013
git pull --ff-only origin research/behavioral-edge-20261013
git rev-parse HEAD
gh pr view 1 --repo RuthlessCreature/Logic-B-Iteration --json number,state,isDraft,headRefName,headRefOid,baseRefName,url
python --version
```

`git status --short` 如果非空，先停并报告；在未确认现场前**不要继续执行 switch/pull**。如果当前分支 HEAD 已改变，先审查是否已有等价修复，不要重复补丁。`git fetch ... main` 只更新远端跟踪引用，不是修改 `main`，但**禁止 checkout/switch 到 main 做提交**。

**B. 建立可复现环境**：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -q
```

如果 `.venv` 已配置可直接沿用。基线 pytest 失败时，记录测试名、日志、当前 HEAD；如属已存在缺陷先定位，不得把它当作本轮补丁引入，也不得直接覆盖。

**C. 对 P0 补丁只读审查**（交接目录已提交到本仓库；以下命令可直接在仓库根目录执行）：

```powershell
$Handoff = Join-Path (Get-Location).Path 'research\handoffs\h02-20261014'
$P0 = Join-Path $Handoff 'patches\h02_hardening_v2_20261014.patch'
git apply --stat $P0
git apply --check $P0
```

如果 `git apply --check` 失败，先确认分支 HEAD、补丁是否已部分应用及是否已有等价代码；禁止 `git apply --3way` 强冲突，禁止修复时抹掉原有逻辑。

**D. 应用并验证**：

```powershell
git apply $P0
python -m pytest -q tests/test_h02_hardening.py tests/test_h02_certification.py
python -m pytest -q
logic-b smoke
logic-b validate-config config/b0.yaml
git diff --check
git diff --stat
git status --short
```

如果某个命令因 CLI 版本差异失败，查 `logic-b --help` 和仓库 workflow，不得假装通过。必须手工读生产代码和新增测试，尤其审查 `nan`、`inf`、时间精度、重复证券、缺列、合法 0 成交分钟 bar、乱序与日内暂停的处理。

**E. 只提交 P0，不混入数据/配置/收益文件**：

```powershell
git add src/logic_b/h02_minute_audit.py src/logic_b/h02_certification.py tests/test_h02_hardening.py
git diff --cached --check
git diff --cached --stat
git commit -m "fix(h02): fail closed on invalid minute bars and price limits"
git push origin research/behavioral-edge-20261013
```

推送前复查 `git diff --cached --name-only`，只允许列出的三个文件。若有未经批准的文件混入，取消暂存对应文件，不能随便提交。若无变更说明远程已有修复，记录证据而非制造空 commit。

**F. 验证对应新 HEAD 的 GitHub Actions**：

```powershell
git rev-parse HEAD
gh run list --repo RuthlessCreature/Logic-B-Iteration --branch research/behavioral-edge-20261013 --limit 10
# 从列表中找到与本次新 HEAD 匹配的 run；确认 headSha 后再 watch
gh run view <RUN_ID> --repo RuthlessCreature/Logic-B-Iteration --json headSha,status,conclusion,url,workflowName
gh run watch <RUN_ID> --repo RuthlessCreature/Logic-B-Iteration --exit-status
# 若失败
gh run view <RUN_ID> --repo RuthlessCreature/Logic-B-Iteration --log-failed
```

如果 workflow 的触发条件未涵盖所改文件，补一份**只针对研究分支且不触及 holdout 的安全 CI** 或明确报告 `CI_NOT_TRIGGERED`；不能引用旧 HEAD 成功记录充数。若 CI 红灯，先定位本轮引入的错误，修复后另提交并确认新 HEAD CI，再完成 P0。

### P0 完成门槛（必须全部满足）

- 本地原有完整 `pytest` 通过；新增校验专项测试通过。
- 旧有正常分钟线、合法涨跌停价仍可通过“结构合法”门；非法输入会明确阻断。
- 无 `config/b0.yaml`、策略信号、holdout、原始行情文件变更；PR #1 仍 Draft。
- GitHub 研究分支 HEAD 产生真实非强推 commit 且相应新 HEAD CI 绿色。
- 输出 commit URL、CI URL、测试数、最终 diff 清单、失败/阻碍与下一步。

**任何一条缺失：P0 只能报 `PARTIAL` / `BLOCKED`，不能报 `DONE`。**

## 3. P1：账户非法价格保护（P0 通过后才做）

目的：拒绝 `NaN`、正负 `Inf`、零、负数的 `buy_all(price)`、`sell_all(price)` 和 `equity(mark_price)`；状态改变前校验，任何异常订单**现金和持仓均保持原状**。保留单票单仓、A 股 T+1（买入日不可卖出）、100 股整手、全部费用模型与正常成交行为。切勿在发现坏价格后“替换为前收/均价”并继续成交。

执行：先 `git apply --check`，再应用 `patches/h02_portfolio_price_guard_20261014.patch`；运行 `python -m pytest -q tests/test_h02_portfolio_price_validation.py`、`python -m pytest -q`、`logic-b smoke`、`logic-b validate-config config/b0.yaml`；确认无回归后另起一个 commit 并推送，观察新 HEAD CI。特别补查 `TradingCosts` 费用计算中非有限成交额、非法费率的处理是否存在同类污染：**若需要扩大修复范围，请单独记录为 P2 候选，不得偷偷扩张 P1。**

当前冻结默认值（代码参数，**不是已核验的真实历史券商费率**）：`commission_rate=0.0003`、`minimum_commission=5.0`、`transfer_fee_rate=0.00001`、`stamp_rate=0.0005`（仅卖出）。另需从实际账户/官方时间表取证；此前不得声称历史手续费已认证。

## 4. P2 及以后：H02 真实可成交回测数据工程路线（未授权在本轮一口气完成）

### P2-A. 数据血缘与覆盖矩阵（先设计再实现，**首选下一次小增量**）

- 不改冻结策略，新增单独 H02 审计输出。例如 `research/experiments/h02-stage0-20261013/` 下的 schema/报告，或项目既有 `runs/` 下可复现的机器可读 JSON+Parquet。
- 以交易日 `D` 的 **`D-1` 收盘涨停候选**为分母（去重后 symbol-day），列出：`calendar`、`candidate D-1`、`independent_daily D`、`reference_ST D`、`reference_halt D`、`official_price_limits D`、`candidate_minute_1m D`、checksum、时区与时间戳、provider、PIT 资格、成交状态；每个字段记录 `present / structurally_valid / provenance_valid / PIT_certified / execution_ready`。
- 2020 年 1 月历史独立日线的 **985/985** 是先前报告的窄范围数值；下载归档后按交易日、证券码重新算期望值与实际值，不得写死 985，也不得把 985 当作 2020–2026 总数。若历史参考为盘后发布，标 `EOD_REFERENCE_ONLY`。
- 每个 `BLOCKED` 都应输出具体日、证券、数据集、原因和供应商；不丢弃稀疏分钟 K，不将无成交条数直接判定停牌。
- 保留跨源冲突样本：2020-01-03 `000716.SZ` 的 XGB 1m 与 BaoStock 日线 `open/low` 各差约 0.02 元，不能通过放宽容差“洗掉”。可对照研究文档。
- 最小验收：一个已知小日期集完全可重放出覆盖矩阵；bad fixture 的记录不被判断为可成交；同一输入重复运行输出一致（固定排序、固定 schema、源哈希）；没有任何 2026 holdout 调用。

### P2-B. 官方逐股上/下限数据与独立 ST/停牌

- 首先本地无泄密检测 `TUSHARE_TOKEN` 是否配置、对应历史权限是否真的可读；复用 `.github/workflows/h02-historical-official-limits-permission-probe.yml` 的指标与逻辑，但不要先公开跑大批量。
- **若 Token 不可用，停止官方限价采集子任务，产出 `BLOCKED_MISSING_TUSHARE_TOKEN`；禁止自动推定 5/10/20% 取代逐股 `up_limit/down_limit`。**
- 优先使用程序已有 `TushareProvider` 的 `stk_limit` / `stock_st` / `suspend_d` 规范化路径；如替换供应商，必须审核许可、历史口径、逐日权威性、API 限流、字段含义、时间戳，独立新增 adapter 与完整来源记录；不得仅为了绕过硬门把任意来源字符串伪装成 `TushareProvider`。
- ST/停牌如果来自 BaoStock `isST`、`tradestatus` 历史 EOD 字段，先只用于跨源一致性审计；除非有独立可信证明当时开盘前/09:35已公示，否则不得参与当日 PIT 信号。
- 必须处理 IPO 无价限窗口、ST、创业板 2020-08-24 前后制度变化、科创板、复权调整、退市与历史证券状态，不得一把统一百分比处理所有股票。历史逐股 `up_limit/down_limit` 合法，不意味着行情数据源有相同价格/时间口径。

### P2-C. 候选股分钟线与 PIT 时间合同

- 每根记录需要 `trade_date`、`ts_code`、原始 bar timestamp、timestamp 语义（开盘标签还是收盘标签）、交易所时区 `Asia/Shanghai`、`open/high/low/close/vol`（含成交量单位）、供应商、数据版本、查询日期、原始哈希。
- 不能将获取时间 `retrieved_at` 冒充 `published_at/available_at`。如果历史供应商无法提供时点可见性证明，则 `PIT_certified=false` 并阻断入信号。
- **09:35 的 K 线标签语义必须实证确认**：若标记 `09:35` 的一分钟柱为 09:35:00~09:35:59 完成，09:35:00 的信号不能使用该柱。冻结策略中“09:35 已完成分钟 K”及最早下一根成交，要在代码中明确观察区间 `[start,end)` 和最早可交易事件 `event_time>decision_available_at`。不能机械使用 `ts<=09:35` 代替公布时间证明。
- `signal_snapshot` 必须持久化可用数据 ID 清单及每条 `available_at`，对每个输入强制 `available_at<=decision_at`；09:35后的高低价、成交量及 D 收盘汇总只能在成交回放端使用，不得回流信号端。
- 分钟回放不等于实盘 tick/盘口：`后续分钟有量` 是必要但非充分条件；一字涨停买不到、跌停锁死卖不掉、滑点、无法判断队列成交时，要保守拒单或标明模型界限；绝对不能声称拥有历史逐笔真实成交证明。

### P2-D. T+1、成本与执行台账

- 逐笔最少：`signal_id`、`order_time`、`earliest_eligible_fill_time`、`symbol`、`side`、`target_lots`、`filled_lots`、`fill_price`、`fee_commission`、`fee_transfer`、`fee_stamp`、`slippage`、`not_fill_reason`、`position_before/after`、`cash_before/after`、`source_hashes`。
- 原始设定：单票满目标仓、100 股整手、买入当日禁止卖、E0 次交易日 09:35 退出尝试。跌停/停牌/无量导致无法卖时继续持仓并保留被动风险；不许通过日终收盘价“强行结算”出场。
- 费用必须逐成交方向正确收取，佣金最低费用生效，卖出印花税单独处理。手续费率及生效日期需独立取证，固定模型默认值只能注明为假设。`gross`、`after-fee`、`net` 全部可对账；坏 price 不得污染现金。
- 异常测试：一字板、无分钟、零成交量、分时断点、停牌复牌、延迟卖出、持仓跨多日、IPO 无涨跌限制、T+1 当日卖、账户余额边界、税费最低佣金、重复委托与错误时间戳。

### P2-E. 研究升级硬门与退出条件

- Stage 0：独立数据来源、覆盖、PIT、成交约束和账本全部可审计前只允许发布 coverage/blocked 报告。
- Stage 1：H02-R（获利强化）、H02-C（拥挤）、H02-X（衰竭）三条假设**分别**与冻结基线做时间序列验证；不能将市场总成交量冒称 Level-2 OFI；不能把模拟策略账户利润说成真实投资者心理。
- Stage 2：只有 Stage 1 达到预注册标准，才允许跑费用后可成交策略对照；用户尚未批准新调参，也不能借此改冻结 B0。
- 任何核心来源无法满足 PIT 真实性、不能复现交易、无正确退出状态机、出现缺失却被回填成功 → `BLOCKED/STOP`。不可拿某个漂亮收益补偿数据门槛失败。

## 5. CI 与回归测试的严格验收矩阵

| 场景 | 最低正确结果 |
|---|---|
| 正常 `09:35` 检查点 + 之后合法成交量 | `STRUCTURALLY_VALID`；`fill_certified=false` |
| `open/high/low/close=NaN/Inf/-Inf/0/负数` | `BLOCKED`、非异常崩溃 |
| 09:35 后 bar 缺失/无正成交量 | `BLOCKED`，原因可机器读取 |
| 秒、微秒、纳秒非零 | `BLOCKED` |
| 同一 symbol-day 重复/乱序/非当日时间 | `BLOCKED` |
| 官方逐股上/下限字段缺失、非有限、逆序、重复代码 | `BLOCKED` |
| 来源 manifest/hash 不一致 | `BLOCKED` |
| 仅有 BaoStock 历史 EOD `isST/tradestatus` | 只能 `REFERENCE_ONLY`，非 PIT 已证实 |
| 当日信号尝试读 09:36/当日收盘 | 防泄漏断言失败，不得静默通过 |
| 买入日卖出 | T+1 拒绝，原持仓不变 |
| 非法卖出价格 | 拒绝，现金/持仓无副作用 |
| 卖不出跌停/停牌 | 保留仓位，记录 nonfill |
| 旧版完整单测、smoke、配置检查 | 全通过（否则红灯） |
| GitHub 最新 HEAD CI | 有对应链接、非旧 CI、绿色才可 `DONE` |
| 保护留出集 | 未访问，默认阻断保持生效 |

## 6. 给本地 Codex 的报告格式（强制在每轮结束时填写）

```text
H02 LOCAL CODEX REPORT
时间/时区：
分支：research/behavioral-edge-20261013
开始 SHA：
结束 SHA：
工作目标：P0 / P1 / P2-...（必须只填本轮真正做过的）
变更文件：
本地测试：命令 + 通过/失败数量 + 首个失败信息
GitHub 提交：commit SHA + URL（没有就填 NONE）
CI：对应 HEAD + run URL + conclusion（没有就填 NOT_RUN）
数据证据：样本日期、候选 symbol-days、覆盖数、来源、manifest 校验、PIT 资格
禁止项复核：main 未改；holdout 未读；未改策略参数；未用未来信息
失败及阻碍：精确命令/错误/缺凭证，不得空泛
当前 Gate：DONE / PARTIAL / BLOCKED
下一个最高杠杆动作：仅一项
```

如未成功 push，立刻报告 `PARTIAL` 并给出本地 commit、差异文件及阻碍。不得谎称 GitHub 已更新；不允许把未合入补丁的本地专项通过说成远程CI通过。

## 7. 实施顺序与停工条件

```text
核实 HEAD / 检查本地未提交工作
    ↓ 只读核查
基线 pytest / smoke
    ↓ 旧代码先确定现状
P0 读补丁 → 校验 → 应用 → 专项与全量测试
    ↓ 通过才 commit
Push 研究分支 → 绑定新 HEAD 的 CI → 红灯则修复
    ↓ P0 DONE
P1 账户价格保护 → 测试 → 独立 commit → 绑定 CI
    ↓ P1 DONE
下一轮只选 P2-A：覆盖矩阵最小样本（不碰保护留出集）
    ↓
有真实来源证据才逐项处理官方限价 / ST停牌 / 分钟 PIT / 账本
    ↓
Stage-0 Gate 成立前永久禁止正式 H02 净值报告
```

### 立即停工并报告的条件

- 当前工作目录有未知未提交更改。
- 研究分支 HEAD 不同于交接快照且未完成重新审查。
- 权限/认证/网络阻止推送或运行 CI。
- 完整测试不能恢复绿色。
- 任何工作需要访问冻结留出集、解锁参数、覆盖现有原始数据。
- 缺少官方逐股价格/来源时效性而任务要求输出“真实成交收益”。

---

## 8. 参考入口（全部是当前仓库链接）

- [PR #1 — Draft](https://github.com/RuthlessCreature/Logic-B-Iteration/pull/1)
- [当前 HEAD 对应已成功 CI](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38420733550)
- [H02 Stage-0 可行性与阻碍](https://github.com/RuthlessCreature/Logic-B-Iteration/blob/research/behavioral-edge-20261013/research/experiments/h02-stage0-20261013/FEASIBILITY_AND_DATA_GATES.md)
- [独立 ST/停牌数据采集说明](https://github.com/RuthlessCreature/Logic-B-Iteration/blob/research/behavioral-edge-20261013/research/experiments/h02-stage0-20261013/INDEPENDENT_STATUS_BATCH.md)
- [H02 预注册研究协议](https://github.com/RuthlessCreature/Logic-B-Iteration/blob/research/behavioral-edge-20261013/docs/12_H02_EXECUTABLE_REINFORCEMENT_PREREGISTRATION.md)
- [2020 年 1 月独立日线回填工作流](https://github.com/RuthlessCreature/Logic-B-Iteration/blob/research/behavioral-edge-20261013/.github/workflows/h02-2020-january-reference-backfill.yml)
- [官方历史逐股价格权限探针](https://github.com/RuthlessCreature/Logic-B-Iteration/blob/research/behavioral-edge-20261013/.github/workflows/h02-historical-official-limits-permission-probe.yml)
- [分钟单日审计工作流](https://github.com/RuthlessCreature/Logic-B-Iteration/blob/research/behavioral-edge-20261013/.github/workflows/h02-2020-full-day-minute-audit.yml)
- [冻结配置](https://github.com/RuthlessCreature/Logic-B-Iteration/blob/research/behavioral-edge-20261013/config/b0.yaml)

**总结：本次交接的成功标准不是“做完 H02”，而是把 P0 修复以可审计的单独 commit 合入研究分支，拿到对应新 HEAD 的绿色 CI，保留所有 H02 数据缺口与拒绝条件。**
