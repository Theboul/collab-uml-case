import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/data/entity_gateway.dart';
import 'package:gestion_movil/domain/entity_module.dart';
import 'package:gestion_movil/domain/pending_op.dart';
import 'package:gestion_movil/models/pedido.dart';
import 'package:gestion_movil/models/producto.dart';

import '../support/fake_backend.dart';
import '../support/sync_helpers.dart';
import '../support/test_env.dart';

/// El disparador: al recuperar la conexión la cola se envía SOLA, sin intervención manual.
void main() {
  late FakeBackend backend;
  late TestEnv env;
  late EntityGateway productos;

  setUp(() async {
    backend = seededBackend();
    env = await TestEnv.sqlite(backend: backend);
    productos = env.gateway(const ProductoModule());
    await primeCache(env, ['producto', 'pedido']);
  });

  tearDown(() => env.dispose());

  test(
    'SINCRONIZA SOLA al recuperar la conexión: nadie llama a syncNow',
    () async {
      env.goOffline();
      await productos.create(const Producto(nombre: 'Gorra', precio: 8.5));
      await productos.update(
        1,
        const Producto(nombre: 'Camisa Pro', precio: 25),
      );
      await env.services.sync.refreshCounts();
      expect(env.services.sync.pendingCount, 2);
      expect(env.services.sync.online, isFalse);

      // Solo vuelve la red. No se llama a syncNow() ni a nada de la sincronización.
      backend.offline = false;
      env.monitor.setOnline(true);

      await waitUntil(
        () =>
            backend.count('producto') == 3 &&
            env.services.sync.pendingCount == 0,
        reason: 'la app no sincronizó sola tras recuperar la conexión',
      );
      expect(backend.tables['producto']![1]!['nombre'], 'Camisa Pro');
      expect(env.services.sync.online, isTrue);
      expect(
        (await env.ops()).every((o) => o.status == OpStatus.synced),
        isTrue,
      );
    },
  );

  test('mientras no hay conexión no se envía nada, aunque se hagan más operaciones', () async {
    env.goOffline();
    await productos.create(const Producto(nombre: 'A', precio: 1));
    await productos.create(const Producto(nombre: 'B', precio: 2));
    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(writes(backend), isEmpty);
    expect(backend.count('producto'), 2);
    expect(
      (await env.ops()).every((o) => o.status == OpStatus.pending),
      isTrue,
    );
  });

  test('cada pasada de sincronización sube la revisión (las pantallas recargan) y actualiza los contadores', () async {
    final before = env.services.sync.revision;
    env.goOffline();
    await productos.create(const Producto(nombre: 'A', precio: 1));

    await env.goOnline();

    expect(env.services.sync.revision, greaterThan(before));
    expect(env.services.sync.syncing, isFalse);
    expect(env.services.sync.lastReport!.synced, 1);
  });

  test('las operaciones que requieren atención se cuentan aparte de las pendientes', () async {
    backend.rejectBody = (table, body) => body['nombre'] == 'MALO';
    env.goOffline();
    await productos.create(const Producto(nombre: 'MALO', precio: 1));
    await productos.create(const Producto(nombre: 'OK', precio: 1));

    await env.goOnline();

    expect(env.services.sync.pendingCount, 0);
    expect(env.services.sync.attentionCount, 1);
  });

  test('la conexión se corta y vuelve varias veces: cada registro llega exactamente una vez', () async {
    env.goOffline();
    await productos.create(const Producto(nombre: 'Uno', precio: 1));
    await env.goOnline();

    env.goOffline();
    await productos.create(const Producto(nombre: 'Dos', precio: 2));
    await productos.create(const Producto(nombre: 'Tres', precio: 3));
    await env.goOnline();

    env.goOffline();
    await env.goOnline(); // sin nada pendiente: no debe reenviar nada

    for (final n in ['Uno', 'Dos', 'Tres']) {
      expect(
        countWhere(backend, 'producto', {'nombre': n}),
        1,
        reason: '"$n" exactamente una vez',
      );
    }
    expect(backend.count('producto'), 5);
    expect(
      writes(backend).length,
      3,
      reason: 'un POST por operación, ninguno repetido',
    );
  });

  test('un monitor que dice "en línea" pero el servidor no responde: la petición fallida lo pasa a sin conexión', () async {
    backend.offline = true; // el monitor aún cree que hay conexión
    expect(env.monitor.isOnline, isTrue);

    final list = await productos.list();

    expect(list.fromCache, isTrue);
    expect(
      env.monitor.isOnline,
      isFalse,
      reason: 'reportOffline() tras el fallo real de red',
    );
    expect(env.services.sync.online, isFalse);
  });

  test('crear un Pedido y un Producto sin conexión y volver: ambos quedan sincronizados en una sola pasada', () async {
    env.goOffline();
    await env.gateway(const PedidoModule()).create(const Pedido(fecha: 'f'));
    await productos.create(const Producto(nombre: 'X', precio: 1));

    await env.goOnline();

    expect(env.services.sync.lastReport!.synced, 2);
    expect(backend.count('pedido'), 2);
    expect(backend.count('producto'), 3);
  });

  test('una petición de sincronización que llega DURANTE una pasada en curso no se pierde (regresión)', () async {
    // Encontrado con el backend real: la pasada del arranque ya había leído la cola vacía, y
    // syncNow() devolvía esa misma pasada: la operación nueva quedaba sin enviar.
    env.goOffline();
    await productos.create(const Producto(nombre: 'A', precio: 1));
    backend
      ..offline = false
      ..delay = const Duration(
        milliseconds: 40,
      ); // la pasada 1 tarda: da tiempo a que llegue algo nuevo
    env.monitor.setOnline(true); // arranca la pasada 1 (procesa A)
    await Future<void>.delayed(
      const Duration(milliseconds: 15),
    ); // ya leyó la cola: solo A

    await env.store.insertOp(
      PendingOp(
        opId: newOpId(),
        module: 'producto',
        kind: OpKind.create,
        targetId: await env.store.nextTempId(),
        values: {'nombre': 'B', 'precio': 2.0},
        createdAt: 1,
        updatedAt: 1,
      ),
    );
    await env.services.sync
        .syncNow(); // llega durante la pasada 1: debe provocar otra

    expect(countWhere(backend, 'producto', {'nombre': 'A'}), 1);
    expect(
      countWhere(backend, 'producto', {'nombre': 'B'}),
      1,
      reason: 'B no puede quedar sin enviar',
    );
    expect((await env.ops()).every((o) => o.status == OpStatus.synced), isTrue);
  });
}
