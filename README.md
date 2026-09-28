# Logic-B-Iteration

将“逻辑A”冻结为 **Logic B0**，再以 point-in-time 数据、真实成交约束、T+1 状态机、walk-forward 和 blind holdout 对其进行可复现、可审计的 A 股超短研究。

目标不是把历史曲线拟合得最好看，而是判断一套交易逻辑是否：

- 可解释；
- 可执行；
- 可复现；
- 可审计；
- 对不同市场阶段具有稳定性；
- 在保守成交口径下仍有正期望。

## 当前状态

当前冻结规格：

```text
Logic spec: B0.0.3
Proxy:      B0-P.1
Decision:   09:35
Exit:       E0_NEXT_DAY_0935
Portfolio:  single position / full target / T+1
```

已实现：

- B0-H 人工参考协议；
- B0-P 程序化代理；
- D-1 THS 涨停候选池；
- D-1 KPL 历史题材证据；
- ATTACK / TRIAL / NEUTRAL / RETREAT / ICE 市场状态；
- 09:25 / 09:35 checkpoint 构建；
- 官方每日涨跌停价；
- ST 历史状态过滤；
- 停牌候选过滤；
- 持仓停牌锁定与复牌后继续卖出；
- 主板 / 创业板 / 科创板 universe 硬过滤；
- 无有效涨跌停价格的新股日过滤；
- T+1；
- 涨停不可买；
- 跌停不可卖；
- 禁止信号与成交使用同一根已完成分钟 K；
- 三档成交模型；
- E0 次日 09:35 基线退出；
- 佣金 / 最低佣金 / 过户费 / 印花税成本账本；
- 本地 Parquet 数据湖；
- SHA256 manifest；
- 断点下载；
- 缺分钟数据按需补全；
- 数据源 preflight；
- 数据质量 audit；
- 缓存数据 readiness gate；
- B0-H / B0-P 一致性审计；
- chronological walk-forward；
- blind holdout 默认锁定；
- GitHub Actions 自动测试。

**尚未发布任何两年收益结论。**

真实开发集尚未在本仓库会话中完成下载和运行，因此任何历史收益数字在此之前都无效。

---

## 1. B0 双层定义

### B0-H — Human Reference

B0-H 保留 Logic A 的原始语义：

1. 总龙头；
2. 板块核心容量；
3. 最强换手前排；
4. 明确补涨核心；
5. 冰点 / 退潮不新开仓；
6. 核心不可买或确认不足时空仓；
7. 不使用后排替代买不到的核心。

B0-H 的作用不是制造回测收益，而是回答：

> B0-P 到底还是不是 Logic A？

人工标签协议见：

```text
schemas/human_reference.schema.yaml
docs/06_HUMAN_REFERENCE_PROTOCOL.md
```

### B0-P — Programmatic Proxy

当前为 **B0-P.1**。

核心身份优先级是硬约束：

```text
TOTAL_MARKET_LEADER
    >
SECTOR_CAPACITY_CORE
    >
TURNOVER_FRONT
    >
CATCHUP_CORE
```

程序先确定最高层级候选，再检查：

- confirmation；
- tradability。

最高层级核心未通过闸门时：

```text
CASH
```

而不是自动向下选择次优票。

---

## 2. Point-in-time 原则

任何信号只能使用当时已经可观察的信息。

09:35 信号可使用：

- D-1 完成后的涨停体系；
- D-1 历史题材结构；
- D-1 完成后的市场状态；
- 当日开盘前已知 ST / 风险警示状态；
- 当日停牌状态；
- 当日集合竞价；
- 截至 09:35 已完成的分钟行情。

禁止使用：

- 10:00 / 14:30 / 收盘后的数据反推 09:35；
- 下一交易日收益；
- 事后“大龙头”身份；
- 未来题材成分；
- 事后成交结果定义当前核心。

另外：

> 如果 09:35 完成的分钟 K 被用于生成信号，最早成交只能从后续分钟 K 开始。

---

## 3. 历史题材证据

B0-P 不使用“最新概念成分”回填历史。

当前采用：

```text
D-1 KPL limit-up list
        ↓
historical theme
        ↓
theme breadth / height / amount
        ↓
D day semantic core gate
```

没有历史题材证据时：

- 不允许标记为 `SECTOR_CAPACITY_CORE`；
- 不允许标记为 `CATCHUP_CORE`。

题材强度在 B0.0.3 中主要用于**身份合法性**，而不是收益优化权重。

---

## 4. Universe

当前默认：

```text
main
chinext
star
```

排除：

- 北交所等未纳入板块；
- 当前 ST / 风险警示股票；
- 当前停牌股票；
- 当日没有合法 `up_limit/down_limit` 的无涨跌幅限制情形。

Universe 配置见：

```text
config/b0.yaml
```

---

## 5. 研究区间

完整研究区间：

```text
2024-09-30 ~ 2026-09-28
```

冻结拆分：

```text
Development:
2024-09-30 ~ 2026-06-30

Blind Holdout:
2026-07-01 ~ 2026-09-28
```

开发阶段默认禁止运行 holdout。

Walk-forward 默认：

