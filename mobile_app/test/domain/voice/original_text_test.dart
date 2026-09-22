import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/domain/voice/original_text.dart';
import 'package:gestion_movil/domain/voice/text_normalizer.dart';
import 'package:gestion_movil/domain/voice/voice_command.dart';
import 'package:gestion_movil/domain/voice/voice_command_parser.dart';

/// El parser trabaja sobre texto normalizado (`camison`), pero lo que se guarda es lo que dijo el
/// usuario (`Camisón`): `restoreOriginalText` recupera mayúsculas y tildes en los campos de TEXTO.
VoiceCommand _parseAndRestore(String spoken) {
  final parsed = const VoiceCommandParser().parse(normalizeText(spoken));
  expect(parsed, isA<VoiceCommand>(), reason: spoken);
  return restoreOriginalText(parsed as VoiceCommand, spoken);
}

void main() {
  const table = <(String, String, Map<String, String>)>[
    // (caso, frase original, slots esperados)
    (
      'mayúsculas y tildes',
      'Crear producto Camisón Azul 20',
      {'nombre': 'Camisón Azul', 'precio': '20'},
    ),
    (
      'espacios de más, tabuladores y extremos',
      '  Crear   producto\t Camisa  de Algodón  con precio 20 ',
      {'nombre': 'Camisa de Algodón', 'precio': '20'},
    ),
    (
      'puntuación pegada al valor',
      'crear producto Camisa, precio 20.',
      {'nombre': 'Camisa', 'precio': '20'},
    ),
    (
      'la ñ',
      'Crear producto Piña colada 15',
      {'nombre': 'Piña colada', 'precio': '15'},
    ),
    (
      'campo de texto con números dentro',
      'Crear pedido con fecha 21 de Septiembre de 2026',
      {'fecha': '21 de Septiembre de 2026'},
    ),
    (
      'actualizar un campo de texto',
      'cambiar el nombre del producto 3 a Camisón Roja',
      {'nombre': 'Camisón Roja'},
    ),
    (
      'un campo numérico no se toca',
      'Crear producto Gorra con precio 19,90',
      {'nombre': 'Gorra', 'precio': '19,90'},
    ),
    (
      'número en palabras: sigue siendo el número',
      'Crear producto Gorra veinte',
      {'nombre': 'Gorra', 'precio': '20'},
    ),
    // No es un trozo contiguo del original: se queda como lo entendió el parser (normalizado)
    (
      'valor no contiguo (queda normalizado)',
      'crear producto Camisa 20 Azul',
      {'nombre': 'camisa azul', 'precio': '20'},
    ),
  ];

  for (final (name, spoken, expected) in table) {
    test(name, () => expect(_parseAndRestore(spoken).values, expected));
  }

  test('un comando sin campos de texto queda igual', () {
    final cmd = _parseAndRestore('Eliminar producto 3');
    expect(cmd.id, 3);
    expect(cmd.values, isEmpty);
  });

  test('conserva acción, entidad e id', () {
    final cmd = _parseAndRestore('Cambiar el nombre del producto 3 a Camisón');
    expect(cmd.intent, VoiceIntent.actualizar);
    expect(cmd.module.path, 'producto');
    expect(cmd.id, 3);
  });

  test('si el original no se corresponde con el texto normalizado, no inventa nada', () {
    final parsed = const VoiceCommandParser().parse(
      'crear producto camisa 20',
    ) as VoiceCommand;

    final restored = restoreOriginalText(
      parsed,
      'texto que no tiene nada que ver',
    );

    expect(restored.values, parsed.values);
  });
}
