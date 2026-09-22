<#
  CU14 - diagnostico de voz HUMANA real (no sintetizada) en el TELEFONO REAL, CON red.

  A diferencia de device-voice-test.ps1, este script NUNCA reproduce audio por TTS: en cada marca
  MARK:SPEAK_NOW hay que decirle la frase al telefono EN VOZ ALTA, de verdad. Corre
  integration_test/cu14_voice_human_diagnostic_test.dart, que compara dos capas para la misma
  pregunta: el camino de produccion (VoiceAssistantScreen) y el listener nativo directo (AsrProbe.kt,
  con codigo de error real y nivel de audio onRmsChanged).

  7 intentos en total (2 por la UI real + 5 por el listener nativo). Al ver "HABLE AHORA" en la
  consola, decir la frase clara y de cerca al microfono del telefono.

  Uso:  powershell -File mobile_app\tool\device-voice-human-test.ps1
#>
param(
  [string]$OutDir = "$PSScriptRoot\..\build\voice-human-evidence"
)

$ErrorActionPreference = 'Continue'
$dev = 'C:\Users\alex\dev'
$adb = "$dev\android-sdk\platform-tools\adb.exe"
$env:JAVA_HOME = 'C:\Program Files\Java\jdk-21.0.12.1'
$env:ANDROID_HOME = "$dev\android-sdk"
$env:FLUTTER_SUPPRESS_ANALYTICS = 'true'
$env:PATH = "$dev\flutter\bin;$dev\android-sdk\platform-tools;$env:JAVA_HOME\bin;$env:PATH"
$pkg = 'com.example.gestion_movil'
$app = (Resolve-Path "$PSScriptRoot\..").Path
New-Item -ItemType Directory -Force $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
$log = Join-Path $OutDir 'flutter-test.log'
$orq = Join-Path $OutDir 'orquestador.log'
Remove-Item $log, $orq -ErrorAction SilentlyContinue

function Stamp { (Get-Date).ToString('HH:mm:ss.fff') }
# Add-Content falla si otro proceso tiene el archivo abierto para lectura al mismo tiempo (p. ej.
# un `tail -f` externo mirando el progreso en vivo): se abre el archivo con FileShare.ReadWrite.
function Say($m) {
  $line = "[$(Stamp)] $m"
  Write-Host $line
  $stream = [System.IO.File]::Open($orq, 'Append', 'Write', 'ReadWrite')
  $writer = New-Object System.IO.StreamWriter($stream, [System.Text.Encoding]::UTF8)
  try { $writer.WriteLine($line) } finally { $writer.Dispose(); $stream.Dispose() }
}
function Shot($name) { & cmd.exe /c "`"$adb`" exec-out screencap -p > `"$OutDir\$name.png`""; Say "captura del telefono: $name.png" }
function Read-Marks($path) { if (Test-Path $path) { Get-Content $path -Raw -ErrorAction SilentlyContinue } else { '' } }

$device = ((& $adb devices) -split "`n" | Where-Object { $_ -match "\sdevice$" } | Select-Object -First 1) -replace "\s+device.*", ''
if (-not $device) { Say 'NO HAY TELEFONO AUTORIZADO (adb devices)'; exit 2 }
Say "telefono: $device"

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
Say 'adb reverse tcp:9000 -> PC:9000 (tunel USB)'
& $adb shell cmd connectivity airplane-mode disable | Out-Null
Say 'modo avion desactivado (esta prueba es CON red)'
& $adb shell input keyevent KEYCODE_WAKEUP | Out-Null
& $adb shell wm dismiss-keyguard | Out-Null
& $adb shell pm grant $pkg android.permission.RECORD_AUDIO 2>&1 | Out-Null
Say 'permiso de microfono concedido'

$proc = Start-Process -FilePath cmd.exe -WindowStyle Hidden -PassThru -ArgumentList '/c', "cd /d `"$app`" && flutter test integration_test\cu14_voice_human_diagnostic_test.dart -d $device --no-pub > `"$log`" 2>&1"
Say 'flutter test lanzado en el telefono (la primera vez compila e instala la app)...'

$seenSpeak = 0
$shotUi = $false
$shotNative = $false
$deadline = (Get-Date).AddMinutes(20)
try {
  while (-not $proc.HasExited -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 150
    $text = Read-Marks $log
    if (-not $text) { continue }
    $marks = ([regex]::Matches($text, 'MARK:SPEAK_NOW (\S+)')) | ForEach-Object { $_.Groups[1].Value }
    while ($seenSpeak -lt $marks.Count) {
      $which = $marks[$seenSpeak]
      $seenSpeak++
      Say ''
      Say '>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>'
      Say ">>>  HABLE AHORA al telefono (intento $which):"
      Say '>>>  "crear producto camisa con precio veinte"'
      Say '>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>'
      Say ''
      if ($which -like 'ui*' -and -not $shotUi) { $shotUi = $true; Shot '1-ui-escuchando' }
      if ($which -like 'native*' -and -not $shotNative) { $shotNative = $true; Shot '2-nativo-escuchando' }
    }
    if ($text -match 'MARK:DONE') { Say 'MARCA: DONE'; break }
  }
  if (-not $proc.HasExited -and (Get-Date) -ge $deadline) { Say 'TIEMPO AGOTADO: se detiene la prueba'; Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
} finally {
  & $adb shell cmd connectivity airplane-mode disable | Out-Null  # esta prueba nunca activa el modo avion; se confirma que quede apagado
}

# Tras MARK:DONE el proceso todavia hace tearDown (desinstala la app, cierra Gradle/adb): esperar
# a que $proc termine de verdad, no solo a que aparezca la marca, antes de leer el resultado.
$exitDeadline = (Get-Date).AddSeconds(60)
while (-not $proc.HasExited -and (Get-Date) -lt $exitDeadline) { Start-Sleep -Milliseconds 300 }
Say '--- salida de flutter test (lineas relevantes) ---'
Get-Content $log | Where-Object { $_ -match 'DIAG:|MARK:|All tests passed|Some tests failed|\[E\]|Expected|Actual|Error' } | ForEach-Object { Say $_ }
if ($startedBackend) {
  Get-NetTCPConnection -LocalPort 9000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
  Say 'backend detenido'
}
$ok = (Get-Content $log -Raw) -match 'All tests passed'
Say ("RESULTADO (el test ejecuto hasta el final): " + $(if ($ok) { 'SI' } else { 'NO' }))
exit $(if ($ok) { 0 } else { 1 })
