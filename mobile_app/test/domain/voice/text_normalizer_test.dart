import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/domain/voice/text_normalizer.dart';

/// CU14 · normalización de texto: minúsculas, sin tildes, espacios colapsados. Función pura.
void main() {
  group('normalizeText', () {
    const table = <(String, String, String)>[
      // (caso, entrada, esperado)
      ('minúsculas', 'CREAR Producto', 'crear producto'),
      (
        'tildes',
        'Crear producto camisón más económico',
        'crear producto camison mas economico',
      ),
      ('todas las vocales con tilde', 'áéíóú ÁÉÍÓÚ', 'aeiou aeiou'),
      ('diéresis', 'pingüino', 'pinguino'),
      (
        'espacios repetidos',
        'crear    producto   camisa',
        'crear producto camisa',
      ),
      (
        'tabuladores y saltos de línea',
        'crear\tproducto\n camisa',
        'crear producto camisa',
      ),
      ('espacios en los extremos', '   crear producto  ', 'crear producto'),
      (
        'todo a la vez',
        '  ÁGREGA   un  Producto\tLLAMADO  Camisón ',
        'agrega un producto llamado camison',
      ),
      ('la ñ es una letra, no una tilde', 'Añadir NIÑO', 'añadir niño'),
      (
        'los números y separadores decimales se conservan',
        'precio 19,90 o 19.90',
        'precio 19,90 o 19.90',
      ),
      ('las fechas se conservan', 'Fecha 2026-09-21', 'fecha 2026-09-21'),
      ('cadena vacía', '', ''),
      ('solo espacios', '   \t\n ', ''),
    ];

    for (final (name, input, expected) in table) {
      test(name, () => expect(normalizeText(input), expected));
    }

    test('es idempotente: normalizar dos veces da lo mismo', () {
      for (final (_, input, _) in table) {
        final once = normalizeText(input);
        expect(normalizeText(once), once);
      }
    });
  });
}
