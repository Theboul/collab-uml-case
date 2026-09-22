import 'package:flutter/material.dart';

import '../../domain/voice/voice_command.dart';

/// Mensaje al usuario para una excepción de la ficha. Cada categoría tiene el suyo, y las que
/// dependen de lo que se entendió (`intencionAmbigua`, `datosFaltantes`) lo muestran: qué se
/// entendió, qué falta o entre qué se dudó. Nunca un "no entendí" genérico.
class VoiceMessage {
  const VoiceMessage(this.title, this.body, this.icon);

  final String title;
  final String body;
  final IconData icon;
}

const String voiceExamples =
    'Ejemplos: "crear producto camisa 20", "listar pedidos", '
    '"cambiar el precio del producto 3 a 25", "eliminar pedido 2".';

VoiceMessage voiceMessageFor(VoiceFailure f) {
  final understood = f.understood.isEmpty
      ? ''
      : 'Entendí: ${f.understood.join(' · ')}. ';
  switch (f.kind) {
    case VoiceErrorKind.vozNoReconocida:
      return const VoiceMessage(
        'No se reconoció la voz',
        'No se captó ninguna frase. Habla más cerca del micrófono e inténtalo de nuevo, '
            'o escribe el comando en el campo de texto.',
        Icons.mic_off,
      );
    case VoiceErrorKind.intencionAmbigua:
      return VoiceMessage(
        'La intención es ambigua',
        '${understood}Dudo entre: ${f.candidates.join(' o ')}. '
            'Dilo con más claridad. $voiceExamples',
        Icons.help_outline,
      );
    case VoiceErrorKind.datosFaltantes:
      final missing = f.missing.isEmpty
          ? ''
          : 'Falta: ${f.missing.join(', ')}. ';
      final options = f.candidates.isEmpty
          ? ''
          : 'Campos válidos: ${f.candidates.join(', ')}. ';
      final detail = f.detail == null ? '' : '${f.detail} ';
      return VoiceMessage(
        'Faltan datos',
        '$understood$missing$options$detail'.trim(),
        Icons.edit_note,
      );
    case VoiceErrorKind.accionInexistente:
      return VoiceMessage(
        'Esa acción no existe',
        '${f.detail ?? 'No reconozco ninguna acción en lo que dijiste.'} '
            'Puedo crear, consultar (listar), actualizar y eliminar Productos y Pedidos. '
            '$voiceExamples',
        Icons.block,
      );
    case VoiceErrorKind.recursosInsuficientes:
      return VoiceMessage(
        'Reconocimiento de voz no disponible',
        f.detail ?? 'No hay recursos suficientes para reconocer la voz. Usa el campo de texto.',
        Icons.signal_wifi_off,
      );
  }
}