```text
minimum training window: 120 trading days
validation window:       40 trading days
step:                    40 trading days
warmup:                   2 trading days
```

warmup 只用于建立 D-1 / D-2 状态，其收益不会计入验证结果。

---

## 6. 安装

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

---

## 7. Tushare 凭证

Token 不得写进代码或提交到 Git。

Linux / macOS:

```bash
export TUSHARE_TOKEN="..."
```

PowerShell:

```powershell
$env:TUSHARE_TOKEN="..."
```

当前依赖的数据能力包括：

- 交易日历；
- THS 涨停 / 跌停 / 炸板；
- KPL 历史题材榜；
- 日线；
- 官方每日涨跌停价；
- 历史开盘集合竞价；
- 历史 ST / 风险警示状态；
- 历史停牌状态；
- 股票历史 1 分钟行情。

历史分钟数据通常需要单独权限。

---

## 8. 先跑数据源 Preflight

不要一上来就抓两年数据。

先用一个已完成交易日验证所有权限：

```bash
logic-b preflight-data \
  --date 2026-06-30
```

如果自动选样本股票不合适，可显式指定：

```bash
logic-b preflight-data \
  --date 2026-06-30 \
  --code 600000.SH
```

检查项包括：

```text
trade_calendar
daily
limit_list_ths
kpl_list
stk_limit
stk_auction_o
stock_st
suspend_d
stock_minute_1m
```

任何关键项失败，都不要开始完整历史下载。

---

## 9. 下载日级数据

开发阶段先只下载 development：

```bash
logic-b fetch-daily \
  --start 2024-09-30 \
  --end 2026-06-30
```

支持断点续跑，已存在分区默认跳过。

日级 bundle：

```text
limit_up
limit_down
limit_break
kpl_limit_up
daily
limit_prices
auction
stock_st
suspend
```

---

## 10. 数据审计

```bash
logic-b audit-data \
  --start 2024-09-30 \
  --end 2026-06-30
```

审计包括：

- OHLC 合法性；
- 重复股票；
- 官方涨跌停价覆盖；
- 收盘是否超出官方价格限制；
- THS 涨停池与收盘涨停一致性；
- THS 跌停池与收盘跌停一致性；
- 涨停 / 跌停异常交集；
- 炸板异常交集；
- KPL 字段完整性；
- KPL / THS 涨停覆盖率；
- ST 数据 schema；
- suspend 数据 schema；
- auction 数据 schema。

存在 ERROR 时，不应开始正式回测。

---

## 11. 下载分钟数据

```bash
logic-b fetch-minutes \
  --start 2024-09-30 \
  --end 2026-06-30
```

不会下载全市场两年分钟数据，只下载 D-1 涨停候选。

对于持仓跨日锁死、停牌复牌等导致的额外分钟需求，可以在回放时显式启用：

```text
--fetch-missing-minutes
```

缺失分钟一旦补齐，会持久化到本地数据湖，后续运行可复用。

---

## 12. 数据 Readiness Gate

正式回测前：

```bash
logic-b data-readiness \
  --start 2024-09-30 \
  --end 2026-06-30
```

检查：

- 所有必需日级分区是否存在；
- manifest/hash 是否有效；
- 按真实 universe 过滤后，应下载多少 candidate-minute 分区；
- 当前缺少哪些分钟分区。

`ready=false` 时不要运行正式 baseline。

---

## 13. B0 开发集 Baseline

三档一起跑：

```bash
logic-b run-b0 \
  --start 2024-09-30 \
  --end 2026-06-30 \
  --fill all \
  --fetch-missing-minutes
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

成交口径：

- `optimistic`：上界；
- `realistic`：主研究口径；
- `conservative`：压力测试下界。

---

## 14. 交易成本

B0.0.3 显式建模：

```text
broker commission
minimum commission
transfer fee
sell-side stamp duty
```

默认值在：

```text
config/b0.yaml
```

券商佣金属于账户级条件，必须按真实账户修改，而不是把仓库默认值当成事实。

每笔成交会记录：

- entry_cost；
- exit_cost；
- net_return。

---

## 15. 停牌 / 跌停锁死

持仓不能卖出时，不允许凭空成交。

### 跌停锁死

记录 unfilled sell，继续持有，下一交易日继续尝试。

### 停牌

记录：

```text
side=SELL
filled=false
reason=suspended
```

停牌期间：

- 不成交；
- 沿用上一可交易 mark；
- 复牌后重新进入卖出流程。

---

## 16. Walk-forward

开发集 baseline 之后：

```bash
logic-b walk-forward-b0 \
  --start 2024-09-30 \
  --end 2026-06-30 \
  --fill realistic \
  --fetch-missing-minutes
```

默认窗口来自 `config/b0.yaml`，也可以通过 CLI 显式覆盖。

输出：

```text
runs/walk_forward_<...>/
  fold_metrics.parquet
  summary.json
  spec.json
