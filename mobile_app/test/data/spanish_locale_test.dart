import 'dart:ui' show Locale;

import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/data/voice/speech_input.dart';

/// CU14 · el idioma de reconocimiento sale del dispositivo, no de un valor fijo.
void main() {
  const table = <(String, Locale, String)>[
    ('teléfono en español de Bolivia', Locale('es', 'BO'), 'es_BO'),
    ('teléfono en español de España', Locale('es', 'ES'), 'es_ES'),
    ('español sin país', Locale('es'), 'es_419'),
    ('país vacío', Locale('es', ''), 'es_419'),
    ('otro idioma → español latinoamericano', Locale('en', 'US'), 'es_419'),
  ];
  for (final (name, device, expected) in table) {
    test(name, () => expect(spanishLocaleFor(device), expected));
  }
}
