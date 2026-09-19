import os
import re
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from .policies import PolicyRepository
from .knowledge import answer_policy_question
from .schemas import ChatRequest, ChatResponse, Claim, DecisionResponse
from .service import ClaimService, ModelAssessmentError
from .storage import Storage


PROJECT_DIR = Path(__file__).resolve().parents[1]


def configured_path(variable: str, default: str) -> Path:
    configured = Path(os.getenv(variable, default))
    return configured if configured.is_absolute() else PROJECT_DIR / configured


def create_app(db_path: Path | None = None, mode: str | None = None, policy_dir: Path | None = None) -> FastAPI:
    store = Storage(db_path or configured_path("INSURANCE_AGENT_DB_PATH", "data/insurance.sqlite3"))
    policies = PolicyRepository(policy_dir or configured_path("INSURANCE_AGENT_POLICY_DIR", "data/policies"))
    service = ClaimService(policies, mode or os.getenv("INSURANCE_AGENT_MODE", "mock"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store.initialize()
        yield

    app = FastAPI(title="Insurance Claim Decision Support", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": service.mode}

    @app.get("/v1/claims", response_model=list[Claim])
    def list_claims():
        return store.list_claims()

    @app.post("/v1/claims", response_model=Claim, status_code=201)
    def create_claim(claim: Claim):
        if not store.create_claim(claim):
            raise HTTPException(status_code=409, detail="Claim ID already exists")
        return claim

    def require_claim(claim_id: str) -> Claim:
        claim = store.get_claim(claim_id)
        if claim is None:
            raise HTTPException(status_code=404, detail="Claim not found")
        return claim

    @app.get("/v1/claims/{claim_id}", response_model=Claim)
    def get_claim(claim_id: str):
        return require_claim(claim_id)

    @app.post("/v1/claims/{claim_id}/decide", response_model=DecisionResponse)
    async def decide(claim_id: str):
        claim = require_claim(claim_id)
        try:
            decision = await service.assess(claim)
        except ModelAssessmentError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        store.save_decision(decision)
        return decision

    @app.post("/v1/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        """Chat entry point for the assistant-ui frontend.

        The first version intentionally keeps intent extraction deterministic:
        the user names a seeded claim (for example CL001), then the existing
        claim workflow performs the specialist assessment.
        """
        user_messages = [message.content for message in request.messages if message.role == "user"]
        prompt = user_messages[-1] if user_messages else ""
        policy_answer = answer_policy_question(prompt)
        if policy_answer:
            return ChatResponse(
                content=f"{policy_answer.answer}\n\n来源：{policy_answer.source}\n\n以上为保单条款摘要，最终承保范围以正式保单和批单为准。"
            )
        match = re.search(r"\bCL\d{3}\b", prompt.upper())
        if not match:
            return ChatResponse(
                content="请提供理赔案件编号，例如：请审核 CL001。",
            )

        claim_id = match.group(0)
        claim = require_claim(claim_id)
        try:
            decision = await service.assess(claim)
        except ModelAssessmentError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        store.save_decision(decision)
        evidence = "\n".join(
            f"- {item.source_id}: {item.quote}" for item in decision.evidence[:4]
        )
        content = (
            f"案件 {decision.claim_id} 的审核建议：**{decision.decision}**\n\n"
            f"{decision.reason}\n\n"
            f"追踪号：`{decision.trace_id}`\n\n"
            f"证据：\n{evidence or '- 暂无可核验证据'}"
        )
        return ChatResponse(
            content=content,
            decision=decision.decision,
            claim_id=decision.claim_id,
            trace_id=decision.trace_id,
        )

    @app.get("/v1/models")
    def models():
        """Expose the Baoxian Agent as an OpenAI-compatible model."""
        return {
            "object": "list",
            "data": [{
                "id": "baoxian-agent",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "insurance-agent",
            }],
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(request: dict):
        """OpenAI-compatible adapter for chat clients."""
        messages = request.get("messages") or []
        internal_messages = [
            {"role": item.get("role"), "content": item.get("content", "")}
            for item in messages
            if item.get("role") in {"user", "assistant"}
        ]
        if not internal_messages:
            raise HTTPException(status_code=422, detail="messages must contain a user message")
        result = await chat(ChatRequest(messages=internal_messages))
        completion_id = f"chatcmpl-{result.trace_id or int(time.time())}"
        payload = {
            "id": completion_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.get("model") or "baoxian-agent",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": result.content},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        if not request.get("stream"):
            return payload

        async def event_stream():
            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": payload["created"],
                "model": payload["model"],
                "choices": [{"index": 0, "delta": {"role": "assistant", "content": result.content}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': payload['created'], 'model': payload['model'], 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.get("/v1/claims/{claim_id}/decisions", response_model=list[DecisionResponse])
    def decisions(claim_id: str):
        require_claim(claim_id)
        return store.decisions(claim_id)

    return app


app = create_app()
