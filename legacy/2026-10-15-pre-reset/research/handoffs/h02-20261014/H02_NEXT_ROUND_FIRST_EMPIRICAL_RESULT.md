# H02 NEXT ROUND — 必须交付第一份真实历史数值结果（2026-10-14）

**优先级：P0 / 最高。** 本任务优先于旧版 H02-LT 的大框架建设，承接 FAST-TRACK，禁止重复已完成的 P0/P1/P2-A。  
**用户明确要求：下一轮必须看到初步结果。** 不是更多概念、只有测试数量、只写后续计划。  
**写入范围：** 仅 research/behavioral-edge-20261013，PR #1 保持 Draft、base=main，不修改 main、config/b0.yaml 或冻结交易/研究参数。  
**起始提交（执行时须再次核对）：** 22d2b440103e47020c332836610380013d31e76b。  
**允许数据：** 2026-06-30及以前；完全禁止读取/下载 2026-07-01..2026-09-28 真实保护留出数据（包括 2026observed artifact）；合成日期拒绝测试除外。  
**净值限制：** 当前 Tier E仍 BLOCKED，无官方逐股限价、PIT状态、09:35完成语义和模拟成交资格时不得生成“可成交/手续费后策略收益”“胜率”“年度回报”。事件级观测值必须明确标为 TIER D、不得偷换为交易结论。

## 验收定义：本轮少一个都不算完整DONE

- **R0 安全预检修复**：审阅 scripts/h02_audit_dev_artifact_coverage.py。当前逻辑仅预检以 YYYYMMDD 命名的 raw 分区，然后读取 calendar Parquet，才核验 calendar 内容日期是否超出 20260630。若预检不足以阻止读取恶意/错误命名的保护期内容，应添加可信ZIP allowlist（明确已确认的五个artifact名称、source run ID、完整ZIP SHA256），先在字节层比对整ZIP哈希，然后才允许解压/读取任何 Parquet。Archive SHA改变立即拒绝；拒绝 2026observed 与未许可的额外分区及伪造后缀。保持合成fixture测试可复现，安全条件与测试覆盖必须清晰（可信签名/静态SHA优先）。**绝不借口检查而读保护期数据。**
- **R1 真正数值结果**：从已经留存的五个H01开发期档案（见附录SHA），仅使用其 calendar、limit_up、limit_down，产出首份实际数字：D-1出现在供应商涨停事件池的股票在D继续出现于供应商涨停事件池的比例（事件延续率）；D出现供应商跌停事件的比例（极端负向事件代理）。至少涵盖冻结开发区间 **2024-09-30..2026-06-30**。逐年/半年度与总体提供事件分子、分母和百分比（全样本候选计数是多个symbol-day观察，不是互不相关样本），另列每日比率均值/中位数供透明对比。时间配对依据已验证的实际交易日日历，不能用自然日跳过节假日。只有完整D-1分区和D两个观测日才入样；最后一天没有D+1时严禁伪造后续样本；禁止在2026-06-30之后寻找任何后续结果。
- **R2 风险观察**：同一D-1涨停集合在接下来最多三**个交易日**（D、D+1、D+2）的供应商跌停事件触及率；只纳入后续三个交易日均在准许开发范围且对应limit_down分区hash完整的观测点。不得因停牌/不存在而计为涨停或跌停；无事件表示“未见供应商对应事件”，不等于可成交、平仓或没有下跌。
- **R3 明确识别数据语义和已有H01重复**：先查清vendor的 limit_up/limit_down 行到底是收盘涨停/跌停，还是盘中触及/事件。若档案和provider文档无法确认，报“同源限价事件池转移率”，**不能写为严格的封板率/跌停收盘率**。H01已开展过市场延续性proxy研究，必须对照既有H01报告和定义，写出本次与旧结果的真正新增部分（开发集正确切片、跌停风险、三日极端风险、字节可复现）。不制造H02心理强化显著性结论，不以“回看分组找到好结果”调参。
- **R4 可重放性**：代码置于 scripts/ 或 src/logic_b/，固定命令从五个**同SHA原始archive**重放，输出同一JSON/Markdown以及数据hash；报告含每个观察日期/分区的来源与hash，摘要可以不给原始证券明细，禁止上传受限raw数据或secrets。必须提供完整的测试，包括三个合成交易日边界、跨假日、分段拼接边界、最后可用日无future、缺盘日fail-closed、伪造hash、数据不可用、候选/跌停重复symbol-day、保护日期一票否决、数值计算举例、年份切片。合成fixture不需要真实授权。
- **R5 数值展板和阻断声明**：输出 research/experiments/h02-stage0-20261013/H02_FIRST_EMPIRICAL_RESULT_20261014.md 和 .json。必须有真实计算数字，不得仅输出“会计算”的计划。标题注明 TIER D / 不是交易绩效；提供误差、覆盖分子/分母、原始ZIP SHA、重要不确定性以及TIER E当前依旧BLOCKED；要一眼看懂“市场涨停隔日延续”和“下一日/三日跌停风险”。
- **R6 Git与CI**：任务可分2至3个原子提交，push并核对各新HEAD Actions；全量pytest、smoke、config校验。请勿因缺官方Tushare Token阻塞本任务，它只做已存在真实事件池的观察性统计。不得伪造本地数据算作历史观测。若五个授权范围内的旧artifacts不能安全取得，写出准确GitHub错误和所需许可条件，给出从已校验manifest摘要能算出的其他有限真实观察值，但**不能编造R1/R2分子**；如实标 PARTIAL 并继续可离线工程。

