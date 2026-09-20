import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/data/entity_gateway.dart';
import 'package:gestion_movil/data/failures.dart';
import 'package:gestion_movil/domain/entity_module.dart';
import 'package:gestion_movil/domain/pending_op.dart';
import 'package:gestion_movil/models/pedido.dart';
import 'package:gestion_movil/models/pedido_producto.dart';
import 'package:gestion_movil/models/producto.dart';

import '../support/fake_backend.dart';
import '../support/test_env.dart';

/// El repositorio que usa la UI: datos locales + cola + servidor. Aquí, sobre todo, lo que ocurre
/// SIN conexión: la app sigue funcionando y toda escritura queda pendiente de sincronizar.
void main() {
  late FakeBackend backend;
  late TestEnv env;
  late EntityGateway productos;
  late EntityGateway pedidos;
  late EntityGateway relaciones;

  setUp(() async {
    backend = FakeBackend()
      ..insert('producto', {'nombre': 'Camisa', 'precio': 19.9})
      ..insert('producto', {'nombre': 'Zapato', 'precio': 40.0})
      ..insert('pedido', {'fecha': '2026-09-01'});
    env = await TestEnv.sqlite(backend: backend);
    productos = env.gateway(const ProductoModule());
    pedidos = env.gateway(const PedidoModule());
    relaciones = env.gateway(const PedidoProductoModule());
    // Carga inicial con conexión: es lo que la app "recuerda" después.
    await productos.list();
    await pedidos.list();
    await relaciones.list();
  });

  tearDown(() => env.dispose());

  group('la app sigue funcionando sin conexión', () {
    test(
      'lee los últimos datos guardados de cada entidad (y lo dice)',
      () async {
        env.goOffline();

        final result = await productos.list();

        expect(result.fromCache, isTrue);
        expect(result.items.map((e) => (e as Producto).nombre), [
          'Camisa',
          'Zapato',
        ]);
        expect((await pedidos.list()).items, hasLength(1));
      },
    );

    test(
      'con conexión los datos vienen del servidor y refrescan la caché',
      () async {
        backend.insert('producto', {'nombre': 'Gorra', 'precio': 8.5});

        final result = await productos.list();
        expect(result.fromCache, isFalse);
        expect(result.items, hasLength(3));

        env.goOffline();
        expect(
          (await productos.list()).items,
          hasLength(3),
          reason: 'la caché quedó al día',
        );
      },
    );

    test('consultar un registro conocido sin conexión funciona; uno desconocido lo dice claro', () async {
      env.goOffline();

      expect(((await productos.getById(1)) as Producto).nombre, 'Camisa');
      await expectLater(
        productos.getById(99),
        throwsA(
          isA<OfflineMissFailure>().having(
            (f) => f.userMessage,
            'mensaje',
            contains('Sin conexión'),
          ),
        ),
      );
    });

    test('CREAR sin conexión: se guarda local, queda PENDIENTE y se ve en la lista', () async {
      env.goOffline();

      final outcome = await productos.create(
        const Producto(nombre: 'Gorra', precio: 8.5),
      );

      expect(outcome.isPending, isTrue);
      expect(
        outcome.entity!.id,
        isNegative,
        reason: 'id temporal hasta que el servidor asigne el real',
      );
      expect(backend.count('producto'), 2, reason: 'nada llegó al servidor');

      final op = await env.opOf(OpKind.create);
      expect(op.status, OpStatus.pending);
      expect(op.values, {'nombre': 'Gorra', 'precio': 8.5});

      final list = await productos.list();
      expect(list.items, hasLength(3));
      expect(list.pendingIds, {outcome.entity!.id});
      expect(
        ((await productos.getById(outcome.entity!.id!)) as Producto).nombre,
        'Gorra',
      );
    });

    test('ACTUALIZAR sin conexión: pendiente, con la base (lo último que sabía del servidor)', () async {
      env.goOffline();

      final outcome = await productos.update(
        1,
        const Producto(nombre: 'Camisa Pro', precio: 25),
      );

      expect(outcome.isPending, isTrue);
      final op = await env.opOf(OpKind.update);
      expect(op.targetId, 1);
      expect(op.base, {'nombre': 'Camisa', 'precio': 19.9});
      expect(op.values, {'nombre': 'Camisa Pro', 'precio': 25.0});
      expect(
        ((await productos.getById(1)) as Producto).nombre,
        'Camisa Pro',
        reason: 'la vista local ya lo refleja',
      );
      expect(
        backend.tables['producto']![1]!['nombre'],
        'Camisa',
        reason: 'el servidor no cambió',
      );
    });

    test('ELIMINAR sin conexión: pendiente y el registro desaparece de la vista local', () async {
      env.goOffline();

      final outcome = await productos.delete(2);

      expect(outcome.isPending, isTrue);
      expect((await productos.list()).items.map((e) => e.id), [1]);
      expect(backend.count('producto'), 2);
      expect((await env.opOf(OpKind.delete)).base, {
        'nombre': 'Zapato',
        'precio': 40.0,
      });
    });

    test('borrar un Pedido pendiente oculta sus relaciones (como hace el servidor en cascada)', () async {
      backend.insert('producto', {'nombre': 'P', 'precio': 1.0});
      final creada = await relaciones.create(
        const PedidoProducto(pedidoId: 1, productoId: 1),
      );
      expect(creada.status, WriteStatus.synced);

      env.goOffline();
      await pedidos.delete(1);

      expect((await relaciones.list()).items, isEmpty);
    });
  });

  group('validación: se reutiliza la de siempre (FieldValidator), nada inválido llega a la cola', () {
    test(
      'un nombre vacío o un precio no numérico se rechazan antes de encolar',
      () async {
        env.goOffline();

        await expectLater(
          productos.create(const Producto(nombre: '  ', precio: 1)),
          throwsA(
            isA<InvalidInputFailure>().having(
              (f) => f.userMessage,
              'mensaje',
              contains('obligatorio'),
            ),
          ),
        );
        await expectLater(
          productos.create(Producto(nombre: 'X', precio: double.nan)),
          throwsA(isA<InvalidInputFailure>()),
        );
        await expectLater(
          productos.create(Producto(nombre: 'X', precio: double.infinity)),
          throwsA(isA<InvalidInputFailure>()),
        );
        await expectLater(
          productos.create(Producto(nombre: 'x' * 256, precio: 1)),
          throwsA(isA<InvalidInputFailure>()),
        );

        expect(
          await env.ops(),
          isEmpty,
          reason: 'ninguna operación inválida quedó pendiente',
        );
      },
    );

    test('un update inválido tampoco se encola', () async {
      env.goOffline();
      await expectLater(
        productos.update(1, const Producto(nombre: '', precio: 1)),
        throwsA(isA<InvalidInputFailure>()),
      );
      expect(await env.ops(), isEmpty);
    });

    test('las referencias aceptan ids temporales negativos (registros creados sin conexión), pero no 0', () async {
      env.goOffline();
      final pedido = await pedidos.create(const Pedido(fecha: 'f'));
      final producto = await productos.create(
        const Producto(nombre: 'N', precio: 1),
      );

      final ok = await relaciones.create(
        PedidoProducto(
          pedidoId: pedido.entity!.id,
          productoId: producto.entity!.id,
        ),
      );
      expect(ok.isPending, isTrue);

      await expectLater(
        relaciones.create(const PedidoProducto(pedidoId: 0, productoId: 1)),
        throwsA(isA<InvalidInputFailure>()),
      );
    });
  });

  group('reglas de fusión de la cola (menos operaciones, mismo resultado)', () {
    test('editar un registro creado sin conexión modifica SU create: sigue habiendo una sola operación', () async {
      env.goOffline();
      final created = await productos.create(
        const Producto(nombre: 'Borrador', precio: 1),
      );

      await productos.update(
        created.entity!.id!,
        const Producto(nombre: 'Definitivo', precio: 2),
      );

      final ops = await env.ops();
      expect(ops, hasLength(1));
      expect(ops.single.kind, OpKind.create);
      expect(ops.single.values, {'nombre': 'Definitivo', 'precio': 2.0});
    });

    test('eliminar un registro creado sin conexión lo descarta: no queda operación ni llega al servidor', () async {
      env.goOffline();
      final created = await productos.create(
        const Producto(nombre: 'Efímero', precio: 1),
      );

      final outcome = await productos.delete(created.entity!.id!);

      expect(outcome.status, WriteStatus.synced);
      expect(outcome.message, contains('nunca había llegado'));
      expect(await env.ops(), isEmpty);
      expect((await productos.list()).items, hasLength(2));
    });

    test('descartar un Pedido creado offline rechaza (con motivo visible) la relación que dependía de él', () async {
      env.goOffline();
      final pedido = await pedidos.create(const Pedido(fecha: 'f'));
      await relaciones.create(
        PedidoProducto(pedidoId: pedido.entity!.id, productoId: 1),
      );

      await pedidos.delete(pedido.entity!.id!);

      final dependent = (await env.ops()).single;
      expect(dependent.status, OpStatus.rejected);
      expect(dependent.reason, OpReason.parentRejected);
      expect(dependent.detail, contains('descartado'));
    });

    test('dos actualizaciones seguidas del mismo registro se combinan y conservan la base original', () async {
      env.goOffline();
      await productos.update(
        1,
        const Producto(nombre: 'Camisa v2', precio: 21),
      );
      await productos.update(
        1,
        const Producto(nombre: 'Camisa v3', precio: 22),
      );

      final ops = await env.ops();
      expect(ops, hasLength(1));
      expect(ops.single.values, {'nombre': 'Camisa v3', 'precio': 22.0});
      expect(ops.single.base, {
        'nombre': 'Camisa',
        'precio': 19.9,
      }, reason: 'la base es lo que decía el servidor');
    });

    test('eliminar tras actualizar reemplaza el update por un delete con la base original', () async {
      env.goOffline();
      await productos.update(
        1,
        const Producto(nombre: 'Camisa v2', precio: 21),
      );
      await productos.delete(1);

      final ops = await env.ops();
      expect(ops, hasLength(1));
      expect(ops.single.kind, OpKind.delete);
      expect(ops.single.base, {'nombre': 'Camisa', 'precio': 19.9});
    });
  });

  group('con conexión', () {
    test('escribir con conexión y cola vacía se ejecuta al momento y queda verificado (como CU12)', () async {
      final outcome = await productos.create(
        const Producto(nombre: 'Gorra', precio: 8.5),
      );

      expect(outcome.status, WriteStatus.synced);
      expect(outcome.entity!.id, 3, reason: 'id real asignado por el servidor');
      expect(backend.count('producto'), 3);
      expect((await productos.list()).pendingIds, isEmpty);
    });

    test('un conflicto detectado al momento (otro cliente lo cambió) se informa y NO se aplica', () async {
      backend.tables['producto']![1]!['precio'] =
          30.0; // otro cliente, después de mi última carga

      await expectLater(
        productos.update(1, const Producto(nombre: 'Camisa', precio: 25)),
        throwsA(
          isA<ConflictFailure>().having(
            (f) => f.userMessage,
            'mensaje',
            contains('modificado por otro usuario'),
          ),
        ),
      );

      expect(
        backend.tables['producto']![1]!['precio'],
        30.0,
        reason: 'el servidor gana',
      );
      expect(
        await env.ops(),
        everyElement(predicate<PendingOp>((o) => o.status == OpStatus.synced)),
      );
    });

    test('un rechazo del servidor se muestra como en CU12 y no deja nada pendiente', () async {
      backend.rejectBody = (table, body) => body['nombre'] == 'MALO';

      await expectLater(
        productos.create(const Producto(nombre: 'MALO', precio: 1)),
        throwsA(isA<ConflictFailure>()),
      );

      expect(backend.count('producto'), 2);
      expect((await env.ops()).where((o) => o.isActive), isEmpty);
    });
  });
}
