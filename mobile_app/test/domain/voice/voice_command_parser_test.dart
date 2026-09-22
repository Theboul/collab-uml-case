import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/domain/voice/text_normalizer.dart';
import 'package:gestion_movil/domain/voice/voice_command.dart';
import 'package:gestion_movil/domain/voice/voice_command_parser.dart';

/// CU14 · corpus del parser por reglas: frase (tal como la diría o escribiría el usuario) →
/// resultado esperado. Se escribió ANTES que el parser.
///
/// Los valores de los slots son texto CRUDO (`'19,90'`, no `19.9`): convertirlos y validarlos es
/// trabajo de `FieldValidator` al ejecutar (Fase 2), no del parser.

/// Caso que debe producir un [VoiceCommand].
class _Ok {
  const _Ok(this.phrase, this.intent, this.path, this.id, this.values);

  final String phrase;
  final VoiceIntent intent;
  final String path;
  final int? id;
  final Map<String, String> values;
}

/// Caso que debe producir un [VoiceFailure] de [kind].
class _Fail {
  const _Fail(
    this.phrase,
    this.kind, {
    this.missing = const [],
    this.candidates = const [],
    this.understood,
  });

  final String phrase;
  final VoiceErrorKind kind;
  final List<String> missing;
  final List<String> candidates;

  /// `null` = no se comprueba.
  final List<String>? understood;
}

const _crearProducto = [
  _Ok('crear producto camisa 20', VoiceIntent.crear, 'producto', null, {
    'nombre': 'camisa',
    'precio': '20',
  }),
  _Ok(
    'Crear producto camisa con precio 20',
    VoiceIntent.crear,
    'producto',
    null,
    {'nombre': 'camisa', 'precio': '20'},
  ),
  _Ok(
    'crear un producto llamado camisa azul con precio 19,90',
    VoiceIntent.crear,
    'producto',
    null,
    {'nombre': 'camisa azul', 'precio': '19,90'},
  ),
  _Ok('agrega producto vaso precio 5', VoiceIntent.crear, 'producto', null, {
    'nombre': 'vaso',
    'precio': '5',
  }),
  // Orden de palabras distinto
  _Ok(
    'crear producto precio 20 nombre camisa',
    VoiceIntent.crear,
    'producto',
    null,
    {'nombre': 'camisa', 'precio': '20'},
  ),
  _Ok('crear producto 20 camisa', VoiceIntent.crear, 'producto', null, {
    'nombre': 'camisa',
    'precio': '20',
  }),
  _Ok(
    'nuevo producto zapatos deportivos 45.5',
    VoiceIntent.crear,
    'producto',
    null,
    {'nombre': 'zapatos deportivos', 'precio': '45.5'},
  ),
  _Ok(
    'registrar producto pantalon con precio 100',
    VoiceIntent.crear,
    'producto',
    null,
    {'nombre': 'pantalon', 'precio': '100'},
  ),
  _Ok(
    'añade el producto gorra a 8 bolivianos',
    VoiceIntent.crear,
    'producto',
    null,
    {'nombre': 'gorra', 'precio': '8'},
  ),
  // Las palabras internas del nombre ("de") no se pierden
  _Ok(
    'crear producto camisa de algodon con precio 20',
    VoiceIntent.crear,
    'producto',
    null,
    {'nombre': 'camisa de algodon', 'precio': '20'},
  ),
  // Salida real vista en la Fase 0 con el reconocedor de Google: "producto crear producto camisa 20"
  _Ok(
    'producto crear producto camisa 20',
    VoiceIntent.crear,
    'producto',
    null,
    {'nombre': 'camisa', 'precio': '20'},
  ),
  // Números en palabras (0-999)
  _Ok('crear producto camisa veinte', VoiceIntent.crear, 'producto', null, {
    'nombre': 'camisa',
    'precio': '20',
  }),
  _Ok(
    'crear producto camisa treinta y cinco',
    VoiceIntent.crear,
    'producto',
    null,
    {'nombre': 'camisa', 'precio': '35'},
  ),
  _Ok('crear producto camisa veintiuno', VoiceIntent.crear, 'producto', null, {
    'nombre': 'camisa',
    'precio': '21',
  }),
  _Ok(
    'crear producto camisa ciento veinte',
    VoiceIntent.crear,
    'producto',
    null,
    {'nombre': 'camisa', 'precio': '120'},
  ),
  _Ok(
    'crear producto camisa doscientos cincuenta y uno',
    VoiceIntent.crear,
    'producto',
    null,
    {'nombre': 'camisa', 'precio': '251'},
  ),
  _Ok(
    'registrar producto pantalon con precio cien',
    VoiceIntent.crear,
    'producto',
    null,
    {'nombre': 'pantalon', 'precio': '100'},
  ),
  // Un valor que NO es número se conserva tal cual: lo rechaza el validador al ejecutar (Fase 2)
  _Ok('crear producto camisa precio abc', VoiceIntent.crear, 'producto', null, {
    'nombre': 'camisa',
    'precio': 'abc',
  }),
];