```

关键结果包括：

- positive_return_fold_rate；
- positive_expectancy_fold_rate；
- median / worst fold return；
- median / worst drawdown；
- closed trades；
- exposure。

禁止随机 shuffle。

---

## 17. B0-H 对齐

人工标签：

```text
schemas/human_reference.schema.yaml
```

比较：

```bash
logic-b align-b0 \
  --human research/human_labels.csv \
  --proxy runs/<run_id>/signals.parquet \
  --out runs/<run_id>/human_alignment.csv
```

指标：

- action agreement；
- selected-code agreement；
- core-type agreement；
- label coverage。

如果 B0-P 收益更高、但 B0-H 语义对齐明显下降，则不能悄悄宣称“Logic A 改进”。

它应进入一个新的 B1+ 假设。

---

## 18. Blind Holdout

以下命令默认拒绝：

```bash
logic-b run-b0 \
  --start 2026-07-01 \
  --end 2026-09-28
```

只有完成以下事项后：

1. B0.0.3 规则冻结；
2. development baseline 完成；
3. walk-forward 完成；
4. B0-H 对齐完成；
5. 不再修改 B0 参数；

才允许：

```bash
logic-b run-b0 \
  --start 2026-07-01 \
  --end 2026-09-28 \
  --fill all \
  --unlock-holdout
```

holdout 只用于最终一次性评估，不得反复调参。

---

## 19. 推荐完整运行顺序

```text
1. preflight-data
        ↓
2. fetch-daily (development only)
        ↓
3. audit-data
        ↓
4. fetch-minutes
        ↓
5. data-readiness
        ↓
6. run-b0 (optimistic / realistic / conservative)
        ↓
7. walk-forward-b0
        ↓
8. B0-H / B0-P alignment
        ↓
9. Freeze candidate
        ↓
10. Unlock blind holdout once
```

任何一步失败，不向后装死硬跑。

---

## 20. 数据许可与仓库边界

完整历史原始数据默认不提交 GitHub。

`.gitignore` 排除：

```text
data/raw/
data/processed/
cache/
runs/
```

公开仓库只保留：

- 代码；
- schema；
- manifest；
- 小型合成 fixture；
- 研究协议；
- 失败实验记录。

第三方历史数据应遵守对应数据授权条款，不在公开仓库重新分发完整数据集。

---

## 21. 研究纪律

禁止：

- 随机 shuffle 时间序列；
- 用收盘信息决定上午交易；
- 用下一日收益定义当天核心；
- 默认一字涨停可以买；
- 默认一字跌停能卖；
- 停牌日凭空成交；
- 用无涨跌幅限制新股污染普通候选集；
- 用当前概念成分回填历史；
- 用少数异常大赚遮盖整体负期望；
- 在 holdout 上反复修改规则；
- 扫大量参数只报告最好结果；
- 删除失败实验。

目标不是证明 Logic A 正确。

目标是让 Logic A 经得起真实历史、真实交易约束、不同市场阶段和未见样本的检验。


---

## 22. Xuangubao 公共 Candidate-Slice 路线

当 Tushare 的历史分钟或部分高级数据权限不可用时，可以使用 Xuangubao 公共数据路线做独立研究。

这条路线不是全市场日线替代，而是：

```text
历史涨停/跌停/炸板/题材证据
        ↓
D-1 涨停候选
        ↓
按候选物化 D 日分钟 / 日线 / 涨跌停价
        ↓
candidate-slice readiness
        ↓
B0 replay
```

完整规格：

```text
docs/07_XUANGUBAO_PUBLIC_PIPELINE.md
```

### 22.1 接口预检

```bash
logic-b preflight-xgb \
  --date 2026-06-30

logic-b preflight-xgb-market \
  --date 2026-06-30
```

### 22.2 构建开发集

建议与 Tushare 数据分开存放：

```bash
logic-b fetch-xgb-evidence \
  --start 2024-09-30 \
  --end 2026-06-30 \
  --data-root data-xgb

logic-b fetch-xgb-market \
  --start 2024-09-30 \
  --end 2026-06-30 \
  --data-root data-xgb
```

### 22.3 XGB 专用 Readiness

```bash
logic-b xgb-readiness \
  --start 2024-09-30 \
  --end 2026-06-30 \
  --data-root data-xgb
```

该检查按策略实际候选 symbol-day 计算覆盖率，不要求伪造全市场日线。

### 22.4 回放与按需补数据

```bash
logic-b run-b0 \
  --start 2024-09-30 \
  --end 2026-06-30 \
  --data-root data-xgb \
  --fill all \
  --fetch-missing-minutes \
  --missing-minute-source xuangubao
```

持仓后续交易日若缺市场数据，runner 会先补完整 symbol-day，再判断是否可卖。

### 22.5 重要限制

Xuangubao 公共 fallback 当前有以下明确限制：

- 历史 ST 状态不是官方逐日表，候选侧使用 D-1 名称进行保守推断；
- `is_new_stock=true` 的候选在启用 IPO 无涨跌幅限制排除时直接保守剔除；
- fallback 生成的 `daily / limit_prices` 不会静默覆盖已有更高权威数据；
- 推荐单独使用 `data-xgb`，避免不同源的历史口径混杂；
- XGB 路线的收益结果必须单独标明数据源，不得与 Tushare 路线静默拼接成同一结论。
