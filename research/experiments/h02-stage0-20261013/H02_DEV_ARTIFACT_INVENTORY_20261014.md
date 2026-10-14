# H02 2024–2026 开发期 artifact 盘点

盘点时间：2026-10-14。数据只读范围：2024-01-02 至 2026-06-30。保护留出期 `2026-07-01..2026-09-28` 未下载、未读取、未计算。

## 可复核结果

从 [H01 历史回填 run 38358815302](https://github.com/RuthlessCreature/Logic-B-Iteration/actions/runs/38358815302) 下载了五个既存开发期 artifacts 到系统临时目录，未写入仓库。审计脚本 [`scripts/h02_audit_dev_artifact_coverage.py`](../../../scripts/h02_audit_dev_artifact_coverage.py) 对 ZIP 内原始 Parquet 字节逐项校验 manifest SHA；对候选池实际读取 Parquet 后重算行数、证券日唯一性、交易日连续性和供应商自带日计数。

| 区段 | 交易日 | `limit_up` 分区 | 事件池行 / 唯一 symbol-days | Artifact ID | Archive SHA256 |
|---|---:|---:|---:|---:|---|
| 2024H1 | 117 | 117/117 | 8,085 / 8,085 | 11797278322 | `1abfc7022075958537e635b107c0919a68122dc0ff6b7a97cec6132f9ab6fec8` |
| 2024H2 | 125 | 125/125 | 12,287 / 12,287 | 11797792805 | `ddd770f7f0dc1322c2d782ae1925d43df302570277c0b53af0bde8bef674c1ad` |
| 2025H1 | 117 | 117/117 | 9,146 / 9,146 | 11797588455 | `cb9bca81e71fa42ed85659564e5a6a7f446f25cbfc1bc7005d734529dbdc0c67` |
| 2025H2 | 126 | 126/126 | 8,985 / 8,985 | 11798034955 | `8c4a9c90acfc9b7e841a453b127b2dcfb6dcc68e43566ca9f5838d1dcbcb0144` |
| 2026开发期 | 116 | 116/116 | 10,138 / 10,138 | 11798524194 | `7da9da754fb7d976b03a371666fd9d27fec0fcaf4f4f784dbecae01e978e857c` |
| **合计** | **601** | **601/601** | **48,641 / 48,641** | — | 分段哈希列于上 |

五个 artifact 中的 **3,010/3,010** 份 dataset manifest 哈希均与对应 ZIP 内原始 Parquet 字节吻合，包括 `calendar`、`limit_break`、`limit_down`、`limit_up`、`market_indicator`、`theme_limit_up`。所有 601 个 `limit_up` 分区均覆盖当期日历交易日；重复证券日 0。Xuangubao `market_indicator.limit_up_count` 与 `limit_up` 行数相符 **601/601**。这是同一供应商内的口径一致性检查，不是独立市场完整性证明。

`limit_up` 是供应商事件池，不是冻结 B0 过滤后的最终候选数。它从 2024-01-02 起连续存在，但由于没有重放执行日输入，无法计算 B0 过滤后实际信号分母。最早 TIER E 可认证连续样本：**无**。

## 真实回测缺口

这五个 artifacts 只含 `calendar`、限价事件/跌停/炸板/题材池和 `market_indicator`。没有独立日线、官方逐股涨跌停价、ST、停牌或 1 分钟执行数据。历史 `available_at` 也没有保存在 artifact manifest 中；`retrieved_at` 为 2026-10-13，不能证明数据在 2024–2026 对应决策时点已可见。

因此，这 48,641 个事件池 symbol-days 的数据诊断结果不是回测样本：官方限价、PIT ST、PIT 停牌均为 **0/48,641**；策略过滤后分母未知，1 分钟执行数据在所选 artifacts 中为 **0 分区**，所以真实可执行资格为 **0 个已认证样本**，不得解释为账户实际会选出 48,641 次交易。

## 许可和保留边界

artifact manifest 标注来源为 Xuangubao，但项目留存资料没有确立其再分发许可或历史时点可见性。这轮只从既存 CI artifact 读取并在临时目录验证；机器可读报告只保存摘要、来源分区哈希和计数，不保存证券行。GitHub artifact API 显示这些 artifacts 预计于 **2026-11-12** 过期；没有通过本报告授权新的 Xuangubao 请求或原始数据转存。

机器可读明细：[`H02_DEV_ARTIFACT_INVENTORY_20261014.json`](H02_DEV_ARTIFACT_INVENTORY_20261014.json)。