const _crearPedido = [
  _Ok('crear pedido fecha 2026-09-21', VoiceIntent.crear, 'pedido', null, {
    'fecha': '2026-09-21',
  }),
  _Ok(
    'crear pedido con fecha 21 de septiembre de 2026',
    VoiceIntent.crear,
    'pedido',
    null,
    {'fecha': '21 de septiembre de 2026'},
  ),
  _Ok('crear pedido 2026-09-21', VoiceIntent.crear, 'pedido', null, {
    'fecha': '2026-09-21',
  }),
  _Ok(
    'agrega un pedido fecha 15 de octubre de 2026',
    VoiceIntent.crear,
    'pedido',
    null,
    {'fecha': '15 de octubre de 2026'},
  ),
  _Ok('nuevo pedido con fecha 2026-10-01', VoiceIntent.crear, 'pedido', null, {
    'fecha': '2026-10-01',
  }),
];

const _consultarProducto = [
  _Ok('listar productos', VoiceIntent.consultar, 'producto', null, {}),
  _Ok('muestra los productos', VoiceIntent.consultar, 'producto', null, {}),
  _Ok('quiero ver los productos', VoiceIntent.consultar, 'producto', null, {}),
  _Ok('consultar producto 3', VoiceIntent.consultar, 'producto', 3, {}),
  _Ok('ver el producto numero 3', VoiceIntent.consultar, 'producto', 3, {}),
  _Ok('buscar producto con id 7', VoiceIntent.consultar, 'producto', 7, {}),
  _Ok('consulta el producto tres', VoiceIntent.consultar, 'producto', 3, {}),
];

const _consultarPedido = [
  _Ok('listar pedidos', VoiceIntent.consultar, 'pedido', null, {}),
  _Ok('ver los pedidos', VoiceIntent.consultar, 'pedido', null, {}),
  _Ok('consultar pedido 2', VoiceIntent.consultar, 'pedido', 2, {}),
  _Ok('mostrar el pedido numero 2', VoiceIntent.consultar, 'pedido', 2, {}),
];

const _actualizarProducto = [
  _Ok(
    'actualizar producto 3 precio 25',
    VoiceIntent.actualizar,
    'producto',
    3,
    {'precio': '25'},
  ),
  _Ok(
    'cambiar el precio del producto 3 a 25',
    VoiceIntent.actualizar,
    'producto',
    3,
    {'precio': '25'},
  ),
  _Ok(
    'cambiar a 25 el precio del producto 3',
    VoiceIntent.actualizar,
    'producto',
    3,
    {'precio': '25'},
  ),
  _Ok(
    'modificar producto 3 nombre camisa roja',
    VoiceIntent.actualizar,
    'producto',
    3,
    {'nombre': 'camisa roja'},
  ),
  _Ok(
    'cambia el nombre del producto 3 a camisa roja',
    VoiceIntent.actualizar,
    'producto',
    3,
    {'nombre': 'camisa roja'},
  ),
  _Ok(
    'editar producto numero 3 precio a treinta',
    VoiceIntent.actualizar,
    'producto',
    3,
    {'precio': '30'},
  ),
  _Ok(
    'actualiza el producto 5 con precio 12,5',
    VoiceIntent.actualizar,
    'producto',
    5,
    {'precio': '12,5'},
  ),
];

