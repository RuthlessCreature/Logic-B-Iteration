# Data Plan

## 1. 初始研究窗口

- start: 2024-09-30
- end: 2026-09-28
- market: A-share
- baseline excludes: B-share, ETF, CB, index

## 2. Primary Provider: Tushare

### Daily market
- `daily`: OHLCV
- `stk_limit`: 每日涨停/跌停价格
- `stock_basic`: 股票上市/市场基础信息

### Limit-up ecosystem
- `limit_list_ths`: 涨停池、连板池、炸板池、跌停池
- `kpl_list`: 开盘啦涨停/炸板/跌停榜单
- `limit_cpt_list`: 强势概念板块统计

`limit_list_ths` 历史从 2023-11-01 起，足以覆盖初始两年窗口。

### Minute bars
股票历史分钟通过 `pro_bar(..., freq='1min')` 获取；分钟权限需单独开通。

## 3. 数据获取分层

### Layer A — 全市场日级

用于：
- 交易日历
- 涨跌停价
- 市场状态
- 涨停生态
- 候选筛选
- 基础收益计算

### Layer B — 候选股票分钟级

不建议一开始下载全市场两年的所有 1min。

第一阶段只下载：
1. t-1 涨停候选；
2. t 日核心竞争者；
3. 持仓期间股票；
4. 必要的板块/指数代理。

这样可以大幅降低分钟数据量，同时满足 B0 的核心研究。

### Layer C — 高精度成交数据

若 B0/B1 显示正期望，再考虑：
- 逐笔成交
- Level-2
- 集合竞价细节
- 排队成交建模

## 4. Raw Data Manifest

每次下载必须生成 manifest：

```json
{
  "dataset": "limit_list_ths",
  "provider": "tushare",
  "query": {},
  "retrieved_at": "",
  "effective_range": ["", ""],
  "row_count": 0,
  "sha256": "",
  "schema_version": "1"
}
```

## 5. Point-in-time 问题

题材/涨停原因属于最容易产生未来污染的数据。

必须区分：
- 当日盘中已经公开的标签；
- 收盘后才整理出的涨停原因；
- 后续媒体事后归因。

如果某字段在 15:00 后才可获得，它不能参与 09:35 信号。

## 6. 交易规则版本化

交易制度需要 `effective_from/effective_to`。

特别注意：
- 主板 / 科创板 / 创业板涨跌幅不同；
- IPO 前若干交易日可能无涨跌幅限制；
- ST/风险警示制度存在规则变更；
- 交易所规则变化不能向历史倒灌。

## 7. 数据质量检查

每日检查：

- OHLC 是否满足 low <= open/close <= high
- 涨停价/跌停价是否合法
- 收盘涨停标签与收盘价是否一致
- 一字板 high == low 的一致性
- 停牌日是否错误产生行情
- 复权因子是否跳变
- 股票名称/ST 状态是否与日期匹配
- 分钟数据首尾时点是否完整
- 交易量/成交额是否存在异常 0 值
- 同一股票同一时点是否重复

## 8. 数据源交叉验证

建议随机抽取每月：
- 5 个普通涨停
- 3 个一字板
- 3 个炸板
- 3 个跌停
- 2 个新股/特殊规则样本

与第二数据源或交易所公开数据核对。

## 9. 数据不提交策略

GitHub 只提交：
- schema
- manifest
- 小型 fixture
- 测试样本

不提交完整两年分钟大文件。

推荐本地：
```text
data/raw/*.parquet
data/processed/*.parquet
cache/duckdb/
```

并通过 manifest 保证可复现。