## 计算定义，禁止歧义

令 U_t 为provider在交易日 t 的去重 limit_up symbols集合，L_t 为provider当日去重 limit_down symbols集合；确认每个artifact的时间范围、含义、hash和唯一性。

对于每一个 outcome day t 属于 2024-09-30..2026-06-30，prev(t) 为**实际前一个**交易日：
- n_t = |U_prev(t)|。n_t=0则此日无个股分母，不得参与候选加权比率。
- c_t = |U_prev(t) ∩ U_t|（次日依旧进入同供应商涨停事件池）。
- l_t = |U_prev(t) ∩ L_t|（次日进入供应商跌停事件池）。
- pooled continuation = Σc_t / Σn_t；pooled down-event = Σl_t / Σn_t。每日比率 mean/median 单独展示，不准把mean比率当pooled。
- three-day down-event proxy = 对每一个 U_prev(t) 的code，若出现在 L_t ∪ L_next(t) ∪ L_next2(t)，记1；仅纳入三天均完整且 <=2026-06-30 的 t；分母是这些 day t 的候选symbol-days，和单日分母不同。
- 异常情况（候选=0、重名、无法跨period取prev、交易日日历缺口、manifest SHA错误、同日涨停和跌停事件并存）必须保留reason/counter。对同日出现在U和L的股票，报告源冲突数量且风险计数可继续标为“事件观察”，但不能认定价格可成交。
- 如果需要按自然年分组，以 outcome day t 对应年归组，不得将dev之外日期计算进总体；如分母样本重叠，必须声明这些symbol-day不是独立样本。
- 所有使用 day t 或之后的结果都是**事后标签/目标变量**，而不是 t 09:35决策时可用输入。不得据此做B0买点或绩效。

## 立即执行步骤（低推理能力Codex执行顺序）

1. git status、fetch、核对 PR #1、审查起始HEAD和目录、读旧H02 FAST-TRACK规格；确认五个artifact的完整SHA，**不要下载2026observed**。
2. 修R0安全preflight并添加合成反例测试（**必须在处理真实档案前通过**）。
3. 从现有H01 run 38358815302 仅取得五个已被校验且允许读取的archive：2024h1、2024h2、2025h1、2025h2、2026dev。验证整个archive SHA、ZIP内部manifest SHA、日历和分区双边一致性。
4. 复用现有h01_activity/limitup_continuation代码和脚本设计，不重复发明策略；**增加跌停风险与年度分母，以及脚本/JSON/Markdown**。
5. 输出R1/R2真实具体数值，检查2024-09-30前的上下文只作D-1历史context，2026-06-30以后从不触碰。比较旧H01诊断有无重复、补充三日风险结果。
6. 逐步提交到研究分支、CI绿灯、更新 FAST_TRACK_PROGRESS.md。完成后输出机器可验收报告，附HEAD、tests数、Actions、JSON文件链接及三项最重要的历史数值。
7. 若还有资源，独立继续三股分钟时间语义和合成订单账本，但不允许让它拖延R1/R2的真实统计报告。

## 两个仍然重要的危险点

- 原有h02_audit_dev_artifact_coverage.py 可能在“检查完命名分区日期”后才读含保护日期的calendar内部记录；应改为哈希 allowlist优先，并在真正解析Parquet前形成文档化的边界保证。
- 五个档案从2024-01-02开始，601个交易日包含正式开发期之前的数据；**初步市场统计必须只以 2024-09-30..2026-06-30 为研究区间**。不可把601天或48641事件当成冻结B0开发集的分母或信号。

## 初始档案白名单 / 明确不可包含的部分

source run: https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38358815302

- h01-raw-2024h1.zip = 1abfc7022075958537e635b107c0919a68122dc0ff6b7a97cec6132f9ab6fec8
- h01-raw-2024h2.zip = ddd770f7f0dc1322c2d782ae1925d43df302570277c0b53af0bde8bef674c1ad
- h01-raw-2025h1.zip = cb9bca81e71fa42ed85659564e5a6a7f446f25cbfc1bc7005d734529dbdc0c67
- h01-raw-2025h2.zip = 8c4a9c90acfc9b7e841a453b127b2dcfb6dcc68e43566ca9f5838d1dcbcb0144
- h01-raw-2026dev.zip = 7da9da754fb7d976b03a371666fd9d27fec0fcaf4f4f784dbecae01e978e857c

**绝对禁止 h01-raw-2026observed.zip、任何2026-07-01..09-28实际数据、未经用户授权的收费数据。**

## 下一轮验收结论的预期格式（Codex必须填真实数字）

~~~text
H02 FIRST EMPIRICAL RESULT (TIER D, NOT EXECUTABLE RETURNS)
dev区间: 2024-09-30 .. 2026-06-30
样本outcome交易日: __，唯一D-1候选symbol-days: __
D-1事件->D涨停事件: __ / __ = __%
D-1事件->D跌停事件: __ / __ = __%
D-1事件->D..D+2三交易日任一跌停事件: __ / __ = __%
分年: 2024/2025/2026，各自分子/分母/数据范围
数据质量: manifest验证 __/__ ; 五个ZIP SHA 5/5; 语义 UNKNOWN 或已核实
正式策略买入信号/盈利和T+1可执行性: NOT EVALUATED / BLOCKED
提交SHA/CI/报告JSON地址: ...
~~~

用户要求结果，因此不能只给“将来数据具备时才做”的空报告。哪怕最终Tier E仍BLOCKED，也要在不越过保护边界时，尽最大可能完成本页可观测事件指标。
