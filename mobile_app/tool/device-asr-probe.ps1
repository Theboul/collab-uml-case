<#
  CU14 - FASE 0: sondeo de reconocimiento de voz OFFLINE (espanol) en el TELEFONO REAL.

  1. Concede/revoca el permiso de microfono para que la peticion sea real, y pulsa "permitir" en el dialogo
     del sistema (uiautomator) para no depender de una persona.
  2. Corre integration_test/cu14_asr_probe_test.dart en el telefono.
  3. Lee las marcas MARK:* del test: activa el modo avion con adb y, cuando el reconocedor esta escuchando,
     reproduce la frase de prueba con la voz TTS en espanol del PC (mejor esfuerzo: depende de que el
     telefono este cerca de los altavoces). Con -NoSpeak no reproduce nada: hay que hablarle al telefono.
  4. Al terminar deja el modo avion DESACTIVADO y guarda logcat en build\asr-evidence.

  Uso:  powershell -File mobile_app\tool\device-asr-probe.ps1 [-Locale es_ES] [-OnDevice $true] [-NoSpeak] [-SkipListen]
#>
param(
  [string]$Locale = 'es_ES',
  [bool]$OnDevice = $true,
  [string]$Phrase = 'crear producto camisa con precio veinte',
  [switch]$NoSpeak,
  [switch]$SkipListen,
  [switch]$NoAirplane,   # CONTROL: mismo sondeo con red (no toca el modo avion)
  [switch]$PreferOnline, # CONTROL: sin EXTRA_PREFER_OFFLINE (reconocimiento normal del sistema)
  [int]$ListenSeconds = 30,
  [string]$NativeTags = '',      # barrido de la escucha nativa: 'es-ES,es-US,en-US'
  [int]$NativeSeconds = 0,       # cuanto espera audio un idioma aceptado (0 = por defecto del test)
  [string]$OutDir = "$PSScriptRoot\..\build\asr-evidence"
)

$ErrorActionPreference = 'Continue'
if ($PreferOnline) { $OnDevice = $false }
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
function Say($m) { $line = "[$(Stamp)] $m"; Write-Host $line; Add-Content $orq $line }
function Airplane([bool]$on) {
  & $adb shell cmd connectivity airplane-mode $(if ($on) { 'enable' } else { 'disable' }) | Out-Null
  Start-Sleep -Milliseconds 500
  Say ("modo avion => " + (& $adb shell settings get global airplane_mode_on) + "  (1 = activado)")
}
function Shot($name) { & cmd.exe /c "`"$adb`" exec-out screencap -p > `"$OutDir\$name.png`""; Say "captura del telefono: $name.png" }

# Pulsa "permitir" en el dialogo de permisos del sistema (busca el boton en el arbol de UI).
function Tap-PermissionAllow {
  foreach ($i in 1..8) {
    Start-Sleep -Seconds 2
    & $adb shell uiautomator dump /sdcard/asr-ui.xml | Out-Null
    & $adb pull /sdcard/asr-ui.xml "$OutDir\asr-ui.xml" 2>&1 | Out-Null
    if (-not (Test-Path "$OutDir\asr-ui.xml")) { continue }
    [xml]$x = Get-Content "$OutDir\asr-ui.xml" -Raw
    $nodes = @($x.SelectNodes("//node[contains(@resource-id,'permission_allow')]"))
    $btn = $nodes | Where-Object { $_.'resource-id' -match 'foreground_only' } | Select-Object -First 1
    if (-not $btn) { $btn = $nodes | Select-Object -First 1 }
    if (-not $btn) { $btn = @($x.SelectNodes("//node")) | Where-Object { $_.text -match '(?i)mientras|while using|solo esta vez|only this time|permitir|allow' } | Select-Object -First 1 }
    if ($btn -and $btn.bounds -match '\[(\d+),(\d+)\]\[(\d+),(\d+)\]') {
      $cx = [int](([int]$Matches[1] + [int]$Matches[3]) / 2); $cy = [int](([int]$Matches[2] + [int]$Matches[4]) / 2)
      Shot '1-dialogo-permiso-microfono'
      & $adb shell input tap $cx $cy | Out-Null
      Say "permiso: pulsado '$($btn.text)' ($($btn.'resource-id')) en ($cx,$cy)"
      return $true
    }
  }
  Say 'permiso: NO se encontro el boton de permitir; se concede con pm grant como plan B'
  & $adb shell pm grant $pkg android.permission.RECORD_AUDIO | Out-Null
  return $false
}

function Speak-Spanish($text) {
  Add-Type -AssemblyName System.Speech
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'es*' } | Select-Object -First 1
  if (-not $v) { Say 'TTS: no hay voz en espanol en el PC'; return }
  $s.SelectVoice($v.VoiceInfo.Name); $s.Volume = 100; $s.Rate = -2
  Say "TTS del PC ($($v.VoiceInfo.Name)) dice: '$text'"
  $s.Speak($text)
}

