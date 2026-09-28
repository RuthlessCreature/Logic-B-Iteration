# Changelog

## B0.0.3 - 2026-09-28

### Added
- 数据源 `preflight-data`：运行长周期下载前验证全部关键接口和历史分钟权限。
- `stock_st` 历史风险警示状态进入 point-in-time universe。
- `suspend_d` 历史停牌数据进入 ingest、preflight 和 replay。
- 持仓停牌锁定、上一可交易价格估值和复牌后继续卖出。
- 主板 / 创业板 / 科创板硬 universe 过滤。
- 无合法每日涨跌停价格的新股日过滤。
- 明确的佣金、最低佣金、过户费和印花税成本模型。
- 每笔交易记录 entry_cost / exit_cost。
- 辅助数据审计：KPL / ST / suspend / auction。
- 缓存数据 `data-readiness` 门，检查日级分区、manifest/hash 和候选分钟数据覆盖。
- 缺失分钟按需补全并持久化。
- chronological expanding-window walk-forward 引擎与 CLI。
- walk-forward warmup 收益隔离，验证结果从 warmup 最后实际净值重新计量。

### Changed
- Walk-forward 窗口参数正式冻结到 `config/b0.yaml`。
- B0 runner、provider、ingest、strategy 的 KPL/ST/suspend 数据契约完成端到端收敛。
- Universe 配置不再是文档声明，实际进入 replay candidate filter。
- B0.0.3 完成后，开发阶段原则上只允许修数据/实现缺陷，不允许依据收益随意改 B0 规则。

### Validation
- 新增 provider→ingest 合同集成测试。
- 新增 KPL/ST runner 集成测试。
- 新增停牌持仓复牌退出测试。
- 新增 universe、交易成本、readiness、walk-forward 回归测试。
- Blind holdout 继续默认锁定。
- 仍未发布真实两年收益结论。

## B0.0.2 - 2026-09-28

### Added
- 引入 KPL 历史题材标签作为 D-1 point-in-time 板块证据。
- 增加 `B0-H` 人工参考标签 schema 和 B0-H/B0-P 对齐指标。
- 增加数据质量审计模块与 `audit-data` CLI。
- 增加缓存日历分区发现，允许从较大缓存区间运行开发子区间。
- blind holdout 默认锁定，只有显式 `--unlock-holdout` 才允许最终评估。

### Changed
- B0-P 升级为 `B0-P.1`。
- 没有历史题材证据时，不再允许将个股标记为板块容量核心或补涨核心。
- 严格执行 Logic A 核心优先级：总龙头 > 板块核心容量 > 最强换手前排 > 明确补涨核心。
- 最高优先级核心确认/可成交失败后直接空仓，不向次优候选降级。
- 09:35 完成 bar 产生信号后，成交必须从后续 bar 开始。

### Validation
- GitHub Actions 持续运行单元测试、CLI smoke test 和配置校验。
- 当前版本仍未发布历史收益结论；真实开发集数据与 B0-H 对齐尚未完成。

## B0.0.1 - 2026-09-28

### Added
- Python 可执行研究框架。
- Tushare provider。
- 本地 Parquet + SHA256 manifest 数据层。
- 09:25 / 09:35 checkpoint 构建。
- 市场 regime 构建。
- 三档成交模型。
- T+1 单仓状态机。
- E0 次日 09:35 基线退出。
- 回放器、metrics、run artifacts。
- GitHub Actions 测试流程。

### Fixed
- 禁止利用信号生成所依赖的同一根分钟 bar 成交。

## B0.0.0 - 2026-09-28

### Added
- 初始化 Logic-B-Iteration 研究仓库。
- 冻结 Logic A 为 Logic B0。
- 引入 B0-H（人工参考）与 B0-P（程序化代理）双层定义。
- 定义 Point-in-time、T+1、成交约束和日期化交易规则。
- 建立 walk-forward / blind holdout / promotion gate 协议。
- 建立 failure-case taxonomy。
- 明确当前阶段不接受未经真实成交建模的收益数字。
