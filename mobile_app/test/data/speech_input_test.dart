import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/data/voice/speech_input.dart';
import 'package:gestion_movil/domain/voice/voice_command.dart';

/// CU14 · qué excepción de la ficha corresponde a cada error del reconocedor de Android.
void main() {
  const table = <(String, VoiceErrorKind, String)>[
    // (error de speech_to_text, excepción, fragmento del motivo)
    ('error_no_match', VoiceErrorKind.vozNoReconocida, 'No se oyó'),
    ('error_speech_timeout', VoiceErrorKind.vozNoReconocida, 'No se oyó'),
    (
      'error_permission',
      VoiceErrorKind.recursosInsuficientes,
      'permiso de micrófono',
    ),
    (
      'error_network',
      VoiceErrorKind.recursosInsuficientes,
      'necesita conexión',
    ),
    (
      'error_network_timeout',
      VoiceErrorKind.recursosInsuficientes,
      'necesita conexión',
    ),
    ('error_server', VoiceErrorKind.recursosInsuficientes, 'necesita conexión'),
    (
      'error_language_not_supported',
      VoiceErrorKind.recursosInsuficientes,
      'español no está disponible',
    ),
    (
      'error_language_unavailable',
      VoiceErrorKind.recursosInsuficientes,
      'español no está disponible',
    ),
    ('error_busy', VoiceErrorKind.recursosInsuficientes, 'ocupado'),
    ('error_audio_error', VoiceErrorKind.recursosInsuficientes, 'micrófono'),
    ('error_client', VoiceErrorKind.recursosInsuficientes, 'micrófono'),
    (
      'algo_desconocido',
      VoiceErrorKind.recursosInsuficientes,
      'algo_desconocido',
    ),
  ];

  for (final (error, kind, reason) in table) {
    test('$error → ${kind.name}', () {
      final failure = speechErrorToFailure(error);

      expect(failure.kind, kind);
      expect(failure.detail, contains(reason));
    });
  }
}
