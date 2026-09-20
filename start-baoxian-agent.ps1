$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ApiPort = 8000
$FrontendPort = 3000
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$LogDir = Join-Path $ProjectRoot "logs"
function Test-Port($Port) { return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) }
if (-not (Test-Path $Python)) { Write-Host "未找到 Python 虚拟环境：$Python" -ForegroundColor Yellow; Write-Host "请先执行：uv venv .venv，然后安装项目依赖。" -ForegroundColor Yellow; exit 1 }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Write-Host "未找到 npm，请先安装 Node.js。" -ForegroundColor Red; exit 1 }
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
if (-not (Test-Port $ApiPort)) { Start-Process -FilePath $Python -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port",$ApiPort -WorkingDirectory $ProjectRoot -RedirectStandardOutput (Join-Path $LogDir "api.out.log") -RedirectStandardError (Join-Path $LogDir "api.err.log"); Write-Host "保险 API 已启动：http://127.0.0.1:$ApiPort" -ForegroundColor Green } else { Write-Host "保险 API 已在端口 $ApiPort 运行，跳过启动。" -ForegroundColor DarkYellow }
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) { Push-Location $FrontendDir; try { npm install } finally { Pop-Location } }
if (-not (Test-Port $FrontendPort)) { Start-Process -FilePath "npm.cmd" -ArgumentList "run","dev","--","--port",$FrontendPort -WorkingDirectory $FrontendDir -RedirectStandardOutput (Join-Path $LogDir "frontend.out.log") -RedirectStandardError (Join-Path $LogDir "frontend.err.log"); Write-Host "前端正在启动：http://127.0.0.1:$FrontendPort" -ForegroundColor Green } else { Write-Host "前端已在端口 $FrontendPort 运行，跳过启动。" -ForegroundColor DarkYellow }
Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:$FrontendPort"
Write-Host "Baoxian Agent 已启动。日志目录：$LogDir" -ForegroundColor Cyan
