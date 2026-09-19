# Baoxian Agent

保险行业多 Agent 协作的理赔决策支持示例。项目把一次理赔审核拆成多个职责清晰、可独立验证的智能体，再由确定性的决策门统一汇总结果，适合用于保险核赔、保单问答和审核流程原型。

> 本项目是决策支持演示，不是自动赔付系统。`APPROVED` 代表模拟审核建议，不代表真实赔付或法律结论。仓库中的保单和案件均为测试数据，请勿用于真实客户。

## 多 Agent 协作

一次理赔请求会经过三个专业 Agent：

1. **保单 Agent**：检索保单条款，判断事故是否有可核验的承保或除外条款，并返回原文证据。
2. **案件审核 Agent**：检查事故描述、损失情况和必要材料，识别缺失文件及材料矛盾。
3. **风险分析 Agent**：根据案件中的风险标记计算风险等级，不直接认定欺诈。
4. **决策门**：用确定性规则汇总三个 Agent 的结构化结果，输出 `APPROVED`、`DENIED`、`NEED_MORE_INFO` 或 `HUMAN_REVIEW`。

```text
用户问题
   |
   +--> 保单 Agent ------ 条款证据
   +--> 案件审核 Agent -- 材料与一致性
   +--> 风险分析 Agent -- 风险等级
             |
             v
        决策门与审计记录
```

Agent 使用 PydanticAI 和 Pydantic 结构化输出；决策门不把最终判断交给模型，从而保证缺少材料、无法验证条款或出现高风险时能够稳定升级人工复核。项目不使用 LangGraph，也不依赖 Azure。

## 功能

- 理赔案件创建、查询和审核
- 保单条款 Markdown 检索与证据引用
- 风险、材料完整性和条款覆盖的分工协作
- SQLite 审计记录与 `trace_id` 追踪
- 中文保单问答和中文测试案例
- OpenAI 兼容接口，可接入任意兼容的聊天前端
- 默认 `mock` 模式离线运行；可选 `ollama` 模式调用本地模型

## 快速开始

需要 Python 3.11+，建议使用 `uv` 管理环境：

```powershell
cd baoxian-agent
uv venv .venv
uv pip install --python .venv\Scripts\python.exe -e ".[test]"
\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

服务启动后，访问 `http://127.0.0.1:8000/docs` 查看 API 文档。常用接口包括 `GET /health`、`GET /v1/claims`、`POST /v1/claims/{claim_id}/decide`、`GET /v1/claims/{claim_id}/decisions`、`POST /v1/chat` 和 `POST /v1/chat/completions`。

聊天接口示例：

```text
请审核 CL001
根据综合汽车保单，车辆被盗是否承保？
```

## 配置模式

默认模式为 `mock`，使用规则和本地测试数据，不需要网络或模型服务。若要使用本地兼容模型：

```powershell
$env:INSURANCE_AGENT_MODE="ollama"
$env:OLLAMA_BASE_URL="http://localhost:11434/v1"
$env:OLLAMA_MODEL="qwen3:8b"
\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

模型调用失败或返回无法由本地条款验证的结果时，服务会以 HTTP 503 失败关闭，不会写入虚假的审核记录。

## 测试

```powershell
\.venv\Scripts\python -m pytest -q
```

测试覆盖基础案件、中文保单问答、中文测试夹具、审计记录、模型故障关闭和证据校验。

## 目录结构

```text
app/                 Agent、决策门、API 和存储
data/policies/       本地 Markdown 保单
tests/               回归测试和中文测试夹具
frontend/            轻量对话前端源码
docs/                产品与验收说明
```

## 许可证与责任边界

这是一个保险行业技术原型。生产环境还需要接入真实保单系统、权限控制、脱敏流程、人工复核机制、模型评估和合规审计。任何赔付决定都必须由授权业务人员依据正式保单和适用法律作出。
