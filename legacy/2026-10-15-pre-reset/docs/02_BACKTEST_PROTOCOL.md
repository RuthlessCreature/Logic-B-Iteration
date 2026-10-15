# Backtest Protocol

## 1. 目的

确保任何 B 版本的收益结果不是由未来函数、不可成交价格、幸存者偏差或数据清洗错误制造出来的。

## 2. 时间结构

初始总区间：

- 2024-09-30 ~ 2026-09-28

推荐 walk-forward：

```text
Fold 1: train 6m -> validate 2m
Fold 2: roll +2m
Fold 3: roll +2m
...
Final: untouched blind holdout
```

最终 blind holdout 在实验启动时冻结；在版本正式评估之前不得查看其策略表现并据此改规则。

## 3. 数据层

### 必需

- 交易日历
- 股票基础信息及历史名称/ST状态
- 复权因子
- 日 OHLCV
- 每日涨跌停价
- 涨停/跌停/炸板榜单
- 连板/N日M板
- 首封/末封时间
- 开板次数
- 成交额/换手率
- 流通市值
- 题材/涨停原因
- 板块强度
- 指数行情

### 强烈建议

- 1分钟行情
- 逐笔/盘口（用于高级成交模型）
- 集合竞价数据
- 历史公告时间
- 异动/龙虎榜

## 4. 交易制度必须日期化

不能把今天的交易规则套到两年前。

Rule Engine 至少按以下维度决定每日限制：

- exchange
- board
- ST/risk-warning status
- listing age
- special no-limit days
- effective date of exchange rule changes

## 5. 成交模型

至少提供三档：

### Fill-A Optimistic

只要决策后存在对应价格成交，即认为可成交。

仅用于上界估计，不作为正式收益。

### Fill-B Realistic

基于分钟成交量、涨停状态、开板持续时间、可交易窗口估算成交。

作为主要研究口径。

### Fill-C Conservative

对秒板、一字板、极小成交窗口、涨停排队施加严格过滤。

作为收益下界。

正式报告必须同时给出 B/C，必要时附 A。

## 6. 成本

配置化：

- 佣金
- 最低佣金
- 印花税
- 过户相关费用
- 滑点
- 冲击成本

成本规则同样允许按日期变化。

## 7. T+1

买入日不得卖出。

若次日一字跌停或无有效成交窗口：
- 不允许假设按跌停价顺利卖出；
- 持仓继续锁定；
- 直到模型判定存在可成交窗口。

## 8. 禁止未来函数

典型违规：

- 用 t 日最终涨停家数决定 t 日 09:35 买入；
- 用 t 日最终封板状态决定上午是否追板；
- 用收盘后形成的题材排名决定盘中交易；
- 用次日最高价判断前日买点；
- 用回测后才知道的“大龙头”身份标记其早期买点。

所有特征必须声明 `available_at`。

## 9. 收益指标

至少：

- Total Return
- CAGR
- Annualized Log Return
- Max Drawdown
- Calmar
- Profit Factor
- Win Rate
- Expectancy per Trade
- Median Trade Return
- Avg Win / Avg Loss
- Max Consecutive Losses
- Turnover
- Exposure
- Number of Trades
- Unfillable Signal Rate
- Limit-down Lock Rate

## 10. 稳健性

必须切片：

- 年 / 季 / 月
- 牛 / 熊 / 震荡
- ATTACK / TRIAL / RETREAT / ICE
- 高位周期 / 空间压缩期
- 主线集中 / 多题材轮动
- 主板 / 创业板 / 科创板
- 一字 / 换手 / T字
- 高位 / 中位 / 低位补涨

## 11. 统计不确定性

建议：
- block bootstrap
- 交易序列 bootstrap
- bootstrap CI of CAGR / expectancy
- 参数敏感性热图
- 扰动交易成本
- 扰动成交概率
- 扰动入场时间

如果轻微扰动导致策略从大赚变大亏，视为脆弱。

## 12. 回测输出

每次运行输出：

```text
runs/<run_id>/
  config.yaml
  version.json
  data_manifest.json
  trades.parquet
  signals.parquet
  daily_equity.parquet
  metrics.json
  regime_metrics.json
  failure_cases.csv
  report.md
```

所有结果必须能从 commit + config + data manifest 完整复现。
