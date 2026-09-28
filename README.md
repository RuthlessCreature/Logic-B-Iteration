# Logic-B-Iteration

将“逻辑A”冻结为 **Logic B0**，并以 point-in-time 数据、真实成交约束、T+1 状态机和盲测协议进行可复现的 A 股超短交易研究。

项目目标不是寻找历史曲线最漂亮的参数，而是逐步得到一套：

- 可解释；
- 可执行；
- 可复现；
- 可审计；
- 对不同市场阶段具备稳定性的交易逻辑。

## 当前状态

当前策略规格：**B0.0.2 / B0-P.1**

已实现：

- B0-H 人工参考协议；
- B0-P 可程序化代理；
- 前一交易日涨停候选池；
- KPL 历史题材证据；
- 市场状态 ATTACK / TRIAL / NEUTRAL / RETREAT / ICE；
- 09:25 / 09:35 checkpoint 特征构建；
- 官方涨跌停价格 `stk_limit`；
- 三档成交模型；
- T+1；
- 涨停不可买 / 跌停不可卖；
- 禁止信号与成交使用同一根完成分钟 K；
- E0 次日 09:35 基线退出；
- 本地 Parquet 数据湖和 SHA256 manifest；
- 数据质量审计；
- B0-H / B0-P 一致性审计；
- blind holdout 默认锁定；
- GitHub Actions 自动测试。

**尚未发布任何两年收益率。**

在真实数据下载、数据审计、B0-H 对齐和完整开发集回放完成之前，任何收益数字均不作为有效研究结论。

## 1. B0 的双层定义

### B0-H — Human Reference

保留 Logic A 的人工语义：

1. 总龙头；
2. 板块核心容量；
3. 最强换手前排；
4. 明确补涨核心；
5. 冰点 / 退潮不开新仓；
6. 核心不可买或确认失败时空仓；
7. 不使用后排作为核心的替代交易。

B0-H 用于判断“机器是否真的在表达 Logic A”。

### B0-P — Programmatic Proxy

将 B0-H 映射为程序可重放特征。

B0-P.1 强制执行核心层级：

```text
TOTAL_MARKET_LEADER
    >
SECTOR_CAPACITY_CORE
    >
TURNOVER_FRONT
    >
CATCHUP_CORE
```

先选最高层级核心，再检查确认度和可成交性。

最高层级核心未通过闸门时：

```text
CASH
```

而不是向下选择次优候选。

## 2. Point-in-time 原则

任何信号只能使用决策时点已经可观察的信息。

例如 09:35 信号：

- 可以使用 D-1 完成后的涨停体系和题材结构；
- 可以使用开盘集合竞价结果；
- 可以使用截至 09:35 已完成的分钟行情；
- 不可以使用 10:00、14:30 或收盘后的结果；
- 不可以使用下一交易日溢价；
- 不可以用事后确认的“大龙头”身份反推早期买点。

另外：

> 若 09:35 完成的分钟 K 被用于产生信号，最早成交只能从下一根分钟 K 开始。

## 3. 历史题材数据

B0-P 不使用 THS “最新概念成分”回填历史，因为最新成分会污染过去时点。

当前采用：

- D-1 KPL 涨停榜 `kpl_list` 的历史 `theme` 字段；
- 后续可用 `kpl_concept_cons(trade_date=...)` 扩展历史题材成分。

没有历史题材证据时：

- 不允许标记为 `SECTOR_CAPACITY_CORE`；
- 不允许标记为 `CATCHUP_CORE`。

## 4. 研究窗口

总研究区间：

```text
2024-09-30 ~ 2026-09-28
```

当前冻结为：

```text
Development:
2024-09-30 ~ 2026-06-30

Blind Holdout:
2026-07-01 ~ 2026-09-28
```

开发阶段默认禁止运行 blind holdout。

## 5. 安装

Python 3.11+。

```bash
git clone https://github.com/RuthlessCreature/Logic-B-Iteration.git
cd Logic-B-Iteration

python -m venv .venv
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

pip install -e ".[dev]"
pytest
```

## 6. Tushare 凭证

不要把 token 写入代码、配置文件或 Git 提交。

Linux / macOS:

```bash
export TUSHARE_TOKEN="..."
```

PowerShell:

```powershell
$env:TUSHARE_TOKEN="..."
```

当前数据层依赖的 Tushare 权限包括：

- THS 涨跌停榜；
- KPL 涨停榜；
- 官方每日涨跌停价格；
- 历史开盘集合竞价；
- 股票历史分钟数据。

