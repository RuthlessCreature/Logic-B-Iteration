# TypeSafe AI Jev — Logic-B Decision API 预留说明

**状态：`RESERVED / DISABLED / NOT_CONNECTED / NOT_BILLED`。** 这是2026-10-15新增需求，不得做付费联网激活、账户注册、密钥申请或模型基准试验。

## 1. 定位：它不是 OpenAI/DeepSeek 文本生成接口

TypeSafe AI Jev System One 是返回类型约束的**智能决策**：`choice` 多选分类、`score` 等级评分、`noul` 是/否概率。OpenAI 仍承担主要高推理假设与研究设计；DeepSeek 是**未来生产运行时的上下文推理 Provider**（当前禁用，既有研究提案接口只是早期预留实现）；Jev 是**未来生产运行时的类型化 DecisionProvider**。Codex/OpenAI 独立负责离线历史研究和策略迭代。

官方接口：
- `POST https://api.typesafe.ai/v1/systemone`，Bearer `TYPESAFE_API_KEY`
- `GET https://api.typesafe.ai/v1/models`，账户授权后获取实时支持的模型名
- 官方 API 规格：https://api.typesafe.ai/openapi.json
- 官网：https://typesafe.ai/

**不要**和非官方社区网关 `/api/v1/decide` 混用，价格、密钥、数据隐私条款不相同。

## 2. 逻辑B预留任务

| 系统用途 | 官方问题类型 | 建议效果指标 |
|---|---|---|
| 市场状态辅助分类（ATTACK/TRIAL/NEUTRAL/RETREAT/ICE） | `choice` | 类别前向稳定性、与确定性Regime差异、风险误放行率 |
| 隔日跌停/锁仓风险辅助分级 | `score` | 尾部极端事件召回、离线校准、拒单后实际费后净值 |
| 高位负反馈外溢提示 | `noul` | 历史对照概率误差、错误拒绝机会成本 |

**未来 JEV 将在经过 Shadow/Paper 及历史对照验证后参与工程应用的日常决策链；不只是研究工具。JEV 输出不等于真实市场心理**：它是基于历史信息的可测试辅助分类，不是真实投资者数据，供应商声称的校准概率也不能替代针对市场时段的独立校准检验。

## 3. 安全和数据协议

仅允许使用 `DecisionRequest(asof, task, state)`，从已经由确定性代码计算/核验过的训练时点特征采样，严格 `evidence_asof <= decision_asof`，不允许未来收益、当日收盘后事件、受保护 2026-07-01..09-28 市场数据、账户私人信息和密钥混入state。

现有 `build_jev_questions` 已有三个问题模板；没有完整05-06年状态数据之前，不能让Jev“随意解释”无来源新闻。返回answer必须匹配官方schema且类型与问题一致，所有概率有合法范围、输出留SHA和明确使用模型版本。

## 4. 当前代码文件与测试

- `config/decision_providers.json`：`active_provider: deterministic`，`jev_typesafe.enabled: false`，`allow_external_calls: false`，`model: null`。
- `src/logic_b/decision_providers.py`：typed provider Protocol、官方payload组装、mock运输注入、历史时间/字段过滤。
- `tests/test_decision_providers.py`：默认禁用、无网络、无密钥、无模型、超范围历史、当日未来数据、mock response类型校验。

离线检验：
```bash
python -m pytest -q tests/test_decision_providers.py
```

**禁用状态下不能运行真实Jev服务**；独立测试可以临时使用虚构凭据与模拟响应，不意味着厂商服务真实连通。

## 5. 将来如何启用（本轮不得执行）

1. 用户明确授权使用 TypeSafe/Jev，并给出是否接受潜在付费调用的上限。
2. 通过官方账户获得 `TYPESAFE_API_KEY`，保存在GitHub Actions Secrets或用户自己的服务端环境；不写入repo或聊天正文。
3. 受权限控制，调用官方模型发现接口确认当时可用具体模型版本，**固定版本**；更新单独config。
4. 审核并实现正式 `transport`，限制超时、重试、配额、错误处理、隐私/合规、输入快照hash、token费用审计。
5. 在相同固定训练/验证历史材料上，先做**shadow-only**评估，不用于买卖触发；胜过确定性Regime才能申请提升研究权重。
6. 状态 `CONNECTED` 仅在已验证真实调用、录入日志和费用后可用；否则保持 `RESERVED`。

优先级：先修BaoStock采集、行情长期存储、增量回放、真正MarketState的确定性基线。Jev adapter已留足扩展口，不应抢占主工程资源。


## 6. 正式角色修订（2026-10-15）

在生产系统中，Jev可以成为日常运行时的**已验证类型化推理组件**，而非只是保存一份离线研究评分。Codex负责开发和冻结策略；Jev负责在真实09:35截止时刻基于合法特征给出 choice/score/noul；DeepSeek承担互补的Runtime上下文信号。Jev的响应允许参与**经过用户批准、训练/前向验证的既定组合规则**，但不允许凭即时评分临时改变规则或撤销硬风险门。上线前需要先进行Shadow→Paper→人工Follow对照，保证超时、API失败、上游数据缺失时按冻结降级策略处理。详见 [双阶段架构](RESEARCH_VS_RUNTIME_ARCHITECTURE.md)。
