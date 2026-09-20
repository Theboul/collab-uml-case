import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/data/local/local_store.dart';
import 'package:gestion_movil/domain/pending_op.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

/// Almacenamiento local con SQLite REAL (sqflite_common_ffi): caché del servidor y cola de operaciones.
void main() {
  late LocalStore store;

  Future<LocalStore> openMemory() {
    sqfliteFfiInit();
    return LocalStore.open(
      path: inMemoryDatabasePath,
      factory: databaseFactoryFfi,
      singleInstance: false,
    );
  }

  PendingOp op(
    String module,
    OpKind kind,
    int target,
    Map<String, Object?> values, {
    Map<String, Object?>? base,
  }) => PendingOp(
    opId: newOpId(),
    module: module,
    kind: kind,
    targetId: target,
    values: values,
    base: base,
    createdAt: 1,
    updatedAt: 1,
  );

  setUp(() async => store = await openMemory());
  tearDown(() => store.close());

  group('caché del servidor (lo último cargado de cada entidad)', () {
    test('guarda y lee lo último cargado, por módulo', () async {
      await store.replaceRecords('producto', {
        1: {'nombre': 'Camisa', 'precio': 19.9},
        2: {'nombre': 'Zapato', 'precio': 40.0},
      });
      await store.replaceRecords('pedido', {
        1: {'fecha': '2026-09-01'},
      });

      final productos = await store.readRecords('producto');
      expect(productos.keys, [1, 2]);
      expect(productos[1], {'nombre': 'Camisa', 'precio': 19.9});
      expect((await store.readRecords('pedido')).length, 1);
    });

    test(
      'un double sigue siendo double tras guardarse (40.0 no vuelve como int)',
      () async {
        await store.upsertRecord('producto', 2, {
          'nombre': 'Zapato',
          'precio': 40.0,
        });
        final precio = (await store.readRecord('producto', 2))!['precio'];
        expect(precio, isA<double>());
        expect(precio, 40.0);
      },
    );

    test(
      'replaceRecords reemplaza: lo que ya no está en el servidor desaparece',
      () async {
        await store.replaceRecords('producto', {
          1: {'nombre': 'A', 'precio': 1.0},
          2: {'nombre': 'B', 'precio': 2.0},
        });
        await store.replaceRecords('producto', {
          2: {'nombre': 'B', 'precio': 2.0},
        });
        expect((await store.readRecords('producto')).keys, [2]);
      },
    );

    test('upsert y remove de un registro', () async {
      await store.upsertRecord('producto', 5, {'nombre': 'X', 'precio': 1.0});
      await store.upsertRecord('producto', 5, {'nombre': 'Y', 'precio': 2.0});
      expect((await store.readRecord('producto', 5))!['nombre'], 'Y');
      await store.removeRecord('producto', 5);
      expect(await store.readRecord('producto', 5), isNull);
    });

    test(
      'borrar en cascada: se van los registros que referencian al padre',
      () async {
        await store.replaceRecords('pedidoproducto', {
          1: {'pedido': 1, 'producto': 1},
          2: {'pedido': 2, 'producto': 1},
        });
        await store.removeRecordsReferencing('pedido', 1);
        expect((await store.readRecords('pedidoproducto')).keys, [2]);
      },
    );
  });

  group('cola de operaciones pendientes', () {
    test('conserva el orden de encolado (FIFO) y asigna seq', () async {
      final a = await store.insertOp(
        op('producto', OpKind.create, -1, {'nombre': 'A', 'precio': 1.0}),
      );
      final b = await store.insertOp(
        op('pedido', OpKind.create, -2, {'fecha': 'f'}),
      );
      final c = await store.insertOp(
        op('producto', OpKind.delete, 3, {'nombre': 'C', 'precio': 3.0}),
      );

      expect(a.seq! < b.seq! && b.seq! < c.seq!, isTrue);
      expect((await store.allOps()).map((o) => o.opId), [
        a.opId,
        b.opId,
        c.opId,
      ]);
    });

    test('guarda todos los campos: tipo, payload, base, estado, motivo, intentos, foto de ids', () async {
      final saved = await store.insertOp(
        op(
          'producto',
          OpKind.update,
          7,
          {'nombre': 'Nuevo', 'precio': 5.0},
          base: {'nombre': 'Viejo', 'precio': 4.5},
        ),
      );
      await store.saveOp(
        saved.copyWith(
          status: OpStatus.uncertain,
          reason: OpReason.transient,
          detail: 'motivo',
          attempts: 2,
          force: true,
          preSendIds: [1, 2, 3],
          resultId: 9,
        ),
      );

      final back = (await store.opById(saved.opId))!;
      expect(back.kind, OpKind.update);
      expect(back.module, 'producto');
      expect(back.targetId, 7);
      expect(back.values, {'nombre': 'Nuevo', 'precio': 5.0});
      expect(back.values['precio'], isA<double>());
      expect(back.base, {'nombre': 'Viejo', 'precio': 4.5});
      expect(back.status, OpStatus.uncertain);
      expect(back.reason, OpReason.transient);
      expect(back.detail, 'motivo');
      expect(back.attempts, 2);
      expect(back.force, isTrue);
      expect(back.preSendIds, [1, 2, 3]);
      expect(back.resultId, 9);
    });

    test('ids temporales: negativos, decrecientes y únicos', () async {
      expect(
        [
          await store.nextTempId(),
          await store.nextTempId(),
          await store.nextTempId(),
        ],
        [-1, -2, -3],
      );
    });

    test('remapTempId sustituye el id temporal por el real en la propia operación y en las referencias', () async {
      await store.insertOp(op('pedido', OpKind.create, -1, {'fecha': 'f'}));
      await store.insertOp(
        op('producto', OpKind.create, -2, {'nombre': 'P', 'precio': 1.0}),
      );
      await store.insertOp(
        op('pedidoproducto', OpKind.create, -3, {'pedido': -1, 'producto': -2}),
      );

      await store.remapTempId('pedido', -1, 10);

      final ops = await store.allOps();
      expect(ops[0].targetId, 10);
      expect(ops[1].targetId, -2, reason: 'otro módulo: no se toca');
      expect(ops[2].values, {'pedido': 10, 'producto': -2});
    });

    test('pruneSynced deja solo las últimas sincronizadas y no toca las pendientes', () async {
      for (var i = 0; i < 5; i++) {
        final saved = await store.insertOp(
          op('pedido', OpKind.create, -i - 1, {'fecha': '$i'}),
        );
        await store.saveOp(saved.copyWith(status: OpStatus.synced));
      }
      final pending = await store.insertOp(
        op('pedido', OpKind.create, -9, {'fecha': 'p'}),
      );

      await store.pruneSynced(keep: 2);

      final left = await store.allOps();
      expect(left.length, 3);
      expect(left.last.opId, pending.opId);
    });

    test('emite un evento cuando cambia la cola o la caché', () async {
      var events = 0;
      final sub = store.changes.listen((_) => events++);
      await store.insertOp(op('pedido', OpKind.create, -1, {'fecha': 'f'}));
      await store.upsertRecord('pedido', 1, {'fecha': 'f'});
      await Future<void>.delayed(Duration.zero);
      await sub.cancel();
      expect(events, 2);
    });
  });

  test('persiste tras cerrar y reabrir el archivo (la app "muere" y vuelve): la cola sobrevive', () async {
    final dir = Directory.systemTemp.createTempSync('gestion_movil_test_');
    final path = '${dir.path}/app.db';
    addTearDown(() => dir.deleteSync(recursive: true));

    final first = await LocalStore.open(
      path: path,
      factory: databaseFactoryFfi,
      singleInstance: false,
    );
    final saved = await first.insertOp(
      op('producto', OpKind.create, await first.nextTempId(), {
        'nombre': 'Offline',
        'precio': 3.5,
      }),
    );
    await first.saveOp(
      saved.copyWith(status: OpStatus.sending, preSendIds: [1, 2]),
    );
    await first.replaceRecords('producto', {
      1: {'nombre': 'Camisa', 'precio': 19.9},
    });
    await first.close();

    final second = await LocalStore.open(
      path: path,
      factory: databaseFactoryFfi,
      singleInstance: false,
    );
    addTearDown(second.close);
    final ops = await second.allOps();

    expect(ops, hasLength(1));
    expect(
      ops.single.status,
      OpStatus.sending,
      reason: 'quedó a mitad de envío',
    );
    expect(ops.single.values, {'nombre': 'Offline', 'precio': 3.5});
    expect(ops.single.preSendIds, [1, 2]);
    expect((await second.readRecords('producto')).keys, [1]);
    expect(
      await second.nextTempId(),
      -2,
      reason: 'el contador de ids temporales también persiste',
    );
  });

  test('newOpId genera UUID v4 únicos', () {
    final ids = {for (var i = 0; i < 200; i++) newOpId()};
    expect(ids, hasLength(200));
    expect(
      ids.every(
        (id) => RegExp(
          r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        ).hasMatch(id),
      ),
      isTrue,
    );
  });
}