const _actualizarPedido = [
  _Ok(
    'actualizar pedido 2 fecha 2026-10-01',
    VoiceIntent.actualizar,
    'pedido',
    2,
    {'fecha': '2026-10-01'},
  ),
  _Ok(
    'cambiar la fecha del pedido 2 a 2026-10-01',
    VoiceIntent.actualizar,
    'pedido',
    2,
    {'fecha': '2026-10-01'},
  ),
  _Ok(
    'modificar el pedido 4 fecha 20 de octubre de 2026',
    VoiceIntent.actualizar,
    'pedido',
    4,
    {'fecha': '20 de octubre de 2026'},
  ),
];

const _eliminarProducto = [
  _Ok('eliminar producto 3', VoiceIntent.eliminar, 'producto', 3, {}),
  _Ok('borrar el producto numero 3', VoiceIntent.eliminar, 'producto', 3, {}),
  _Ok('elimina producto con id 3', VoiceIntent.eliminar, 'producto', 3, {}),
  _Ok('quitar el producto 3', VoiceIntent.eliminar, 'producto', 3, {}),
  _Ok('eliminar producto tres', VoiceIntent.eliminar, 'producto', 3, {}),
];

const _eliminarPedido = [
  _Ok('eliminar pedido 2', VoiceIntent.eliminar, 'pedido', 2, {}),
  _Ok('borra el pedido 2', VoiceIntent.eliminar, 'pedido', 2, {}),
  _Ok('quitar pedido numero 2', VoiceIntent.eliminar, 'pedido', 2, {}),
];

const _ok = [
  ..._crearProducto,
  ..._crearPedido,
  ..._consultarProducto,
  ..._consultarPedido,
  ..._actualizarProducto,
  ..._actualizarPedido,
  ..._eliminarProducto,
  ..._eliminarPedido,
];

const _ambigua = [
  // Dos acciones distintas
  _Fail(
    'crear y eliminar producto camisa',
    VoiceErrorKind.intencionAmbigua,
    candidates: ['crear', 'eliminar'],
    understood: ['Entidad: Producto'],
  ),
  _Fail(
    'borrar o actualizar el pedido 2',
    VoiceErrorKind.intencionAmbigua,
    candidates: ['eliminar', 'actualizar'],
    understood: ['Entidad: Pedido'],
  ),
  // Dos entidades distintas
  _Fail(
    'crear producto y pedido',
    VoiceErrorKind.intencionAmbigua,
    candidates: ['Producto', 'Pedido'],
    understood: ['Acción: crear'],
  ),
  _Fail(
    'listar productos y pedidos',
    VoiceErrorKind.intencionAmbigua,
    candidates: ['Producto', 'Pedido'],
    understood: ['Acción: consultar'],
  ),
  // Hay acción pero no se dijo sobre qué (o se nombró algo que la app no maneja)
  _Fail(
    'crear camisa 20',
    VoiceErrorKind.intencionAmbigua,
    candidates: ['Pedido', 'Producto'],
    understood: ['Acción: crear'],
  ),
  _Fail(
    'listar',
    VoiceErrorKind.intencionAmbigua,
    candidates: ['Pedido', 'Producto'],
    understood: ['Acción: consultar'],
  ),
  _Fail(
    'eliminar 3',
    VoiceErrorKind.intencionAmbigua,
    candidates: ['Pedido', 'Producto'],
    understood: ['Acción: eliminar'],
  ),
  _Fail(
    'crear cliente juan',
    VoiceErrorKind.intencionAmbigua,
    candidates: ['Pedido', 'Producto'],
    understood: ['Acción: crear'],
  ),
  // Actualizar admite UN campo por comando
  _Fail(
    'actualizar producto 3 nombre camisa precio 20',
    VoiceErrorKind.intencionAmbigua,
    candidates: ['Nombre', 'Precio'],
    understood: ['Acción: actualizar', 'Entidad: Producto', 'ID: 3'],
  ),
];

