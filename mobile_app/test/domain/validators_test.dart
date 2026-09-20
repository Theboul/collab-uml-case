import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/domain/field_spec.dart';
import 'package:gestion_movil/domain/validators.dart';

void main() {
  const text = FieldSpec(name: 'nombre', label: 'Nombre', type: FieldType.text);
  const integer = FieldSpec(
    name: 'cantidad',
    label: 'Cantidad',
    type: FieldType.integer,
  );
  const decimal = FieldSpec(
    name: 'precio',
    label: 'Precio',
    type: FieldType.decimal,
  );
  const reference = FieldSpec(
    name: 'pedido',
    label: 'Pedido',
    type: FieldType.reference,
    referenceTo: 'pedido',
  );

  group('texto', () {
    test('acepta un texto normal y recorta espacios', () {
      expect(FieldValidator.validate(text, '  Camisa  '), isNull);
      expect(FieldValidator.parse(text, '  Camisa  '), 'Camisa');
    });

    test('rechaza vacío, solo espacios y null', () {
      expect(FieldValidator.validate(text, ''), contains('obligatorio'));
      expect(FieldValidator.validate(text, '   '), contains('obligatorio'));
      expect(FieldValidator.validate(text, null), contains('obligatorio'));
    });

    test(
      'respeta el máximo de 255 caracteres (varchar por defecto de JPA)',
      () {
        expect(FieldValidator.validate(text, 'a' * 255), isNull);
        expect(FieldValidator.validate(text, 'a' * 256), contains('255'));
      },
    );
  });

  group('entero (Long)', () {
    test('acepta enteros, con signo, y los parsea', () {
      for (final ok in [
        '0',
        '7',
        '-12',
        '+5',
        '9223372036854775807',
        '-9223372036854775808',
      ]) {
        expect(FieldValidator.validate(integer, ok), isNull, reason: ok);
      }
      expect(FieldValidator.parse(integer, '+5'), 5);
      expect(FieldValidator.parse(integer, '-12'), -12);
    });

    test('rechaza decimales, letras, símbolos y vacío', () {
      for (final bad in [
        '1.5',
        '1,5',
        'abc',
        '12a',
        '1e3',
        '0x10',
        '--1',
        ' ',
        '',
      ]) {
        expect(
          FieldValidator.validate(integer, bad),
          isNotNull,
          reason: '"$bad"',
        );
      }
    });

    test('rechaza lo que no cabe en un Long', () {
      expect(
        FieldValidator.validate(integer, '9223372036854775808'),
        contains('rango'),
      );
      expect(
        FieldValidator.validate(integer, '-9223372036854775809'),
        contains('rango'),
      );
    });
  });

  group('decimal (Double)', () {
    test('acepta enteros y decimales con punto o coma', () {
      for (final ok in ['19', '19.9', '19,9', '0.5', '-3.25', '+7']) {
        expect(FieldValidator.validate(decimal, ok), isNull, reason: ok);
      }
      expect(FieldValidator.parse(decimal, '19,9'), 19.9);
      expect(FieldValidator.parse(decimal, '19'), 19.0);
    });

    test('rechaza el caso que el backend acepta en silencio: "abc"', () {
      expect(FieldValidator.validate(decimal, 'abc'), contains('número'));
    });

    test('rechaza NaN, Infinity, notación científica, miles, letras mezcladas y vacío', () {
      for (final bad in [
        'NaN',
        'Infinity',
        '-Infinity',
        '1e3',
        '1.000,50',
        '12abc',
        '.',
        '1.',
        '',
        ' ',
      ]) {
        expect(
          FieldValidator.validate(decimal, bad),
          isNotNull,
          reason: '"$bad"',
        );
      }
    });

    test('rechaza un número que desborda a infinito', () {
      expect(FieldValidator.validate(decimal, '9' * 400), contains('rango'));
    });
  });

  group('referencia', () {
    test('acepta un id positivo', () {
      expect(FieldValidator.validate(reference, '3'), isNull);
      expect(FieldValidator.parse(reference, '3'), 3);
    });

    test('exige seleccionar y rechaza ids no válidos', () {
      expect(FieldValidator.validate(reference, null), contains('Selecciona'));
      expect(FieldValidator.validate(reference, ''), contains('Selecciona'));
      expect(FieldValidator.validate(reference, '0'), isNotNull);
      expect(FieldValidator.validate(reference, '-1'), isNotNull);
      expect(FieldValidator.validate(reference, 'x'), isNotNull);
    });
  });
}