$device = ((& $adb devices) -split "`n" | Where-Object { $_ -match "\sdevice$" } | Select-Object -First 1) -replace "\s+device.*", ''
if (-not $device) { Say 'NO HAY TELEFONO AUTORIZADO (adb devices)'; exit 2 }
Say "telefono: $device  locale=$Locale  onDevice=$OnDevice  listen=${ListenSeconds}s"

& $adb shell pm revoke $pkg android.permission.RECORD_AUDIO 2>&1 | Out-Null
Airplane $false
& $adb shell input keyevent KEYCODE_WAKEUP | Out-Null
& $adb shell wm dismiss-keyguard | Out-Null
& $adb logcat -c | Out-Null

$flags = @("--dart-define=ASR_LOCALE=$Locale", "--dart-define=ASR_ON_DEVICE=$($OnDevice.ToString().ToLower())", "--dart-define=ASR_LISTEN_SECONDS=$ListenSeconds")
if ($SkipListen) { $flags += '--dart-define=ASR_SKIP_LISTEN=true' }
if ($NoAirplane) { $flags += '--dart-define=ASR_AIRPLANE=false' }
if ($NativeTags) { $flags += "--dart-define=ASR_NATIVE_TAGS=$NativeTags" }
if ($NativeSeconds -gt 0) { $flags += "--dart-define=ASR_NATIVE_SECONDS=$NativeSeconds" }
$proc = Start-Process -FilePath cmd.exe -WindowStyle Hidden -PassThru -ArgumentList '/c', "cd /d `"$app`" && flutter test integration_test\cu14_asr_probe_test.dart -d $device --no-pub $($flags -join ' ') > `"$log`" 2>&1"
Say 'flutter test lanzado en el telefono (la primera vez compila e instala la app)...'

$seen = @{}
$deadline = (Get-Date).AddMinutes(20)
try {
  while (-not $proc.HasExited -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 300
    $text = if (Test-Path $log) { Get-Content $log -Raw -ErrorAction SilentlyContinue } else { '' }
    if (-not $text) { continue }
    if ($text -match 'MARK:PERMISSION_REQUEST' -and -not $seen.perm) { $seen.perm = $true; Say 'MARCA: PERMISSION_REQUEST'; [void](Tap-PermissionAllow) }
    if ($text -match 'MARK:AIRPLANE_ON' -and -not $seen.on) { $seen.on = $true; Say 'MARCA: AIRPLANE_ON'; Airplane $true }
    if ($text -match 'MARK:SPEAK_NOW' -and -not $seen.speak) {
      $seen.speak = $true; Say 'MARCA: SPEAK_NOW (el reconocedor esta escuchando)'
      if ($NoSpeak) { Say '>>> HABLE AHORA al telefono (modo -NoSpeak) <<<' }
      else {
        # Sin retrasos: la sesion de escucha puede cerrarse enseguida (se mide cuanto dura).
        Speak-Spanish $Phrase
        $t2 = Get-Content $log -Raw -ErrorAction SilentlyContinue
        if ($t2 -notmatch 'ASR:RESULT' -and $t2 -notmatch 'status=done|ASR:STATUS \S+ done' -and $t2 -notmatch 'MARK:DONE') {
          Start-Sleep -Seconds 3; Speak-Spanish $Phrase
        }
      }
      Shot '2-escuchando'
    }
    if ($text -match 'MARK:DONE') { Say 'MARCA: DONE'; break }
  }
  if (-not $proc.HasExited -and (Get-Date) -ge $deadline) { Say 'TIEMPO AGOTADO: se detiene la prueba'; Stop-Process -Id $proc.Id -Force }
} finally {
  Airplane $false   # pase lo que pase, el telefono queda con el modo avion desactivado
  & cmd.exe /c "`"$adb`" logcat -d > `"$OutDir\logcat-full.txt`" 2>&1"
}

Start-Sleep 3
Get-Content "$OutDir\logcat-full.txt" -ErrorAction SilentlyContinue |
  Where-Object { $_ -match 'speech_to_text|SpeechToText|SpeechRecognizer|RecognitionService|GoogleTTSRecog|onDevice|on-device|AsrProbe|tts\.googletts|SODA|offline' } |
  Set-Content "$OutDir\logcat-asr.txt"
Say '--- salida de flutter test (lineas relevantes) ---'
Get-Content $log | Where-Object { $_ -match 'ASR:|MARK:|All tests passed|Some tests failed|\[E\]|Expected|Actual|Error' } | ForEach-Object { Say $_ }
$ok = (Get-Content $log -Raw) -match 'All tests passed'
Say ("RESULTADO DEL SONDEO (el test ejecuto hasta el final): " + $(if ($ok) { 'SI' } else { 'NO' }))
exit $(if ($ok) { 0 } else { 1 })
