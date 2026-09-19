# Baoxian Agent

A local-first insurance claim decision-support service. It uses FastAPI, SQLite, Markdown policy search, and three PydanticAI agents. The default `mock` mode is deterministic and runs without a model or network. `ollama` mode calls an OpenAI-compatible model endpoint.

**This is a decision-support demonstration, not an automatic payment or production approval system.** `APPROVED` is a simulated recommendation only. Do not use the bundled fictional policy or claim data with real customers.

## Run

```powershell
cd baoxian-agent
uv venv .venv --python 'C:\Users\morty\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
uv pip install --python .venv\Scripts\python.exe -e ".[test]"
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

Open http://127.0.0.1:8000/docs. The SQLite database is created on first startup and 10 fictional claims are inserted only if absent. The defaults can be overridden with the variables in `.env.example` (environment variables are read directly; the file is a template, not auto-loaded).

The service exposes an OpenAI-compatible adapter. The configured model is `baoxian-agent`, and the adapter endpoints are `/v1/models` and `/v1/chat/completions`.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/v1/claims
Invoke-RestMethod -Method Post http://127.0.0.1:8000/v1/claims/CL001/decide
Invoke-RestMethod http://127.0.0.1:8000/v1/claims/CL001/decisions
```

`POST /v1/claims` accepts a structured `Claim` (see `/docs`) and returns 409 for a repeated ID; the seed cases are not the only supported inputs. The current MVP accepts text descriptions and document-presence metadata, not actual PDF/image uploads or OCR.

For a new fictional claim, create it first, then request an assessment and inspect its audit trail:

```powershell
$claim = @{claim_id='CL011';policy_number='AUTO-BASIC';incident_type='collision';description='Door damaged in a collision.';estimated_loss=950;documents=@('statement','repair_estimate');required_documents=@('statement','repair_estimate');damage_consistent=$true;risk_flags=@();customer_id='CUSTOMER-011'} | ConvertTo-Json
Invoke-RestMethod -Method Post http://127.0.0.1:8000/v1/claims -ContentType 'application/json' -Body $claim
Invoke-RestMethod -Method Post http://127.0.0.1:8000/v1/claims/CL011/decide
Invoke-RestMethod http://127.0.0.1:8000/v1/claims/CL011/decisions
```

In `ollama` mode, install/pull the configured model first and set `INSURANCE_AGENT_MODE=ollama`. Failed model calls fail closed (HTTP 503), without recording a fictitious decision. No external provider fallback exists. Ollama was not available in the development environment, so real-model behavior has not been end-to-end validated.

## Decision gate

Missing required claim materials -> `NEED_MORE_INFO`; unknown policy coverage or missing verifiable policy evidence -> `HUMAN_REVIEW`; high risk or review red flags -> `HUMAN_REVIEW`; a cited exclusion -> `DENIED`; invalid claim -> `HUMAN_REVIEW`; otherwise cited coverage with low/medium risk -> `APPROVED`. No route sends money or changes a claim's legal status. Every completed assessment has a trace ID and SQLite audit record. Mock results are rule-driven from fictional seed data, not a measure of model accuracy.

Run regression tests with `python -m pytest`.
