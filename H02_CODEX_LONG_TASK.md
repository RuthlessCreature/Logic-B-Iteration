# H02 FAST-TRACK：先出真实数据结果

**最新、优先执行规格：** [H02_FAST_TRACK_EXECUTION.md](research/handoffs/h02-20261014/H02_FAST_TRACK_EXECUTION.md)

用户明确要求加快看到结果。**当前以FAST-0→FAST-1→FAST-2为最优先**：马上盘点现有数据、做2020-01-03的三股与全日候选真实覆盖统计、查明官方限价/PIT阻碍；之后按日扩至2020-01。无需等待七个旧工程包顺序全部完成。可以并行修认证门与合成交易账本。**所有旧文档的Git/冻结策略/真实收益准入/留出集硬约束继续适用。**

**本地Codex首句话：** 请阅读本入口、FAST-TRACK文档和旧完整规格，直接执行FAST-0、FAST-1、FAST-2；每个有数据的checkpoint输出实际分子/分母、SHA、失败reason、commit及新HEAD CI，缺权限则真实BLOCKED同时做离线任务。不要只回复计划。

---

# H02 长任务 — 本地 Codex 唯一当前入口

**完整执行规格：** [research/handoffs/h02-20261014/H02_LONG_TASK_EVIDENCE_PIPELINE.md](research/handoffs/h02-20261014/H02_LONG_TASK_EVIDENCE_PIPELINE.md)

上一个 H02_CODEX_START.md 是 P0/P1/P2-A 的历史交接，**已经完成，不要重复执行**。当前长任务以本文件链接的 H02-LT 文档为准。

## 直接发给本地 Codex 的指令

你是 RuthlessCreature/Logic-B-Iteration 研究工程执行代理。先完整阅读 `H02_CODEX_LONG_TASK.md` 及其链接的长任务文档、README、配置、相关 H02 源码与已有测试。

**只在 `research/behavioral-edge-20261013` 上工作。** 先审计最新远端 HEAD、PR #1 Draft 和本地工作区；确认之前 P2-B HEAD `0c6fa4ff` 的成果已经存在，若 HEAD 已前进需审阅差异，不能覆盖用户修改。

按长任务 P0→P1→P2→P3/P4/P5/P6→P7 的依赖逐包推进，尽可能完成所有不需要付费凭证的工程任务。每阶段都需要实际代码、专项及全量测试、独立 commit、push、对应新 HEAD 的 CI 和 durable progress checkpoint。上一个步骤失败先修复；权限不可用则标 BLOCKED，继续其他独立步骤。**不能只读计划或只写报告。**

禁止：修改或合并 main、合并或转正 PR #1、读取/解锁保护留出集 `2026-07-01..2026-09-28`、改 `config/b0.yaml`、调参、补造市场数据、冒充09:35时点、拿分钟有量推断真实成交、泄漏凭证、未经数据认证输出实盘收益率。

遇到真实付费/权限申请、主干操作、解锁留出集或任何不可逆高风险操作，停止并说明需要用户授权；其他任务无需重复向用户确认。完成后按完整规格提交 `H02-LT LOCAL CODEX REPORT`，用户再让 ChatGPT 独立验收。

**重要：** 当前 P2-B 只实现固定 BLOCKED 的安全序列化器。长期任务目标是把数据来源、原始字节、历史可用时间和成交假设分别核验，并如实报告限制，不是将 BLOCKED 简单改成 READY。
