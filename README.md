# Luna 新研究交接：心理驱动的市场状态识别 + 个人交易系统

**明确分层（用户最新定义）**：[Codex离线研发 vs DeepSeek/Jev未来线上Runtime架构](docs/RESEARCH_VS_RUNTIME_ARCHITECTURE.md)。Codex负责策略假设、2020—2026历史回测与反复优化；策略成熟后，日常09:35工程运行由**确定性风控 + DeepSeek上下文推理 + Jev类型化状态/评分**完成，Codex并非线上同步依赖。DeepSeek/Jev目前仍默认关闭，需获得授权、Shadow验证后才能正式调用。已提交[不联网Runtime骨架](src/logic_b/runtime.py)与[配置](config/runtime.json)。

**TypeSafe AI Jev 接口也已预留：** [独立 DecisionProvider API 说明](docs/JEV_TYPESAFE_RESERVED_API.md)，配置 `config/decision_providers.json`，实现 `src/logic_b/decision_providers.py`，默认关闭、未联网、未计费。它可在未来做类型约束的市场状态/风险评估，不与DeepSeek文本研究接口混用，不直接下单或覆盖风险硬否决。


**当前权威执行文档：** [Logic-B / Luna 完整 Handoff](docs/HANDOFF_LUNA_BEHAVIORAL_MARKET_SYSTEM.md)；[长期执行检查点](research/GOAL_CHECKPOINT.md)。Luna 必须先阅读它们再动工。研究应理解参与者心理与赚钱/亏钱反馈，以可观测的 MarketState/SectorState/CoreState 构建 MarketGate 和核心筛选，然后用真实价格、单票1万元、T+1、全部税费进行版本化资金回测，最终输出人类可审阅的 Follow 或 NO_FOLLOW。

**大模型架构：** 当前用OpenAI/Codex进行离线研究；未来DeepSeek承担生产Runtime上下文推理而不是研究替补。已预留DeepSeek的 `config/llm_providers.json` + `src/logic_b/llm_providers.py`，**默认禁用、尚未联网、不产生收费**。不得暗中切换模型或把心理理论说成已经识别真实交易者心理。

---

# Logic-B · 自主量化研究与回测

**新项目从这里开始。** 用选股宝的每日涨停/跌停/炸板和市场情绪、BaoStock的历史K线，在2020-01-01—2026-06-30进行可复现交易回测；用大模型提出可被证伪的改进建议；最终生成供本人自主判断的跟随清单。**不自动下单，不保证盈利。**

- 本金：人民币 **10,000**；买卖佣金各 **万2.5，最低每笔5元**；印花税及过户费按历史日期单列。
- A股T+1、100股买入整数手、最多一只持仓；涨停价默认买不到、跌停价默认卖不出。
- 历史证券身份以交易所+六位代码确定；ST、*ST和更名仅是逐日属性。
- 策略和结果必须版本化，训练/验证按时间隔离，逐笔账本比漂亮的模型分数更重要。
- 默认不读取2026-07-01—2026-09-28的旧受保护数据。**新回测仅到2026-06-30。**

## 仓库结构

- `src/logic_b/`：全新、轻量的交易账本、策略、费用、数据适配。
- `config/research.json`：唯一当前研究配置。
- `tests/`：新引擎回归测试。
- `legacy/2026-10-15-pre-reset/`：完整原项目快照，包含原源码、历史H01/H02、报告、工作流和配置。仅供查阅，不参与当前构建或默认测试。
- `docs/RESEARCH_LOOP.md`：LLM提出假设 → 固定实验 → 回测 → 记录决策 → 下一轮。

## 现在可运行

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m logic_b --dataset examples/toy_history.json --out runs/smoke
```

上述是**合成回归样本**，不是2020—2026真实市场收益。使用真实数据须构建同格式的历史日线/5分钟K线数据集；不能把事件池的延续概率当作收益。

详情见 [研究合同](docs/RESEARCH_LOOP.md)。
## 真实数据与AI研究入口

```bash
# 推荐：按需增量采集的第一季度真实价格试跑
python -m logic_b.pipeline --start 2020-01-01 --end 2020-03-31 --max-sessions 50

# 将真实行情样本转换为固定策略比较（目前只是探索性）
python -m logic_b.research_cli --dataset runs/smart-pilot/private_replay_input.json \
  --proposal examples/proposal_example.json

# 只生成供本人审阅的Follow清单
python -m logic_b.follow --dataset runs/smart-pilot/private_replay_input.json
```

以上命令在本地有网络且免费接口仍可用时运行。分钟K报价来自**已结束的09:45五分钟Bar**，是保守模拟而不是实盘真实成交。**目前`strategy.select_core`只是可审计的昨日涨停事件排序v0，不代表已经忠实复原完整逻辑A。** 对真实市场未完成日期、公司行动和源缺失，不得给出完整历史回报结论。

查看 [完整中文操作指南](docs/QUICKSTART.md) 及 [Goal执行约定](AGENTS.md)。