const _faltantes = [
  _Fail(
    'crear producto',
    VoiceErrorKind.datosFaltantes,
    missing: ['Nombre', 'Precio'],
    understood: ['Acción: crear', 'Entidad: Producto'],
  ),
  _Fail(
    'crear producto camisa',
    VoiceErrorKind.datosFaltantes,
    missing: ['Precio'],
    understood: ['Acción: crear', 'Entidad: Producto', 'Nombre: camisa'],
  ),
  _Fail(
    'crear producto precio 20',
    VoiceErrorKind.datosFaltantes,
    missing: ['Nombre'],
    understood: ['Acción: crear', 'Entidad: Producto', 'Precio: 20'],
  ),
  _Fail(
    'crear producto camisa precio',
    VoiceErrorKind.datosFaltantes,
    missing: ['Precio'],
  ),
  _Fail(
    'crear pedido',
    VoiceErrorKind.datosFaltantes,
    missing: ['Fecha'],
    understood: ['Acción: crear', 'Entidad: Pedido'],
  ),
  _Fail(
    'eliminar producto',
    VoiceErrorKind.datosFaltantes,
    missing: ['ID'],
    understood: ['Acción: eliminar', 'Entidad: Producto'],
  ),
  _Fail('borrar pedido', VoiceErrorKind.datosFaltantes, missing: ['ID']),
  _Fail(
    'consultar producto numero',
    VoiceErrorKind.datosFaltantes,
    missing: ['ID'],
  ),
  _Fail(
    'actualizar producto 3',
    VoiceErrorKind.datosFaltantes,
    missing: ['Campo', 'Valor'],
    candidates: ['Nombre', 'Precio'],
    understood: ['Acción: actualizar', 'Entidad: Producto', 'ID: 3'],
  ),
  _Fail(
    'actualizar producto 3 precio',
    VoiceErrorKind.datosFaltantes,
    missing: ['Valor'],
    understood: [
      'Acción: actualizar',
      'Entidad: Producto',
      'ID: 3',
      'Campo: Precio',
    ],
  ),
  _Fail(
    'actualizar producto precio 25',
    VoiceErrorKind.datosFaltantes,
    missing: ['ID'],
  ),
  _Fail(
    'modificar pedido 2 fecha',
    VoiceErrorKind.datosFaltantes,
    missing: ['Valor'],
  ),
];

const _inexistente = [
  // Sin ninguna acción conocida
  _Fail('hola buenos dias', VoiceErrorKind.accionInexistente),
  _Fail('abrir la camara', VoiceErrorKind.accionInexistente),
  _Fail('enviar producto 3', VoiceErrorKind.accionInexistente),
  _Fail('exportar productos a excel', VoiceErrorKind.accionInexistente),
  _Fail('cuantos productos hay', VoiceErrorKind.accionInexistente),
  // Fuera de vocabulario / sin sentido
  _Fail('blablabla', VoiceErrorKind.accionInexistente),
  // Transcripción vacía: se trata como acción inexistente (ver docs/decisions.md)
  _Fail('', VoiceErrorKind.accionInexistente),
  _Fail('   ', VoiceErrorKind.accionInexistente),
  // PedidoProducto no se maneja por voz en esta fase
  _Fail(
    'crear una relacion entre pedido y producto',
    VoiceErrorKind.accionInexistente,
  ),
  _Fail('eliminar pedidoproducto 3', VoiceErrorKind.accionInexistente),
];

VoiceParseResult _parse(String spoken) =>
    const VoiceCommandParser().parse(normalizeText(spoken));

