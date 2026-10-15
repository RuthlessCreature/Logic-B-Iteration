# 新 Logic-B · 实际运行指南

## 1. 安装
```bash
python -m pip install -e ".[dev,data]"
python -m pytest -q
python -m logic_b --dataset examples/toy_history.json --out runs/toy
```
`examples/toy_history.json` 只用于合成撮合测试，收益数字没有市场意义。

## 2. 免费历史数据：从2020年1月开始的小样本

```bash
python -m logic_b.collect calendar --start 2020-01-01 --end 2020-01-31
python -m logic_b.collect events --start 2020-01-01 --end 2020-01-31 --max-days 16
python -m logic_b.collect daily --start 2020-01-01 --end 2020-01-31 --max-days 16
python -m logic_b.collect minute --start 2020-01-01 --end 2020-01-31 --max-days 16 --exit-lookahead-sessions 16
python -m logic_b.collect dataset --start 2020-01-01 --end 2020-01-31 --max-days 16
python -m logic_b --dataset data/replay_dataset.json --out runs/jan2020
```

缓存位于 `data/raw`，不会提交 Git；断点续采默认读取缓存。这是**明确限量的历史K线模拟**，不是实盘成交。扩大期间先确认数据缺口、API响应、分钟历史是否可取得、公司行动处理；上文 `--max-days` 限制采集规模，不是全期回测开关。2019年以前数据或2026年7月以后的市场数据不在新研究范围。

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
