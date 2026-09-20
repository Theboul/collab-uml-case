import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/data/entity_gateway.dart';
import 'package:gestion_movil/domain/entity_module.dart';
import 'package:gestion_movil/domain/pending_op.dart';
import 'package:gestion_movil/models/pedido.dart';
import 'package:gestion_movil/models/pedido_producto.dart';
import 'package:gestion_movil/models/producto.dart';

import '../support/fake_backend.dart';
import '../support/sync_helpers.dart';
import '../support/test_env.dart';

/// Sincronización al reconectar y política de conflictos ("el servidor gana"), con SQLite real y un
/// backend simulado que reproduce el comportamiento medido del real.
void main() {
  late FakeBackend backend;
  late TestEnv env;
  late EntityGateway productos;
  late EntityGateway pedidos;
  late EntityGateway relaciones;

  setUp(() async {
    backend = seededBackend();
    env = await TestEnv.sqlite(backend: backend);
    productos = env.gateway(const ProductoModule());
    pedidos = env.gateway(const PedidoModule());
    relaciones = env.gateway(const PedidoProductoModule());
    await primeCache(env, ['producto', 'pedido', 'pedidoproducto']);
  });

  tearDown(() => env.dispose());

  group(
    'al recuperar la conexión, las operaciones pendientes se envían en orden',
    () {
      test('crear, actualizar y eliminar llegan al servidor y el estado local queda sincronizado', () async {
        env.goOffline();
        await pedidos.create(const Pedido(fecha: '2026-09-19'));
        await productos.create(const Producto(nombre: 'Gorra', precio: 8.5));
        await productos.update(
          1,
          const Producto(nombre: 'Camisa Pro', precio: 25),
        );
        await productos.delete(2);
        await env.services.sync.refreshCounts();
        expect(env.services.sync.pendingCount, 4);
        expect(writes(backend), isEmpty, reason: 'sin conexión no sale nada');

        await env.goOnline();

        expect(writes(backend), [
          'POST /api/pedido',
          'POST /api/producto',
          'PUT /api/producto/1',
          'DELETE /api/producto/2',
        ], reason: 'mismo orden en que el usuario las hizo');
        expect(backend.tables['producto']!.keys, [1, 3]);
        expect(backend.tables['producto']![1]!['nombre'], 'Camisa Pro');
        expect(backend.count('pedido'), 2);

        expect(env.services.sync.pendingCount, 0);
        expect(env.services.sync.attentionCount, 0);
        expect(
          (await env.ops()).every((o) => o.status == OpStatus.synced),
          isTrue,
        );

        final list = await productos.list();
        expect(list.items.map((e) => e.id), [
          1,
          3,
        ], reason: 'ids reales, no temporales');
        expect(list.pendingIds, isEmpty);
      });

      test('lo creado sin conexión con dependencias: la relación espera a sus padres y usa los ids reales', () async {
        env.goOffline();
        final pedido = await pedidos.create(const Pedido(fecha: 'nuevo'));
        final producto = await productos.create(
          const Producto(nombre: 'Nuevo', precio: 5),
        );
        await relaciones.create(
          PedidoProducto(
            pedidoId: pedido.entity!.id,
            productoId: producto.entity!.id,
          ),
        );

        await env.goOnline();

        final row = backend.tables['pedidoproducto']!.values.single;
        expect(
          (row['pedido'] as Map)['id'],
          2,
          reason: 'el Pedido nuevo recibió el id 2',
        );
        expect(
          (row['producto'] as Map)['id'],
          3,
          reason: 'el Producto nuevo recibió el id 3',
        );
        expect(
          (await env.ops()).every((o) => o.status == OpStatus.synced),
          isTrue,
        );
      });

      test('si el padre creado sin conexión es rechazado, lo que dependía de él se rechaza en cascada', () async {
        backend.rejectBody = (table, body) => body['nombre'] == 'MALO';
        env.goOffline();
        final producto = await productos.create(
          const Producto(nombre: 'MALO', precio: 1),
        );
        await relaciones.create(
          PedidoProducto(pedidoId: 1, productoId: producto.entity!.id),
        );

        await env.goOnline();

        final ops = await env.ops();
        expect(ops[0].status, OpStatus.rejected);
        expect(ops[0].reason, OpReason.serverRejected);
        expect(ops[1].status, OpStatus.rejected);
        expect(ops[1].reason, OpReason.parentRejected);
        expect(backend.count('pedidoproducto'), 0);
        expect(
          writes(backend).where((l) => l.contains('pedidoproducto')),
          isEmpty,
          reason: 'ni se intentó',
        );
      });
    },
  );

  group(
    'política de conflictos: el servidor gana, nada se pierde en silencio',
    () {
      test('CASO 1 · update de un registro que otro cliente borró: rechazada, no se recrea sola, "crear como nuevo" es opcional', () async {
        env.goOffline();
        await productos.update(
          1,
          const Producto(nombre: 'Camisa Pro', precio: 25),
        );
        backend.tables['producto']!.remove(
          1,
        ); // otro cliente lo borró mientras estaba offline

        await env.goOnline();

        final op = (await env.ops()).single;
        expect(op.status, OpStatus.rejected);
        expect(op.reason, OpReason.deletedRemotely);
        expect(op.detail, contains('eliminado por otro usuario'));
        expect(
          op.detail,
          contains('Camisa Pro'),
          reason: 'el usuario ve qué cambio perdió',
        );
        expect(op.values, {
          'nombre': 'Camisa Pro',
          'precio': 25.0,
        }, reason: 'sus datos se conservan');
        expect(
          writes(backend),
          isEmpty,
          reason: 'ni PUT ni POST: no se resucita nada',
        );
        expect(backend.tables['producto']!.containsKey(1), isFalse);
        expect(
          await env.store.readRecord('producto', 1),
          isNull,
          reason: 'el servidor gana: se quita de la caché',
        );
        expect((await productos.list()).items.map((e) => e.id), [2]);
        expect(env.services.sync.attentionCount, 1);

        // Acción explícita del usuario: crear como nuevo (id nuevo, nunca el viejo).
        await env.services.engine.createAsNew(op.opId);
        await env.services.sync.syncNow();

        expect(
          backend.tables['producto']!.containsKey(1),
          isFalse,
          reason: 'el id borrado no reaparece',
        );
        expect(
          countWhere(backend, 'producto', {
            'nombre': 'Camisa Pro',
            'precio': 25.0,
          }),
          1,
        );
        expect((await env.ops()).single.status, OpStatus.synced);
      });

      test('CASO 1b · descartar la operación rechazada la elimina sin tocar el servidor', () async {
        env.goOffline();
        await productos.update(1, const Producto(nombre: 'X', precio: 1));
        backend.tables['producto']!.remove(1);
        await env.goOnline();

        await env.services.engine.discard((await env.ops()).single.opId);

        expect(await env.ops(), isEmpty);
        await env.services.sync.refreshCounts();
        expect(env.services.sync.attentionCount, 0);
        expect(backend.count('producto'), 1);
      });

      test('CASO 2 · crear una relación cuyo Pedido ya no existe: rechazada ANTES de enviar, sin fila basura', () async {
        env.goOffline();
        await relaciones.create(
          const PedidoProducto(pedidoId: 1, productoId: 1),
        );
        backend.tables['pedido']!.remove(1); // otro cliente borró el pedido

        await env.goOnline();

        final op = (await env.ops()).single;
        expect(op.status, OpStatus.rejected);
        expect(op.reason, OpReason.parentMissing);
        expect(op.detail, contains('Pedido 1 ya no existe'));
        expect(
          writes(backend),
          isEmpty,
          reason: 'el POST ni se envió (el backend lo habría ignorado con 200 y null)',
        );
        expect(backend.count('pedidoproducto'), 0);
      });

      test(
        'CASO 2b · si el Producto referenciado ya no existe, se dice cuál',
        () async {
          env.goOffline();
          await relaciones.create(
            const PedidoProducto(pedidoId: 1, productoId: 2),
          );
          backend.tables['producto']!.remove(2);

          await env.goOnline();

          expect(
            (await env.ops()).single.detail,
            contains('Producto 2 ya no existe'),
          );
          expect(backend.count('pedidoproducto'), 0);
        },
      );

      test('CASO 3 · delete de algo que otro modificó: BLOQUEADO; "Eliminar igualmente" lo borra a conciencia', () async {
        env.goOffline();
        await productos.delete(1);
        backend.tables['producto']![1]!['precio'] =
            30.0; // otro cliente lo modificó

        await env.goOnline();

        final op = (await env.ops()).single;
        expect(op.status, OpStatus.rejected);
        expect(op.reason, OpReason.modifiedRemotely);
        expect(op.detail, contains('no se eliminó'));
        expect(
          op.detail,
          contains('Precio: 30.0'),
          reason: 'muestra los valores actuales',
        );
        expect(
          backend.tables['producto']!.containsKey(1),
          isTrue,
          reason: 'el servidor gana: sigue existiendo',
        );
        expect(writes(backend), isEmpty);
        expect(
          (await env.store.readRecord('producto', 1))!['precio'],
          30.0,
          reason: 'la caché refleja lo del servidor',
        );
        expect((await productos.list()).items.map((e) => e.id), [
          1,
          2,
        ], reason: 'vuelve a verse');

        await env.services.engine.applyAnyway(op.opId);
        await env.services.sync.syncNow();

        expect(backend.tables['producto']!.containsKey(1), isFalse);
        expect((await env.ops()).single.status, OpStatus.synced);
      });

      test('CASO 3b · delete de algo que otro ya borró: queda sincronizada (la intención se cumplió), no rechazada', () async {
        env.goOffline();
        await productos.delete(2);
        backend.tables['producto']!.remove(2);

        await env.goOnline();

        final op = (await env.ops()).single;
        expect(op.status, OpStatus.synced);
        expect(op.reason, OpReason.alreadyApplied);
        expect(op.detail, contains('Ya estaba eliminado'));
        expect(writes(backend), isEmpty, reason: 'no hace falta enviar nada');
      });

      test('update de algo que otro modificó: rechazada (servidor gana) y "Aplicar igualmente" la aplica', () async {
        env.goOffline();
        await productos.update(1, const Producto(nombre: 'Camisa', precio: 25));
        backend.tables['producto']![1]!['precio'] = 30.0;

        await env.goOnline();

        final op = (await env.ops()).single;
        expect(op.reason, OpReason.modifiedRemotely);
        expect(op.detail, contains('Ahora es'));
        expect(op.detail, contains('Tu cambio era'));
        expect(backend.tables['producto']![1]!['precio'], 30.0);

        await env.services.engine.applyAnyway(op.opId);
        await env.services.sync.syncNow();

        expect(backend.tables['producto']![1]!['precio'], 25.0);
        expect((await env.ops()).single.status, OpStatus.synced);
      });

      test('update sin cambios ajenos: se aplica normalmente', () async {
        env.goOffline();
        await productos.update(
          1,
          const Producto(nombre: 'Camisa Pro', precio: 25),
        );

        await env.goOnline();

        expect(backend.tables['producto']![1]!['nombre'], 'Camisa Pro');
        expect((await env.ops()).single.status, OpStatus.synced);
        expect((await env.ops()).single.reason, OpReason.none);
      });

      test('update cuyo resultado el servidor ya tiene (otro cliente hizo lo mismo): sincronizada, no es conflicto', () async {
        env.goOffline();
        await productos.update(
          1,
          const Producto(nombre: 'Camisa Pro', precio: 25),
        );
        backend.tables['producto']![1]!
          ..['nombre'] = 'Camisa Pro'
          ..['precio'] = 25.0;

        await env.goOnline();

        final op = (await env.ops()).single;
        expect(op.status, OpStatus.synced);
        expect(op.reason, OpReason.alreadyApplied);
      });

      test('borrar un Pedido en el servidor elimina sus relaciones (cascada): un update pendiente sobre ellas se rechaza', () async {
        final creada = await relaciones.create(
          const PedidoProducto(pedidoId: 1, productoId: 1),
        );
        env.goOffline();
        await relaciones.update(
          creada.entity!.id!,
          const PedidoProducto(pedidoId: 1, productoId: 2),
        );
        backend.tables['pedido']!.remove(1);
        backend.tables['pedidoproducto']!.clear(); // cascada del servidor

        await env.goOnline();

        final op = (await env.ops()).lastWhere((o) => o.kind == OpKind.update);
        expect(op.status, OpStatus.rejected);
        expect(op.reason, OpReason.deletedRemotely);
      });
    },
  );

  group('excepciones de la ficha', () {
    test('FALLO DE SINCRONIZACIÓN: un 500 persistente se reintenta 3 veces y luego pide reintento manual; el resto de la cola sigue', () async {
      env.goOffline();
      await productos.update(
        1,
        const Producto(nombre: 'Camisa Pro', precio: 25),
      );
      await pedidos.create(const Pedido(fecha: 'independiente'));
      backend.failAlwaysOf['PUT'] = 500;

      await env.goOnline(); // intento 1
      await env.services.sync.syncNow(); // intento 2
      await env.services.sync.syncNow(); // intento 3
      await env.services.sync.syncNow(); // ya no reintenta solo

      final ops = await env.ops();
      final update = ops.firstWhere((o) => o.kind == OpKind.update);
      final create = ops.firstWhere((o) => o.kind == OpKind.create);
      expect(update.status, OpStatus.failed);
      expect(update.attempts, 3);
      expect(update.reason, OpReason.transient);
      expect(update.detail, contains('error interno'));
      expect(update.detail, contains('reintentos automáticos'));
      expect(
        create.status,
        OpStatus.synced,
        reason: 'un fallo no bloquea las operaciones independientes',
      );
      expect(
        backend.tables['producto']![1]!['nombre'],
        'Camisa',
        reason: 'el dato guardado no se alteró',
      );
      expect(
        backend.log
            .where((l) => l.startsWith('PUT') && l.contains('500 persistente'))
            .length,
        3,
      );
      expect(env.services.sync.attentionCount, 1);

      // El servidor se recupera y el usuario elige "Reintentar".
      backend.failAlwaysOf.clear();
      await env.services.engine.retry(update.opId);
      await env.services.sync.syncNow();

      expect(backend.tables['producto']![1]!['nombre'], 'Camisa Pro');
      expect((await env.store.opById(update.opId))!.status, OpStatus.synced);
    });

    test('PÉRDIDA DE CONEXIÓN A MITAD: se sincroniza lo que se pudo, el resto queda pendiente y al volver se completa sin duplicar', () async {
      env.goOffline();
      for (final n in ['A', 'B', 'C']) {
        await productos.create(Producto(nombre: n, precio: 1));
      }
      backend
        ..offline = false
        ..goOfflineAfter =
            3; // A (GET+POST) y el GET de B; el POST de B ya no llega
      env.monitor.setOnline(true);
      await env.services.sync.syncNow();

      final ops = await env.ops();
      expect(ops[0].status, OpStatus.synced, reason: 'A se envió');
      expect(
        ops[1].status,
        OpStatus.uncertain,
        reason: 'B: se cortó justo al enviarla; no se sabe si llegó',
      );
      expect(ops[2].status, OpStatus.pending, reason: 'C ni se intentó');
      expect(env.services.sync.lastReport!.interrupted, isTrue);
      expect(env.services.sync.online, isFalse);
      expect(countWhere(backend, 'producto', {'nombre': 'A'}), 1);
      expect(countWhere(backend, 'producto', {'nombre': 'B'}), 0);

      await env.goOnline(); // vuelve la conexión: se reanuda sola

      expect(
        (await env.ops()).every((o) => o.status == OpStatus.synced),
        isTrue,
      );
      for (final n in ['A', 'B', 'C']) {
        expect(
          countWhere(backend, 'producto', {'nombre': n}),
          1,
          reason: '"$n" exactamente una vez',
        );
      }
      expect(backend.count('producto'), 5);
    });

    test('RECHAZO DEL SERVIDOR: un 400 deja la operación rechazada con su motivo y sus datos; las demás siguen', () async {
      backend.rejectBody = (table, body) => body['nombre'] == 'MALO';
      env.goOffline();
      await productos.create(const Producto(nombre: 'MALO', precio: 1));
      await productos.create(const Producto(nombre: 'Bueno', precio: 2));

      await env.goOnline();

      final ops = await env.ops();
      expect(ops[0].status, OpStatus.rejected);
      expect(ops[0].reason, OpReason.serverRejected);
      expect(ops[0].detail, contains('HTTP 400'));
      expect(
        ops[0].values['nombre'],
        'MALO',
        reason: 'los datos se conservan para que el usuario decida',
      );
      expect(ops[1].status, OpStatus.synced);
      expect(countWhere(backend, 'producto', {'nombre': 'MALO'}), 0);
      expect(countWhere(backend, 'producto', {'nombre': 'Bueno'}), 1);
      expect(env.services.sync.attentionCount, 1);

      await env.services.engine.discard(ops[0].opId);
      await env.services.sync.refreshCounts();
      expect(env.services.sync.attentionCount, 0);
    });

    test('CONFLICTO LOCAL/REMOTO visible para el usuario: el estado y el motivo quedan en la cola', () async {
      env.goOffline();
      await productos.update(1, const Producto(nombre: 'Local', precio: 1));
      backend.tables['producto']![1]!['nombre'] = 'Remoto';

      await env.goOnline();

      final op = (await env.ops()).single;
      expect(op.needsAttention, isTrue);
      expect(op.detail, contains('Remoto'));
      expect(op.detail, contains('Local'));
    });
  });
}
