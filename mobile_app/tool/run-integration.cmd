@echo off
rem Corre los tests de integracion REALES (test_backend/) contra el backend de CU10.
rem Si no hay nada escuchando en el puerto 9000, levanta el backend H2 (con datos semilla),
rem espera a que responda, corre los tests y lo detiene al terminar.
rem
rem Uso:  mobile_app\tool\run-integration.cmd
setlocal
call "%~dp0dev-env.cmd"
set "APP=%~dp0.."
set "STARTED="

powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 9000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
  echo Levantando el backend H2 en el puerto 9000...
  start "backend-cu10-h2" /min cmd /c "%APP%\backend_cu10\run-h2.cmd"
  set "STARTED=1"
  powershell -NoProfile -Command "$ok=$false; foreach($i in 1..60){ try { Invoke-WebRequest http://127.0.0.1:9000/api/producto -UseBasicParsing -TimeoutSec 2 | Out-Null; $ok=$true; break } catch { Start-Sleep 2 } }; if(-not $ok){ exit 1 }"
  if errorlevel 1 (
    echo El backend no arranco a tiempo.
    exit /b 1
  )
)

pushd "%APP%"
call flutter test test_backend --concurrency=1
set "RESULT=%ERRORLEVEL%"
popd

if defined STARTED (
  echo Deteniendo el backend...
  powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 9000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"
)
exit /b %RESULT%
