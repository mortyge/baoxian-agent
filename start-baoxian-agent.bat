@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-baoxian-agent.ps1"
if errorlevel 1 (
  echo.
  echo 启动失败，请查看上面的错误信息。
  pause
)
endlocal
