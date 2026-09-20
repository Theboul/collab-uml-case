import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/data/entity_gateway.dart';
import 'package:gestion_movil/domain/entity_module.dart';
import 'package:gestion_movil/domain/pending_op.dart';
import 'package:gestion_movil/models/producto.dart';

import '../support/fake_backend.dart';
import '../support/sync_helpers.dart';
import '../support/test_env.dart';

/// Deduplicación de creates: el `POST` NO es idempotente (dos `POST` iguales crean dos filas) y el
/// backend no acepta ninguna clave de idempotencia. Si el servidor procesa un create pero la
/// respuesta se pierde, reintentar a ciegas duplicaría la fila.
///
/// Mecanismo: cada operación tiene un UUID propio y un estado persistido (`sending` antes del POST);
/// una operación ambigua (`uncertain`) NO se reenvía: se busca en el servidor un registro con los
/// mismos datos exactos cuyo id no estuviera en la foto de ids previa al envío ni reclamado por otra
/// operación. 0 candidatos → reenviar; 1 → adoptarlo; varios → lo decide el usuario.
void main() {
  late FakeBackend backend;
  late TestEnv env;
  late EntityGateway productos;

  const gorra = {'nombre': 'Gorra', 'precio': 8.5};

  setUp(() async {
    backend = seededBackend();
    env = await TestEnv.sqlite(backend: backend);
    productos = env.gateway(const ProductoModule());
    await primeCache(env, ['producto']);
  });

  tearDown(() => env.dispose());

  int gorras() => countWhere(backend, 'producto', gorra);

  test('ESCENARIO REAL · el servidor procesa el POST, la respuesta se pierde y se reintenta: NO se duplica la fila', () async {
    env.goOffline();
    await productos.create(const Producto(nombre: 'Gorra', precio: 8.5));
    backend.loseResponseOf.add('POST');

    await env
        .goOnline(); // el POST llega y se procesa, pero la respuesta se pierde

    expect(gorras(), 1, reason: 'el servidor SÍ creó el registro');
    var op = (await env.ops()).single;
    expect(
      op.status,
      OpStatus.uncertain,
      reason: 'la app no sabe si llegó: no se da por enviada ni se reenvía',
    );
    expect(op.preSendIds, [
      1,
      2,
    ], reason: 'foto de ids del servidor justo antes del envío');

    await env.goOnline(); // vuelve la conexión: reintento

    op = (await env.ops()).single;
    expect(gorras(), 1, reason: 'NO se duplicó');
    expect(backend.count('producto'), 3);
    expect(op.status, OpStatus.synced);
    expect(op.reason, OpReason.alreadyCreated);
    expect(op.resultId, 3, reason: 'adoptó el registro que ya existía');
    expect(op.detail, contains('no se duplicó'));
    expect(
      backend.log.where((l) => l == 'POST /api/producto').length,
      1,
      reason: 'un solo POST llegó al servidor',
    );
    expect((await productos.list()).items.map((e) => e.id), [1, 2, 3]);
  });

  test('si el POST ni siquiera llegó (petición perdida), el reintento crea el registro UNA vez', () async {
    env.goOffline();
    await productos.create(const Producto(nombre: 'Gorra', precio: 8.5));
    backend.dropRequestOf.add('POST');

    await env.goOnline();
    expect(gorras(), 0, reason: 'nunca llegó');
    expect((await env.ops()).single.status, OpStatus.uncertain);

    await env.goOnline();

    expect(gorras(), 1);
    expect((await env.ops()).single.status, OpStatus.synced);
    expect(
      (await env.ops()).single.reason,
      OpReason.none,
      reason: 'se creó normalmente, no se adoptó nada',
    );
  });

  test('dos creates legítimamente idénticos: si se pierde la respuesta del primero, quedan exactamente DOS filas (ni 1 ni 3)', () async {
    env.goOffline();
    await productos.create(const Producto(nombre: 'Gorra', precio: 8.5));
    await productos.create(const Producto(nombre: 'Gorra', precio: 8.5));
    backend.loseResponseOf.add('POST');

    await env.goOnline(); // el primero se procesa y pierde su respuesta; se corta la sincronización
    expect(gorras(), 1);

    await env.goOnline(); // el primero se adopta; el segundo se crea

    expect(gorras(), 2);
    expect((await env.ops()).map((o) => o.status), [
      OpStatus.synced,
      OpStatus.synced,
    ]);
    expect((await env.ops()).first.reason, OpReason.alreadyCreated);
    expect(
      backend.log.where((l) => l == 'POST /api/producto').length,
      2,
      reason: 'un POST por cada create legítimo',
    );
  });

  test('otro cliente creó un registro IDÉNTICO y además se perdió la respuesta: no se puede saber cuál es el nuestro → revisión del usuario, sin reenviar', () async {
    env.goOffline();
    await productos.create(const Producto(nombre: 'Gorra', precio: 8.5));
    backend.loseResponseOf.add('POST');
    await env.goOnline(); // nuestro POST se procesó, respuesta perdida
    backend.insert('producto', Map.of(gorra)); // otro cliente crea uno idéntico
    expect(gorras(), 2);

    await env.goOnline();

    final op = (await env.ops()).single;
    expect(op.status, OpStatus.needsReview);
    expect(op.reason, OpReason.duplicatesFound);
    expect(op.detail, contains('2 registros idénticos'));
    expect(op.detail, contains('No se reenvió'));
    expect(gorras(), 2, reason: 'no se reenvió nada: no hay duplicado nuevo');
    expect(backend.log.where((l) => l == 'POST /api/producto').length, 1);
    expect(env.services.sync.attentionCount, 1);

    // El usuario decide "Reenviar igualmente" (acepta el posible duplicado).
    await env.services.engine.resendAnyway(op.opId);
    await env.services.sync.syncNow();

    expect(gorras(), 3);
    expect((await env.ops()).single.status, OpStatus.synced);
  });

  test('la misma situación, pero el usuario elige "Descartar": no se crea nada más', () async {
    env.goOffline();
    await productos.create(const Producto(nombre: 'Gorra', precio: 8.5));
    backend.loseResponseOf.add('POST');
    await env.goOnline();
    backend.insert('producto', Map.of(gorra));
    await env.goOnline();

    await env.services.engine.discard((await env.ops()).single.opId);
    await env.services.sync.syncNow();

    expect(gorras(), 2);
    expect(await env.ops(), isEmpty);
  });

  test('el servidor guarda y luego responde 500: el create queda ambiguo y se ADOPTA, no se duplica', () async {
    env.goOffline();
    await productos.create(const Producto(nombre: 'Gorra', precio: 8.5));
    backend
      ..offline = false
      ..failAfterProcessingOf['POST'] = 500;

    // Pasada 1 (conducida a mano con el motor): el POST se procesa pero llega un 500.
    await env.services.engine.syncAll();
    var op = (await env.ops()).single;
    expect(op.status, OpStatus.uncertain);
    expect(op.reason, OpReason.transient);
    expect(op.detail, contains('se verificará antes de reintentar'));
    expect(gorras(), 1);

    // Pasada 2: no reenvía; busca y adopta.
    await env.services.engine.syncAll();

    op = (await env.ops()).single;
    expect(op.status, OpStatus.synced);
    expect(op.reason, OpReason.alreadyCreated);
    expect(gorras(), 1);
    expect(backend.log.where((l) => l == 'POST /api/producto').length, 1);
  });

  test('la app MUERE a mitad del envío (estado "sending" persistido): al arrancar de nuevo no duplica', () async {
    final dir = Directory.systemTemp.createTempSync('gestion_movil_dedup_');
    addTearDown(() => dir.deleteSync(recursive: true));
    final path = '${dir.path}/app.db';

    final first = await TestEnv.sqlite(
      path: path,
      backend: backend,
      online: false,
    );
    await first
        .gateway(const ProductoModule())
        .create(const Producto(nombre: 'Gorra', precio: 8.5));
    final op = (await first.ops()).single;
    // La app alcanzó a persistir "sending" + foto de ids, envió el POST, el servidor lo procesó… y la app murió.
    await first.store.saveOp(
      op.copyWith(status: OpStatus.sending, preSendIds: [1, 2]),
    );
    backend.insert('producto', Map.of(gorra));
    await first.dispose();

    final second = await TestEnv.sqlite(
      path: path,
      backend: backend,
      online: true,
    );
    addTearDown(second.dispose);
    await second.services.sync.syncNow();

    final recovered = (await second.ops()).single;
    expect(recovered.status, OpStatus.synced);
    expect(recovered.reason, OpReason.alreadyCreated);
    expect(
      gorras(),
      1,
      reason: 'el registro que ya había creado el servidor se adoptó',
    );
    expect(
      backend.log.where((l) => l == 'POST /api/producto'),
      isEmpty,
      reason: 'la app no reenvió el POST',
    );
  });

  test('un UPDATE cuya respuesta se perdió se reintenta sin falso conflicto (PUT es idempotente)', () async {
    env.goOffline();
    await productos.update(1, const Producto(nombre: 'Camisa Pro', precio: 25));
    backend.loseResponseOf.add('PUT');

    await env.goOnline();
    expect(
      backend.tables['producto']![1]!['nombre'],
      'Camisa Pro',
      reason: 'el servidor lo aplicó',
    );
    expect((await env.ops()).single.status, OpStatus.pending);

    await env.goOnline();

    final op = (await env.ops()).single;
    expect(op.status, OpStatus.synced);
    expect(
      op.reason,
      OpReason.alreadyApplied,
      reason: 'los valores ya coinciden: no es un conflicto ajeno',
    );
  });

  test('un DELETE cuya respuesta se perdió se reintenta sin rechazo (DELETE es idempotente)', () async {
    env.goOffline();
    await productos.delete(2);
    backend.loseResponseOf.add('DELETE');

    await env.goOnline();
    expect(backend.tables['producto']!.containsKey(2), isFalse);

    await env.goOnline();

    final op = (await env.ops()).single;
    expect(op.status, OpStatus.synced);
    expect(op.reason, OpReason.alreadyApplied);
  });
}
