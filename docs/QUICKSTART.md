# 新 Logic-B · 实际运行指南

## 1. 安装
```bash
python -m pip install -e ".[dev,data]"
python -m pytest -q
python -m logic_b --dataset examples/toy_history.json --out runs/toy
```
`examples/toy_history.json` 只用于合成撮合测试，收益数字没有市场意义。

## 2. 免费历史数据：现在只需要一条命令

```bash
# 2020年初历史行情，最多50个交易日
python -m logic_b.pipeline --start 2020-01-01 --end 2020-03-31 \
  --max-sessions 50 --out runs/2020q1
```

这一入口自动依次读取/缓存选股宝历史事件和BaoStock不复权日K，并且**只下载当天真正需要买入的核心票或需要退出的持仓的5分钟K**，不会针对每只曾入选股票批量下载所有未来K线。

- 本地缓存：`data/raw/`。真实原始市场行不得提交GitHub。
- 详细可复核账本：`runs/2020q1/private_trade_ledger.json`（仅本地，自动被Git忽略）。
- 公开的非原始统计：`runs/2020q1/aggregate.json`。
- 标记`PARTIAL`代表尚未覆盖2020—2026全部交易日；不能拿这段试跑算长期收益。
- 除权/送股及行情过期导致账户值无法准确计算时，`return_pct=null`，不得强行使用未调整账面值宣传收益。
- 缺少真实源字段时清楚记录缺失，不用想象价格补齐历史。
- 想扩大到全2020年，可改 `--end 2020-12-31 --max-sessions 250`，再按年份滚动到2026-06-30；长数据窗口请利用本地缓存和接口限速，不能将每年分别从1万元重新初始化的结果直接拼成跨年复利曲线。跨年度必须连续账户状态运行。

如果需要低级调试或单独采集原始池、分钟K，依然可使用 `python -m logic_b.collect`；这不再是日常主要执行入口。

## 3. 大模型辅助可证伪实验

```bash
python -m logic_b.research_cli --dataset data/replay_dataset.json --out runs/research --proposal examples/proposal_example.json
```

上面不消耗任何LLM额度；冻结一份JSON提案再运行比较。若需要让大模型提出新假设，把 `OPENAI_API_KEY` 只保存在用户本地环境，并运行：

```bash
python -m logic_b.research_cli --dataset data/replay_dataset.json --out runs/research --llm-model <你账户可用的模型ID>
```

模型**只能收到2020—2024训练段聚合账户信息**，结构化返回三个策略参数和解释。脚本不会给模型提供验证区间未来行情或执行交易权限。

`runs/research/evaluation-*.json` 是分段净值/成本比较；不满足最低样本、资金回报、最大回撤及来源覆盖时直接输出 `NO_FOLLOW`。

## 4. 本人的Follow审阅清单

```bash
python -m logic_b.follow --dataset data/replay_dataset.json --out runs/follow.json
```

未有合格策略评估时输出 `NO_FOLLOW`。有经过规则审核的版本时，用
`--research-report runs/research/evaluation-<digest>.json` 得到
`MANUAL_REVIEW_ONLY`。这不是券商委托，不会触发买卖。

## 5. 研究质量限制

1. 选股宝事件池用于昨日候选、市场环境，BaoStock不复权日K和5分钟完成bar用于价格假设。ST更名不得使同一代码拆成两只股票。
2. 佣金买卖双边万2.5且最低各5元，印花税与过户费按日期分别算；1万元单票满仓、100股一手。
3. 涨停价默认不成交买单、跌停价默认不成交卖单；无法卖出需要隔日重试，保持原仓。
4. 无事件源/分钟K/公司行动的日期必须透明标记，不能用现金净值假装代表整个2020—2026真实收益。
5. 目前仅2020年初小样本通过远端真实价格试跑；全期尚未完成，严禁把试跑结果年化或当成稳健策略。
6. 旧完整项目在 `legacy/2026-10-15-pre-reset/`，原文件与 Git SHA 可复查。
