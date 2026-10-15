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
## 真实数据和AI研究的入口

```bash
# 2020年1月16个交易日的免费源试跑（缓存到data/，不会公开提交原始数据）
python -m logic_b.collect calendar --start 2020-01-01 --end 2020-01-31
python -m logic_b.collect events --start 2020-01-01 --end 2020-01-31 --max-days 16
python -m logic_b.collect daily --start 2020-01-01 --end 2020-01-31 --max-days 16
python -m logic_b.collect minute --start 2020-01-01 --end 2020-01-31 --max-days 16
python -m logic_b.collect dataset --start 2020-01-01 --end 2020-01-31 --max-days 16
python -m logic_b --dataset data/replay_dataset.json --out runs/jan2020

# 用冻结的离线提案复核策略；也可提供 --llm-model 连接自己已授权的大模型
python -m logic_b.research_cli --dataset data/replay_dataset.json --proposal examples/proposal_example.json
# 仅人工审阅的Follow清单，未验证策略默认NO_FOLLOW
python -m logic_b.follow --dataset data/replay_dataset.json
```

以上命令在本地有网络且免费接口仍可用时运行。分钟K报价来自**已结束的09:45五分钟Bar**，是保守模拟而不是实盘真实成交。**目前`strategy.select_core`只是可审计的昨日涨停事件排序v0，不代表已经忠实复原完整逻辑A。** 对真实市场未完成日期、公司行动和源缺失，不得给出完整历史回报结论。

查看 [完整中文操作指南](docs/QUICKSTART.md) 及 [Goal执行约定](AGENTS.md)。