历史分钟数据需要单独权限。

## 7. 下载日级数据

```bash
logic-b fetch-daily \
  --start 2024-09-30 \
  --end 2026-09-28
```

下载支持断点续跑：已经存在的分区默认跳过。

日级 bundle 当前包括：

```text
limit_up
limit_down
limit_break
kpl_limit_up
daily
limit_prices
auction
```

## 8. 数据审计

```bash
logic-b audit-data \
  --start 2024-09-30 \
  --end 2026-09-28
```

审计内容包括：

- OHLC 合法性；
- 重复股票；
- 官方涨跌停价格覆盖；
- 收盘价格是否超出官方限制；
- 涨停池与实际收盘涨停是否一致；
- 跌停池与实际收盘跌停是否一致；
- 涨停池 / 跌停池异常交集；
- 炸板池异常交集。

存在 ERROR 时，正式回测不应继续。

## 9. 下载分钟数据

```bash
logic-b fetch-minutes \
  --start 2024-09-30 \
  --end 2026-06-30
```

分钟数据只针对 D-1 涨停候选下载，不下载全市场两年分钟数据。

完整研究仍需考虑持仓跨日锁死后的补充分钟数据；后续将增加按需补全机制。

## 10. 运行 B0 开发集

```bash
logic-b run-b0 \
  --start 2024-09-30 \
  --end 2026-06-30 \
  --fill all
```

输出：

```text
runs/<run_id>/
  signals.parquet
  fills.parquet
  trades.parquet
  daily_equity.parquet
  metrics.json
  config.json
  run_manifest.json
```

三档成交口径：

- `optimistic`：收益上界；
- `realistic`：主要研究口径；
- `conservative`：保守下界。

## 11. Blind Holdout

以下命令默认拒绝执行：

```bash
logic-b run-b0 \
  --start 2026-07-01 \
  --end 2026-09-28
```

只有冻结候选版本、停止修改规则后，才允许显式解锁：

```bash
logic-b run-b0 \
  --start 2026-07-01 \
  --end 2026-09-28 \
  --fill all \
  --unlock-holdout
```

holdout 结果不得反复用于调参。

## 12. B0-H 对齐

人工标签格式：

```text
schemas/human_reference.schema.yaml
```

对齐命令：

```bash
logic-b align-b0 \
  --human research/human_labels.csv \
  --proxy runs/<run_id>/signals.parquet \
  --out runs/<run_id>/human_alignment.csv
```

报告：

- action agreement；
- selected-code agreement；
- core-type agreement；
- label coverage。

B0-P 如果收益更高但 B0-H 对齐更差，不能自动视为 B0 改进；它应被视为一个新的 B1+ 策略假设。

## 13. 迭代方法

```text
B0
↓
真实开发集重放
↓
失败案例聚类
↓
提出一个可解释假设
↓
只修改一个主要机制
↓
walk-forward
↓
成交压力测试
↓
B0-H 语义审计
↓
Promotion Gate
↓
B1 / Rejected Experiment
```

优先实验：

1. 中位股是否存在条件性负期望；
2. 最高板断板后的空间压缩；
3. 死尸池负反馈对高位接力的影响；
4. 次日确认特征；
5. 核心不可成交时，空仓相对后排替代的机会成本；
6. 板块宽度与龙头高度的交互；
7. 退出规则 E0 / E1 / E2 的贡献拆分。

## 14. 数据许可与仓库边界

完整历史原始数据默认不提交 GitHub。

`.gitignore` 已排除：

```text
data/raw/
data/processed/
cache/
runs/
```

Tushare 的部分 THS / KPL 数据来自第三方数据授权。使用者应遵守对应数据源和 Tushare 的授权条款；公开仓库仅保留：

- 代码；
- schema；
- manifest；
- 小型合成测试 fixture；
- 研究协议。

不发布完整第三方历史数据集。

## 15. 研究纪律

禁止：

- 随机 shuffle 时间序列；
- 用收盘信息决定上午交易；
- 用下一日收益定义当天核心；
- 默认一字涨停可以买入；
- 默认一字跌停可以卖出；
- 用少量异常大赚交易掩盖整体负期望；
- 在 blind holdout 上反复修改规则；
- 扫描大量参数后只报告最好结果；
- 删除失败实验。

目标不是证明 Logic A 正确，而是让 Logic A 接受历史数据、成交机制和未见样本的检验。
