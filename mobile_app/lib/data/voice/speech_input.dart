import 'dart:async';
import 'dart:ui' show Locale, PlatformDispatcher;

import 'package:speech_to_text/speech_to_text.dart';

import '../../domain/voice/voice_command.dart';

/// Resultado de escuchar una frase.
sealed class SpeechCapture {
  const SpeechCapture();
}

final class SpeechHeard extends SpeechCapture {
  const SpeechHeard(this.transcript);

  final String transcript;
}

/// No se obtuvo transcripción: [failure] es `vozNoReconocida` o `recursosInsuficientes`.
final class SpeechFailed extends SpeechCapture {
  const SpeechFailed(this.failure);

  final VoiceFailure failure;
}

/// Entrada de voz: dicta una frase y devuelve el texto. Es un puerto para poder sustituirlo en
/// tests; en la app es [SpeechToTextInput]. Nunca lanza: todo fallo llega como [SpeechFailed].
abstract interface class SpeechInput {
  /// [onReady] se llama cuando el micrófono YA está abierto y se puede empezar a hablar (abrirlo
  /// tarda un momento: quien hable antes pierde las primeras palabras).
  ///
  /// [localeId] fuerza el idioma de reconocimiento (`es_BO`); `null` = el del dispositivo.
  Future<SpeechCapture> listen({void Function()? onReady, String? localeId});

  Future<void> cancel();
}

/// Traduce un error del reconocedor (nombres de `speech_to_text`) a una excepción de la ficha.
///
/// - No se oyó nada / no se entendió → [VoiceErrorKind.vozNoReconocida].
/// - Todo lo que impide reconocer (permiso, red, idioma no disponible, servicio ocupado o
///   inexistente) → [VoiceErrorKind.recursosInsuficientes], con el motivo.
VoiceFailure speechErrorToFailure(String errorMsg) {
  switch (errorMsg) {
    case 'error_no_match':
    case 'error_speech_timeout':
      return const VoiceFailure(
        VoiceErrorKind.vozNoReconocida,
        detail: 'No se oyó ninguna frase.',
      );
    case 'error_permission':
      return const VoiceFailure(
        VoiceErrorKind.recursosInsuficientes,
        detail: 'Falta el permiso de micrófono. Concédelo en los ajustes de la app.',
      );
    case 'error_network':
    case 'error_network_timeout':
    case 'error_server':
    case 'error_server_disconnected':
      return const VoiceFailure(
        VoiceErrorKind.recursosInsuficientes,
        detail: 'El servicio de voz no pudo conectarse. El reconocimiento necesita conexión.',
      );
    case 'error_language_not_supported':
    case 'error_language_unavailable':
      return const VoiceFailure(
        VoiceErrorKind.recursosInsuficientes,
        detail: 'El español no está disponible en el reconocedor de este dispositivo.',
      );
    case 'error_busy':
    case 'error_too_many_requests':
      return const VoiceFailure(
        VoiceErrorKind.recursosInsuficientes,
        detail: 'El reconocedor de voz está ocupado. Espera un momento e inténtalo de nuevo.',
      );
    case 'error_audio_error':
    case 'error_client':
      return const VoiceFailure(
        VoiceErrorKind.recursosInsuficientes,
        detail: 'No se pudo usar el micrófono. Cierra otras apps que lo usen e inténtalo de nuevo.',
      );
    default:
      return VoiceFailure(
        VoiceErrorKind.recursosInsuficientes,
        detail: 'El reconocedor de voz falló ($errorMsg).',
      );
  }
}

/// Idioma de reconocimiento por defecto: el del dispositivo si es español (`es_BO`), y si no el
/// español latinoamericano (`es_419`). Un acento distinto del que espera el reconocedor (`es_ES` con
/// una voz boliviana) lo entiende peor, así que no se fija uno por defecto.
String spanishLocaleFor(Locale device) {
  if (device.languageCode != 'es') return 'es_419';
  final country = device.countryCode;
  return (country == null || country.isEmpty) ? 'es_419' : 'es_$country';
}

