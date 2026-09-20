import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/data/api_client.dart';
import 'package:gestion_movil/data/entity_repository.dart';
import 'package:gestion_movil/data/failures.dart';
import 'package:gestion_movil/domain/entity_module.dart';
import 'package:gestion_movil/models/pedido_producto.dart';
import 'package:gestion_movil/models/producto.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../support/fake_backend.dart';

/// Comportamiento del repositorio frente a las respuestas poco fiables del backend generado.
void main() {
  late FakeBackend backend;
  late EntityRepository productos;
  late EntityRepository relaciones;

  setUp(() {
    backend = FakeBackend();
    final api = ApiClient(client: backend.client, baseUrl: 'http://fake/api');
    productos = EntityRepository(const ProductoModule(), api);
    relaciones = EntityRepository(const PedidoProductoModule(), api);
  });

  group('consultar', () {
    test('lista los registros', () async {
      backend.insert('producto', {'nombre': 'Camisa', 'precio': 19.9});
      backend.insert('producto', {'nombre': 'Zapato', 'precio': 40.0});

      final items = (await productos.list()).cast<Producto>();

      expect(items.map((p) => p.nombre), ['Camisa', 'Zapato']);
      expect(items.map((p) => p.id), [1, 2]);
    });

    test('un id inexistente (el backend responde 500) se traduce a NotFoundFailure', () async {
      backend.insert('producto', {'nombre': 'Camisa', 'precio': 19.9});

      await expectLater(
        productos.getById(99),
        throwsA(
          isA<NotFoundFailure>().having(
            (f) => f.userMessage,
            'mensaje',
            contains('99'),
          ),
        ),
      );
    });

    test('un 500 real (el id SÍ existe) no se disfraza de "no existe": es ServerFailure', () async {
      backend.insert('producto', {'nombre': 'Camisa', 'precio': 19.9});
      backend.failNextWith = 500;

      await expectLater(productos.getById(1), throwsA(isA<ServerFailure>()));
    });
  });

  group('crear', () {
    test(
      'envía solo nombre y precio (sin id) y devuelve el registro con su id',
      () async {
        final saved = await productos.create(
          const Producto(nombre: 'Camisa', precio: 19.9),
        );

        expect(saved.id, 1);
        expect(backend.count('producto'), 1);
        expect(backend.tables['producto']![1]!['precio'], 19.9);
        expect(backend.log, ['POST /api/producto']);
      },
    );

    test('400 del servidor → RejectedFailure y nada guardado', () async {
      backend.failNextWith = 400;

      await expectLater(
        productos.create(const Producto(nombre: 'X', precio: 1)),
        throwsA(isA<RejectedFailure>()),
      );
      expect(backend.count('producto'), 0);
    });

    test('si el backend ignora un campo (200 con null) NO se afirma éxito y se descarta la fila', () async {
      // Los ids de relación inexistentes se ignoran en silencio: 200 con pedido/producto en null.
      final failure = await _failureOf(
        () => relaciones.create(
          const PedidoProducto(pedidoId: 91, productoId: 92),
        ),
      );

      expect(failure, isA<InconsistentResultFailure>());
      expect(failure.userMessage, contains('Pedido'));
      expect(failure.userMessage, contains('Producto'));
      expect(failure.userMessage, contains('Se descartó'));
      expect(
        backend.count('pedidoproducto'),
        0,
        reason: 'no debe quedar una fila a medias',
      );
      expect(backend.log, [
        'POST /api/pedidoproducto',
        'DELETE /api/pedidoproducto/1',
        'GET /api/pedidoproducto', // verifica que de verdad desapareció
      ]);
    });

    test('si además falla el descarte, el mensaje lo dice para que el usuario lo revise', () async {
      backend.deleteDoesNothing = true;

      final failure = await _failureOf(
        () => relaciones.create(
          const PedidoProducto(pedidoId: 91, productoId: 92),
        ),
      );

      expect(failure.userMessage, contains('No se pudo descartar'));
      expect(backend.count('pedidoproducto'), 1);
    });

    test('crear una relación con ids existentes funciona (claves pedidoid/productoid)', () async {
      final pedido = backend.insert('pedido', {'fecha': '2026-09-01'});
      final producto = backend.insert('producto', {
        'nombre': 'Camisa',
        'precio': 19.9,
      });

      final saved = await relaciones.create(
        PedidoProducto(
          pedidoId: pedido['id'] as int,
          productoId: producto['id'] as int,
        ),
      ) as PedidoProducto;

      expect((saved.pedidoId, saved.productoId), (1, 1));
      expect(backend.count('pedidoproducto'), 1);
    });

    test('si solo una relación existe, se informa cuál no se guardó y se descarta la fila', () async {
      backend.insert('pedido', {'fecha': '2026-09-01'});

      final failure = await _failureOf(
        () => relaciones.create(
          const PedidoProducto(pedidoId: 1, productoId: 92),
        ),
      );

      expect(failure.userMessage, contains('Producto'));
      expect(failure.userMessage, isNot(contains('Pedido,')));
      expect(backend.count('pedidoproducto'), 0);
    });

    test('actualizar una relación cambia el producto', () async {
      backend.insert('pedido', {'fecha': 'a'});
      backend.insert('producto', {'nombre': 'A', 'precio': 1.0});
      backend.insert('producto', {'nombre': 'B', 'precio': 2.0});
      final creada = await relaciones.create(
        const PedidoProducto(pedidoId: 1, productoId: 1),
      );

      final saved = await relaciones.update(
        creada.id!,
        const PedidoProducto(pedidoId: 1, productoId: 2),
      ) as PedidoProducto;

      expect(saved.productoId, 2);
    });
  });

  group('actualizar', () {
    test(
      'aplica el cambio y usa el id REAL en la ruta (no el primer atributo)',
      () async {
        backend.insert('producto', {'nombre': 'Camisa', 'precio': 19.9});

        final saved = await productos.update(
          1,
          const Producto(id: 1, nombre: 'Camisa Pro', precio: 25),
        ) as Producto;

        expect(saved.nombre, 'Camisa Pro');
        expect(backend.tables['producto']![1]!['precio'], 25.0);
        expect(backend.log, contains('PUT /api/producto/1'));
        expect(backend.log.where((l) => l.contains('Camisa')), isEmpty);
      },
    );

    test(
      'un registro inexistente → NotFoundFailure y NO se envía ningún PUT',
      () async {
        await expectLater(
          productos.update(7, const Producto(nombre: 'X', precio: 1)),
          throwsA(isA<NotFoundFailure>()),
        );
        expect(backend.log.where((l) => l.startsWith('PUT')), isEmpty);
      },
    );

    test('si el servidor responde 200 pero no aplica el cambio → InconsistentResultFailure', () async {
      backend.insert('producto', {'nombre': 'Camisa', 'precio': 19.9});
      backend.ignoreUpdates = true;

      final failure = await _failureOf(
        () => productos.update(
          1,
          const Producto(nombre: 'Camisa Pro', precio: 25),
        ),
      );

      expect(failure, isA<InconsistentResultFailure>());
      expect(failure.userMessage, contains('Nombre'));
      expect(
        backend.tables['producto']![1]!['nombre'],
        'Camisa',
        reason: 'lo guardado no cambia',
      );
    });

    test(
      'un fallo del servidor durante el PUT deja el registro como estaba',
      () async {
        backend.insert('producto', {'nombre': 'Camisa', 'precio': 19.9});
        // getById (GET lista+id) consume peticiones; se fuerza el fallo justo en el PUT.
        final api = ApiClient(
          client: _failingOnPut(backend),
          baseUrl: 'http://fake/api',
        );
        final repo = EntityRepository(const ProductoModule(), api);

        await expectLater(
          repo.update(1, const Producto(nombre: 'Otro', precio: 99)),
          throwsA(isA<ServerFailure>()),
        );
        expect(backend.tables['producto']![1]!['nombre'], 'Camisa');
      },
    );
  });

  group('eliminar', () {
    test('elimina y confirma que el registro ya no existe', () async {
      backend.insert('producto', {'nombre': 'Camisa', 'precio': 19.9});

      await productos.delete(1);

      expect(backend.count('producto'), 0);
      expect(backend.log, contains('DELETE /api/producto/1'));
    });

    test('un id inexistente NO se da por eliminado: NotFoundFailure y ningún DELETE', () async {
      // El backend real respondería 200 a este DELETE; la app no lo asume como éxito.
      await expectLater(productos.delete(42), throwsA(isA<NotFoundFailure>()));
      expect(backend.log.where((l) => l.startsWith('DELETE')), isEmpty);
    });

    test('si el servidor dice 200 pero el registro sigue ahí → InconsistentResultFailure', () async {
      backend.insert('producto', {'nombre': 'Camisa', 'precio': 19.9});
      backend.deleteDoesNothing = true;

      final failure = await _failureOf(() => productos.delete(1));

      expect(failure, isA<InconsistentResultFailure>());
      expect(failure.userMessage, contains('sigue existiendo'));
      expect(backend.count('producto'), 1);
    });
  });

  group('sin conexión', () {
    test('toda operación falla con NetworkFailure y no altera nada', () async {
      backend.insert('producto', {'nombre': 'Camisa', 'precio': 19.9});
      backend.offline = true;

      await expectLater(productos.list(), throwsA(isA<NetworkFailure>()));
      await expectLater(productos.getById(1), throwsA(isA<NetworkFailure>()));
      await expectLater(
        productos.create(const Producto(nombre: 'X', precio: 1)),
        throwsA(isA<NetworkFailure>()),
      );
      await expectLater(productos.delete(1), throwsA(isA<NetworkFailure>()));

      backend.offline = false;
      expect(backend.count('producto'), 1);
    });

    test('un timeout también es NetworkFailure', () async {
      final slow = MockClient((_) => Completer<http.Response>().future);
      final api = ApiClient(
        client: slow,
        baseUrl: 'http://fake/api',
        timeout: const Duration(milliseconds: 50),
      );

      await expectLater(
        EntityRepository(const ProductoModule(), api).list(),
        throwsA(isA<NetworkFailure>()),
      );
    });
  });

  group('respuestas ilegibles', () {
    test('un cuerpo que no es JSON → InconsistentResultFailure (no una excepción cruda)', () async {
      final api = ApiClient(
        client: MockClient(
          (_) async => http.Response('<html>no soy json</html>', 200),
        ),
        baseUrl: 'http://fake/api',
      );

      await expectLater(
        EntityRepository(const ProductoModule(), api).list(),
        throwsA(isA<InconsistentResultFailure>()),
      );
    });
  });
}

Future<AppFailure> _failureOf(Future<Object?> Function() action) async {
  try {
    await action();
  } on AppFailure catch (failure) {
    return failure;
  }
  fail('se esperaba un AppFailure y la operación terminó bien');
}

/// Cliente que delega en el backend simulado pero responde 500 a cualquier PUT.
MockClient _failingOnPut(FakeBackend backend) {
  return MockClient((request) async {
    if (request.method == 'PUT') return http.Response('{"status":500}', 500);
    return backend.handle(request);
  });
}