void main() {
  group('frases válidas → VoiceCommand', () {
    for (final c in _ok) {
      test('"${c.phrase}"', () {
        final result = _parse(c.phrase);
        expect(
          result,
          isA<VoiceCommand>(),
          reason: 'obtuvo: ${_describe(result)}',
        );
        final cmd = result as VoiceCommand;
        expect(cmd.intent, c.intent, reason: 'acción');
        expect(cmd.module.path, c.path, reason: 'entidad');
        expect(cmd.id, c.id, reason: 'id');
        expect(cmd.values, c.values, reason: 'slots');
      });
    }
  });

  void failureGroup(String title, List<_Fail> cases) {
    group(title, () {
      for (final c in cases) {
        test('"${c.phrase}"', () {
          final result = _parse(c.phrase);
          expect(
            result,
            isA<VoiceFailure>(),
            reason: 'obtuvo: ${_describe(result)}',
          );
          final failure = result as VoiceFailure;
          expect(failure.kind, c.kind);
          expect(failure.missing, c.missing, reason: 'qué falta');
          expect(
            failure.candidates,
            c.candidates,
            reason: 'opciones/candidatos',
          );
          if (c.understood != null) {
            expect(failure.understood, c.understood, reason: 'qué se entendió');
          }
        });
      }
    });
  }

  failureGroup('intencionAmbigua', _ambigua);
  failureGroup('datosFaltantes', _faltantes);
  failureGroup('accionInexistente', _inexistente);

  group('propiedades del parser', () {
    test('nunca produce vozNoReconocida ni recursosInsuficientes (son de la capa de ASR)', () {
      for (final c in [..._ambigua, ..._faltantes, ..._inexistente]) {
        final result = _parse(c.phrase);
        if (result is VoiceFailure) {
          expect(
            result.kind,
            isNot(
              anyOf(
                VoiceErrorKind.vozNoReconocida,
                VoiceErrorKind.recursosInsuficientes,
              ),
            ),
            reason: '"${c.phrase}"',
          );
        }
      }
    });

    test('las entidades por voz se derivan de los EntityModule (sin PedidoProducto)', () {
      expect(voiceModules.map((m) => m.path), ['pedido', 'producto']);
    });

    test('es pura: la misma frase da siempre el mismo resultado', () {
      for (final c in _ok) {
        expect(_describe(_parse(c.phrase)), _describe(_parse(c.phrase)));
      }
    });

    test(
      'el mensaje de cada VoiceCommand describe lo que se va a ejecutar',
      () {
        final cmd = _parse('crear producto camisa 20') as VoiceCommand;
        expect(cmd.summary, contains('Crear'));
        expect(cmd.summary, contains('Producto'));
        expect(cmd.summary, contains('Nombre: camisa'));
        expect(cmd.summary, contains('Precio: 20'));
      },
    );
  });

  group('cobertura del corpus (verificada por código)', () {
    test(
      'cada template (acción × entidad) tiene al menos 2 frases distintas',
      () {
        for (final intent in VoiceIntent.values) {
          for (final path in ['producto', 'pedido']) {
            final n = _ok
                .where((c) => c.intent == intent && c.path == path)
                .length;
            expect(
              n,
              greaterThanOrEqualTo(2),
              reason: '${intent.name} × $path tiene $n',
            );
          }
        }
      },
    );

    test('cada excepción del parser tiene al menos 2 casos', () {
      for (final (kind, cases) in [
        (VoiceErrorKind.intencionAmbigua, _ambigua),
        (VoiceErrorKind.datosFaltantes, _faltantes),
        (VoiceErrorKind.accionInexistente, _inexistente),
      ]) {
        expect(cases.length, greaterThanOrEqualTo(2), reason: kind.name);
        expect(cases.every((c) => c.kind == kind), isTrue);
      }
    });

    test('las variantes de orden de palabras están cubiertas para crear/actualizar', () {
      // Mismos valores, distinto orden: al menos dos formas distintas de decir lo mismo.
      Set<String> orders(List<_Ok> group, String path) => {
        for (final c in group.where((c) => c.path == path))
          c.phrase.split(' ').skip(1).join(' '),
      };
      expect(orders(_crearProducto, 'producto').length, greaterThan(2));
      expect(orders(_actualizarProducto, 'producto').length, greaterThan(2));
    });
  });
}

String _describe(VoiceParseResult r) => switch (r) {
  VoiceCommand c =>
    'VoiceCommand(${c.intent.name} ${c.module.path} id=${c.id} ${c.values})',
  VoiceFailure f =>
    'VoiceFailure(${f.kind.name} missing=${f.missing} candidates=${f.candidates} understood=${f.understood})',
};