/// [SpeechInput] real, con el plugin `speech_to_text`.
///
/// Usa `onDevice: false`: en el dispositivo de pruebas el reconocimiento OFFLINE en español no está
/// disponible (ver `docs/decisions.md`), así que la voz **requiere red**; quien la llama comprueba
/// la conectividad antes de escuchar.
class SpeechToTextInput implements SpeechInput {
  SpeechToTextInput({
    this._speech,
    this.localeId = const String.fromEnvironment('VOICE_LOCALE'),
    this.listenFor = const Duration(seconds: 20),
    this.pauseFor = const Duration(seconds: 4),
    this.finalGrace = const Duration(seconds: 3),
  });

  /// Idioma forzado; vacío = el del dispositivo ([spanishLocaleFor]). Se puede fijar al compilar con
  /// `--dart-define=VOICE_LOCALE=es_419` (lo usa `tool/device-voice-test.ps1 -VoiceLocale`).
  final String localeId;
  final Duration listenFor;
  final Duration pauseFor;

  /// El resultado FINAL puede llegar tras el estado `done` (se observó ~2 s de retraso): se espera
  /// este margen antes de darlo por perdido.
  final Duration finalGrace;

  SpeechToText? _speech;
  SpeechToText get _plugin => _speech ??= SpeechToText();

  Completer<SpeechCapture>? _current;
  void Function()? _onReady;
  String _lastWords = '';
  Timer? _graceTimer;

  Future<bool> _initialize() => _plugin
      .initialize(onStatus: _onStatus, onError: (e) => _onError(e.errorMsg))
      .timeout(const Duration(seconds: 60), onTimeout: () => false);

  @override
  Future<SpeechCapture> listen({
    void Function()? onReady,
    String? localeId,
  }) async {
    await cancel();
    if (!await _initialize()) {
      final denied = !await _plugin.hasPermission;
      return SpeechFailed(
        VoiceFailure(
          VoiceErrorKind.recursosInsuficientes,
          detail: denied
              ? 'Falta el permiso de micrófono. Concédelo en los ajustes de la app.'
              : 'Este dispositivo no tiene un servicio de reconocimiento de voz disponible.',
        ),
      );
    }
    final completer = _current = Completer<SpeechCapture>();
    _onReady = onReady;
    _lastWords = '';
    try {
      await _plugin.listen(
        onResult: (result) {
          if (result.recognizedWords.isNotEmpty) {
            _lastWords = result.recognizedWords;
          }
          if (result.finalResult) _finish(_heardOrNothing());
        },
        listenOptions: SpeechListenOptions(
          onDevice: false,
          partialResults: false,
          cancelOnError: true,
          localeId: localeId ?? _defaultLocale(),
          listenFor: listenFor,
          pauseFor: pauseFor,
        ),
      );
    } on Object catch (e) {
      _finish(SpeechFailed(speechErrorToFailure('error_client ($e)')));
    }
    return completer.future.timeout(
      listenFor + finalGrace + const Duration(seconds: 5),
      onTimeout: () {
        unawaited(_plugin.stop());
        return _heardOrNothing();
      },
    );
  }

  String _defaultLocale() => localeId.isNotEmpty
      ? localeId
      : spanishLocaleFor(PlatformDispatcher.instance.locale);

  SpeechCapture _heardOrNothing() => _lastWords.trim().isEmpty
      ? SpeechFailed(speechErrorToFailure('error_no_match'))
      : SpeechHeard(_lastWords.trim());

  void _onStatus(String status) {
    if (status == 'listening') {
      _onReady?.call(); // el micrófono está abierto
      _onReady = null;
    }
    if (status != 'done') return;
    // El resultado final puede tardar en llegar tras `done`: se espera un margen.
    _graceTimer?.cancel();
    _graceTimer = Timer(finalGrace, () => _finish(_heardOrNothing()));
  }

  void _onError(String errorMsg) =>
      _finish(SpeechFailed(speechErrorToFailure(errorMsg)));

  void _finish(SpeechCapture capture) {
    _graceTimer?.cancel();
    final completer = _current;
    if (completer != null && !completer.isCompleted) {
      completer.complete(capture);
    }
  }

  @override
  Future<void> cancel() async {
    _finish(SpeechFailed(speechErrorToFailure('error_no_match')));
    _current = null;
    if (_speech != null && _speech!.isListening) await _speech!.cancel();
  }
}
