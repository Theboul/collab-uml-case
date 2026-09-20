<#
  Prueba de CU13 en el TELEFONO REAL con modo avion de verdad.

  1. Levanta el backend H2 en el PC si no esta arriba y abre el tunel USB (adb reverse).
  2. Corre integration_test/cu13_offline_test.dart en el telefono.
  3. Lee las marcas MARK:* que imprime el test y, justo entonces, activa / desactiva el modo avion
     con `adb shell cmd connectivity airplane-mode`, y saca capturas de pantalla del telefono.
  4. Al terminar (o si falla) deja el modo avion DESACTIVADO.

  Uso:  powershell -File mobile_app\tool\device-offline-test.ps1 [-OutDir <carpeta>]
#>
param([string]$OutDir = "$PSScriptRoot\..\build\device-evidence")

$ErrorActionPreference = 'Continue'
$dev = 'C:\Users\alex\dev'
$adb = "$dev\android-sdk\platform-tools\adb.exe"
$env:JAVA_HOME = 'C:\Program Files\Java\jdk-21.0.12.1'
$env:ANDROID_HOME = "$dev\android-sdk"
$env:FLUTTER_SUPPRESS_ANALYTICS = 'true'
$env:PATH = "$dev\flutter\bin;$dev\android-sdk\platform-tools;$env:JAVA_HOME\bin;$env:PATH"
$app = (Resolve-Path "$PSScriptRoot\..").Path
New-Item -ItemType Directory -Force $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
$log = Join-Path $OutDir 'flutter-test.log'
Remove-Item $log -ErrorAction SilentlyContinue

function Stamp { (Get-Date).ToString('HH:mm:ss.fff') }
function Say($m) { $line = "[$(Stamp)] $m"; Write-Host $line; Add-Content (Join-Path $OutDir 'orquestador.log') $line }
function Airplane([bool]$on) {
  & $adb shell cmd connectivity airplane-mode $(if ($on) { 'enable' } else { 'disable' }) | Out-Null
  Start-Sleep -Milliseconds 500
  Say ("modo avion => " + (& $adb shell settings get global airplane_mode_on) + "  (1 = activado)")
}
function Shot($name) { & cmd.exe /c "`"$adb`" exec-out screencap -p > `"$OutDir\$name.png`""; Say "captura del telefono: $name.png" }

Remove-Item (Join-Path $OutDir 'orquestador.log') -ErrorAction SilentlyContinue
$device = ((& $adb devices) -split "`n" | Where-Object { $_ -match "\sdevice$" } | Select-Object -First 1) -replace "\s+device.*", ''
if (-not $device) { Say 'NO HAY TELEFONO CONECTADO (adb devices vacio)'; exit 2 }
Say "telefono: $device"

# Backend en el PC
$startedBackend = $false
if (-not (Get-NetTCPConnection -LocalPort 9000 -State Listen -ErrorAction SilentlyContinue)) {
  Say 'levantando backend H2 (puerto 9000)...'
  Start-Process cmd.exe -ArgumentList '/c', "`"$app\backend_cu10\run-h2.cmd`"" -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $OutDir 'backend.log') -RedirectStandardError (Join-Path $OutDir 'backend.err.log')
  $startedBackend = $true
  foreach ($i in 1..60) { Start-Sleep 2; if (Get-NetTCPConnection -LocalPort 9000 -State Listen -ErrorAction SilentlyContinue) { break } }
}
Say ("backend escuchando en 9000: " + [bool](Get-NetTCPConnection -LocalPort 9000 -State Listen -ErrorAction SilentlyContinue))

& $adb reverse tcp:9000 tcp:9000 | Out-Null
Say 'adb reverse tcp:9000 -> PC:9000 (tunel USB: sigue vivo aunque el modo avion apague WiFi y datos)'
Airplane $false
& $adb shell input keyevent KEYCODE_WAKEUP | Out-Null
& $adb shell wm dismiss-keyguard | Out-Null
& $adb logcat -c | Out-Null

$proc = Start-Process -FilePath cmd.exe -ArgumentList '/c', "cd /d `"$app`" && flutter test integration_test\cu13_offline_test.dart -d $device --no-pub > `"$log`" 2>&1" -PassThru -WindowStyle Hidden
Say 'flutter test lanzado en el telefono (la primera vez compila y instala la app)...'

$seen = @{}
$deadline = (Get-Date).AddMinutes(20)
try {
  while (-not $proc.HasExited -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 300
    $text = if (Test-Path $log) { Get-Content $log -Raw -ErrorAction SilentlyContinue } else { '' }
    if (-not $text) { continue }
    if ($text -match 'MARK:AIRPLANE_ON' -and -not $seen.on) { $seen.on = $true; Say 'MARCA: AIRPLANE_ON'; Airplane $true }
    if ($text -match 'MARK:SHOT_OFFLINE' -and -not $seen.shotOff) { $seen.shotOff = $true; Say 'MARCA: SHOT_OFFLINE'; Shot '2-sin-conexion-operacion-pendiente' }
    if ($text -match 'MARK:AIRPLANE_OFF' -and -not $seen.off) { $seen.off = $true; Say 'MARCA: AIRPLANE_OFF'; Airplane $false }
    if ($text -match 'MARK:SHOT_SYNCED' -and -not $seen.shotOn) { $seen.shotOn = $true; Say 'MARCA: SHOT_SYNCED'; Shot '3-conexion-recuperada-sincronizado' }
  }
  if (-not $proc.HasExited) { Say 'TIEMPO AGOTADO: se detiene la prueba'; Stop-Process -Id $proc.Id -Force }
} finally {
  Airplane $false   # pase lo que pase, el telefono queda con el modo avion desactivado
  & $adb logcat -d -s flutter:I 2>$null | Set-Content (Join-Path $OutDir 'logcat-flutter.log')
}

Start-Sleep 2
Say '--- salida de flutter test (lineas relevantes) ---'
Get-Content $log | Where-Object { $_ -match 'EVIDENCIA|MARK:|All tests passed|Some tests failed|\[E\]|Expected|Actual|Tiempo agotado|Error' } | ForEach-Object { Say $_ }
Say '--- log real del telefono (logcat, sync) ---'
Get-Content (Join-Path $OutDir 'logcat-flutter.log') | Where-Object { $_ -match 'sync' } | ForEach-Object { Say $_ }

if ($startedBackend) {
  Get-NetTCPConnection -LocalPort 9000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
  Say 'backend detenido'
}
$ok = (Get-Content $log -Raw) -match 'All tests passed'
Say ("RESULTADO: " + $(if ($ok) { 'OK' } else { 'FALLO' }))
exit $(if ($ok) { 0 } else { 1 })
