$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ApiPort = 8002
$WebUiPort = 8080
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$WebUiRoot = Join-Path (Split-Path -Parent $ProjectRoot) "open-webui"
$WebUiPython = Join-Path $WebUiRoot ".venv\Scripts\python.exe"
$WebUiBackend = Join-Path $WebUiRoot "backend"
$LogDir = Join-Path $ProjectRoot "logs"
function Test-Port($Port) { return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) }
function Wait-Http($Url, $Attempts = 30) { for ($i=0; $i -lt $Attempts; $i++) { try { $r=Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true } } catch { Start-Sleep -Seconds 1 } }; return $false }
if (-not (Test-Path $Python)) { throw "Insurance Agent .venv is missing. Run uv venv .venv and install dependencies first." }
if (-not (Test-Path $WebUiPython)) { throw "Open WebUI was not found. Put it at $WebUiRoot and create its .venv first." }
if (-not (Test-Path $WebUiBackend)) { throw "Open WebUI backend directory is missing: $WebUiBackend" }
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
if (-not (Test-Port $ApiPort)) { Start-Process -FilePath $Python -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port",$ApiPort -WorkingDirectory $ProjectRoot -RedirectStandardOutput (Join-Path $LogDir "api.out.log") -RedirectStandardError (Join-Path $LogDir "api.err.log") }
if (-not (Wait-Http "http://127.0.0.1:$ApiPort/health")) { throw "Insurance API failed to start. See logs/api.err.log." }
if (-not (Test-Port $WebUiPort)) {
    $env:OPENAI_API_BASE_URLS = "http://127.0.0.1:$ApiPort/v1"
    $env:OPENAI_API_KEYS = "local-insurance-agent"
    $env:ENABLE_OLLAMA_API = "false"
    $env:WEBUI_AUTH = "false"
    $env:WEBUI_SECRET_KEY = "baoxian-agent-dev-secret-32bytes"
    $env:OAUTH_SESSION_TOKEN_ENCRYPTION_KEY = "baoxian-agent-oauth-dev-key-32bytes"
    Start-Process -FilePath $WebUiPython -ArgumentList "-m","uvicorn","open_webui.main:app","--host","127.0.0.1","--port",$WebUiPort -WorkingDirectory $WebUiBackend -RedirectStandardOutput (Join-Path $LogDir "openwebui.out.log") -RedirectStandardError (Join-Path $LogDir "openwebui.err.log")
}
if (-not (Wait-Http "http://127.0.0.1:$WebUiPort/")) { throw "Open WebUI failed to start. See logs/openwebui.err.log." }
Start-Process "http://127.0.0.1:$WebUiPort"
Write-Host "Open WebUI started at http://127.0.0.1:$WebUiPort"
