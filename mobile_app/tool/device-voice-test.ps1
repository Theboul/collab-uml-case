<#
  CU14 en el TELEFONO REAL.

  -Mode offline  (por defecto)  Modo avion REAL + campo de texto: integration_test\cu14_voice_test.dart
  -Mode voice                   CON red + boton de voz real:       integration_test\cu14_voice_online_test.dart

  Lee las marcas MARK:* que imprime el test (log de flutter test) y, en cada una:
    AIRPLANE_ON / AIRPLANE_OFF  -> activa / desactiva el modo avion con adb
    SHOT_*                      -> captura de pantalla del telefono
    SPEAK_NOW (solo -Mode voice)-> el asistente esta escuchando: reproduce la frase con la voz TTS en
                                   espanol del PC (mejor esfuerzo: depende de que el telefono este cerca
                                   de los altavoces). Con -NoSpeak no reproduce nada: hay que HABLARLE.
  Al terminar deja el modo avion DESACTIVADO.

  Uso:  powershell -File mobile_app\tool\device-voice-test.ps1 [-Mode offline|voice] [-NoSpeak]
#>
param(
  [ValidateSet('offline', 'voice')][string]$Mode = 'offline',
  [switch]$NoSpeak,
  [string]$Phrase = 'crear producto camisa con precio veinte',
  [int]$SpeakDelayMs = 1200,
  [int]$TtsRate = 0,            # -10 (lenta) .. 10 (rapida). Lenta mete pausas y el reconocedor corta la frase
  [string]$OutDir = ''
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
if (-not $OutDir) { $OutDir = "$app\build\voice-evidence-$Mode" }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
$log = Join-Path $OutDir 'flutter-test.log'
$orq = Join-Path $OutDir 'orquestador.log'
Remove-Item $log, $orq -ErrorAction SilentlyContinue
$testFile = if ($Mode -eq 'offline') { 'integration_test\cu14_voice_test.dart' } else { 'integration_test\cu14_voice_online_test.dart' }

function Stamp { (Get-Date).ToString('HH:mm:ss.fff') }
function Say($m) { $line = "[$(Stamp)] $m"; Write-Host $line; Add-Content $orq $line }
function Airplane([bool]$on) {
  & $adb shell cmd connectivity airplane-mode $(if ($on) { 'enable' } else { 'disable' }) | Out-Null
  Start-Sleep -Milliseconds 500
  Say ("modo avion => " + (& $adb shell settings get global airplane_mode_on) + "  (1 = activado)")
}
function Shot($name) { & cmd.exe /c "`"$adb`" exec-out screencap -p > `"$OutDir\$name.png`""; Say "captura del telefono: $name.png" }
function Speak-Spanish($text) {
  Add-Type -AssemblyName System.Speech
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'es*' } | Select-Object -First 1
  if (-not $v) { Say 'TTS: no hay voz en espanol en el PC'; return }
  $s.SelectVoice($v.VoiceInfo.Name); $s.Volume = 100; $s.Rate = $TtsRate
  Say "TTS del PC ($($v.VoiceInfo.Name)) dice: '$text'"
  $s.Speak($text)
}
function Read-Marks($path) { if (Test-Path $path) { Get-Content $path -Raw -ErrorAction SilentlyContinue } else { '' } }

$device = ((& $adb devices) -split "`n" | Where-Object { $_ -match "\sdevice$" } | Select-Object -First 1) -replace "\s+device.*", ''
if (-not $device) { Say 'NO HAY TELEFONO AUTORIZADO (adb devices)'; exit 2 }
Say "telefono: $device  modo=$Mode  prueba=$testFile"

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
Airplane $false
& $adb shell input keyevent KEYCODE_WAKEUP | Out-Null
& $adb shell wm dismiss-keyguard | Out-Null
if ($Mode -eq 'voice') { & $adb shell pm grant $pkg android.permission.RECORD_AUDIO 2>&1 | Out-Null }
& $adb logcat -c | Out-Null

$proc = Start-Process -FilePath cmd.exe -WindowStyle Hidden -PassThru -ArgumentList '/c', "cd /d `"$app`" && flutter test $testFile -d $device --no-pub > `"$log`" 2>&1"
Say 'flutter test lanzado en el telefono (la primera vez compila e instala la app)...'

$done = @{}
$speaks = 0
$deadline = (Get-Date).AddMinutes(20)
try {
  while (-not $proc.HasExited -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 150
    $text = Read-Marks $log
    if (-not $text) { continue }
    if ($text -match 'MARK:AIRPLANE_ON' -and -not $done.on) { $done.on = $true; Say 'MARCA: AIRPLANE_ON'; Airplane $true }
    if ($text -match 'MARK:SHOT_CREATED' -and -not $done.s1) { $done.s1 = $true; Say 'MARCA: SHOT_CREATED'; Shot '2-creado-en-modo-avion' }
    if ($text -match 'MARK:SHOT_EXCEPTION' -and -not $done.s2) { $done.s2 = $true; Say 'MARCA: SHOT_EXCEPTION'; Shot '3-excepcion-en-modo-avion' }
    if ($text -match 'MARK:AIRPLANE_OFF' -and -not $done.off) { $done.off = $true; Say 'MARCA: AIRPLANE_OFF'; Airplane $false }
    if ($text -match 'MARK:SHOT_SYNCED' -and -not $done.s3) { $done.s3 = $true; Say 'MARCA: SHOT_SYNCED'; Shot '4-sincronizado-al-volver-la-red' }
    if ($text -match 'MARK:SHOT_CONFIRM' -and -not $done.s4) { $done.s4 = $true; Say 'MARCA: SHOT_CONFIRM'; Shot '2-voz-entendido-por-confirmar' }
    if ($text -match 'MARK:SHOT_EXECUTED' -and -not $done.s5) { $done.s5 = $true; Say 'MARCA: SHOT_EXECUTED'; Shot '3-voz-ejecutado' }
    $n = ([regex]::Matches($text, 'MARK:SPEAK_NOW')).Count
    while ($speaks -lt $n) {
      $speaks++
      $seen = ([regex]::Matches($text, 'MARK:SPEAK_NOW[^
]*'))[$speaks - 1].Value
      Say "MARCA: $seen (recibida en el PC a las $(Stamp); el asistente esta escuchando)"
      if ($NoSpeak) { Say ">>> HABLE AHORA al telefono: '$Phrase' <<<" }
      else { Start-Sleep -Milliseconds $SpeakDelayMs; Speak-Spanish $Phrase }
    }
    if ($text -match 'MARK:DONE') { Say 'MARCA: DONE'; break }
  }
  if (-not $proc.HasExited) { Start-Sleep -Seconds 8 }
  if (-not $proc.HasExited) { Say 'la prueba no termino sola: se detiene'; Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
} finally {
  Airplane $false   # pase lo que pase, el telefono queda con el modo avion desactivado
}

Start-Sleep 2
Say '--- salida de flutter test (lineas relevantes) ---'
Get-Content $log | Where-Object { $_ -match 'EVIDENCIA|MARK:|All tests passed|Some tests failed|\[E\]|Expected|Actual|Tiempo agotado|Error' } | ForEach-Object { Say $_ }
if ($startedBackend) {
  Get-NetTCPConnection -LocalPort 9000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
  Say 'backend detenido'
}
$ok = (Get-Content $log -Raw) -match 'All tests passed'
Say ("RESULTADO: " + $(if ($ok) { 'OK' } else { 'FALLO' }))
exit $(if ($ok) { 0 } else { 1 })
