# Changelog

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
