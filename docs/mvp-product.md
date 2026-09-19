# 保险理赔 Agent 第一版产品契约

## 目标与边界

面向车险理赔审核人员，输入一条已有理赔案件及其保单，生成**可追溯的审核建议**。借鉴原项目的“保单核验、材料审核、风险分析、统一决策”职责划分，但不使用 Azure 或 LangGraph。专业判断由 PydanticAI Agent 在本地 Ollama 模式完成，原生 Python 执行确定性决策规则。默认 `INSURANCE_AGENT_MODE=mock` 提供不依赖模型的离线回归；`INSURANCE_AGENT_MODE=ollama` 才调用本地模型。两种模式必须使用相同结果和审计契约。

第一版只处理项目自带的车险 Markdown 条款与种子理赔数据，不接外部核心业务系统，不提供图片 OCR、PDF 解析、在线付款、保单签发、生产自动拒赔或生产自动批准。`APPROVED` / `DENIED` 只是审核建议，不执行支付或变更保险业务状态。任何模型生成文字不能取代原文证据和人工复核。

## 用户流程

1. 审核员查看 `GET /v1/claims`，选择 `CL001` 到 `CL010` 的案件。
2. `GET /v1/claims/{claim_id}` 查看案件事实、已有材料和保单号。
3. `POST /v1/claims/{claim_id}/decide`，请求体可省略；系统读取案件和对应条款，产生三份专业报告并执行规则门。
4. 审核员查看建议、理由、条款原文、报告及追踪号；可通过 `GET /v1/claims/{claim_id}/decisions` 查询历史记录。
5. `HUMAN_REVIEW` 由具备权限的人员线下核验，`NEED_MORE_INFO` 表示补齐材料后再评估。第一版不提供在系统内修改材料或人工结案的工作流。

`GET /health` 用于判定 API 是否就绪。未知案件返回 404，而不是虚构理赔结果；内部模型/数据故障不可伪装成成功审批。

## 输入和数据契约

种子案件 ID 为 `CL001` 到 `CL010`。每案至少有 `claim_id`、`policy_number`、事故基本事实、材料清单、审核风险事实；保单条款存在于本地 Markdown。专业 Agent 只能通过受限的业务读取接口读取该案件、相关保单及必要历史，不能执行任意 SQL、任意文件读写或跨案检索。第一版 SQLite 保留案件与决策历史，原文条款以本地文件为真源。

不将完整身份资料塞进提示词；演示数据不得是真实客户个人信息。后续接入生产数据时需要权限控制、加密、保留期限和脱敏评估，不在 MVP 中声称满足监管上线要求。

## 决策契约

`POST /v1/claims/{claim_id}/decide` 返回 JSON：

```json
{
  "claim_id": "CL001",
  "policy_number": "AUTO-BASIC",
  "decision": "APPROVED",
  "reason": "基于案件事实、条款及风险报告的审核建议",
  "evidence": [{"source_id": "AUTO-BASIC.md", "quote": "Coverage: Accidental collision damage to the insured vehicle is covered, subject to submitted accident statement and repair estimate."}],
  "agent_reports": {"policy": {}, "review": {}, "risk": {}},
  "trace_id": "唯一追踪标识"
}
```

`decision` 仅为 `APPROVED`、`DENIED`、`NEED_MORE_INFO`、`HUMAN_REVIEW` 之一。`agent_reports.policy` 应表示承保、明确不承保或无法确认（`covered: true | false | null`），并提供条款证据；`review` 指出材料完整性和疑点；`risk` 给出低/中/高等级与风险信号。所有对外条款证据必须同时包含能定位真源的 `source_id` 和与本地 Markdown 匹配的非空 `quote`。不能把模型猜测或仅仅一个文件名当成证据。`trace_id` 应能关联本次响应与 SQLite `decisions(trace_id, claim_id, created_at, payload_json)` 中的单条决策审计记录；`GET /v1/claims/{claim_id}/decisions` 返回 `DecisionResponse` 列表。重复请求产生新的可查询记录，不能默默修改旧记录。

规则按下列顺序短路，保证不同来源结论冲突时不会自动批准：

1. 必需理赔材料缺失：`NEED_MORE_INFO`，明确列出待补材料。
2. 高风险、重大疑点、事实相互矛盾、保单不存在/无法取得有效条款引用、模型输出不可核验：`HUMAN_REVIEW`。
3. 条款证据明确证明事故不在保障范围或触发除外责任：`DENIED`，必须指明可核验条款依据。事实疑点、无效索赔嫌疑或材料矛盾只能转人工，不能由模型自行拒赔。
4. 只有材料完整、条款明确承保、有有效条款引用、审核有效且风险低或中、没有重大疑点时，才可 `APPROVED`。

这里的 `covered=null` 不能视为 `false`；“没有找到承保证据”不等于“已证明不承保”。缺材料与高风险同时存在时先要求补材料；补齐后必须重新运行风险检查。任何未覆盖的异常状态都不得回落到 `APPROVED`。

## 人工复核界线

- 风险等级 `high`、欺诈迹象、关键材料互相冲突、条款无法确认、证据引用不可核验，均不得自动批准或拒赔，返回 `HUMAN_REVIEW`。
- 高金额、敏感人身信息、外部系统写操作和真实赔付都不在 MVP 自动决策范围；即使显示 `APPROVED` 仍需人按实际授权流程处理。
- 模型超时、输出校验失败、检索异常不产生肯定性理赔建议；API 应明确报告故障或生成可审计的人工复核状态，不能假装证据已核实。
- 人工人员需要看到完整三份报告、关键事实、证据原文、理由与 `trace_id`，以便独立复查，不能只看结论分数。

## 可核验的 MVP 验收

1. 无 Azure 账号、服务和密钥时可启动本地 API，并在 mock 模式运行全部十条固定案例；PydanticAI + Ollama 是可选择的真实模型路径，不能以 LangGraph 或 Azure 替代。
2. 上述五个端点可请求；未知案件 404。相同 seed 在 mock 模式重复运行给出相同四态结论，且各次 `trace_id` 独立、历史记录可查。
3. 十条案例按 [acceptance-cases.md](acceptance-cases.md) 逐项检验输出、优先级、证据及审计；高风险和证据不明绝不批准。
4. 所有 `APPROVED` 与条款型 `DENIED` 都有可在本地 Markdown 核对的原文引用；每次返回三份结构化专业报告，Pydantic 校验不允许把任意文本冒充业务结果。
5. 本地可执行的自动回归覆盖接口、规则分支、错误路径及审计关联。真实 Ollama 模式仅在已安装和启动对应本地模型的环境验收，不将离线 mock 通过误称为模型推理已验证。

本版本交付的是一个供审核员验证的样机，不是合规认证或生产部署方案。
