import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/app_scope.dart';
import 'package:gestion_movil/data/api_client.dart';
import 'package:gestion_movil/data/connectivity_monitor.dart';
import 'package:gestion_movil/data/entity_gateway.dart';
import 'package:gestion_movil/data/local/local_store.dart';
import 'package:gestion_movil/domain/entity_module.dart';
import 'package:gestion_movil/domain/pending_op.dart';
import 'package:gestion_movil/models/pedido.dart';
import 'package:gestion_movil/models/pedido_producto.dart';
import 'package:gestion_movil/models/producto.dart';
import 'package:http/http.dart' as http;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

/// CU13 contra el backend Spring REAL (sin mocks del servidor): sincronización, conflictos y la
/// deduplicación de creates cuando se pierde la respuesta de un POST que el servidor SÍ procesó.
///
///     mobile_app\backend_cu10\run-h2.cmd
///     flutter test test_backend/offline_sync_integration_test.dart
void main() {
  late LossyClient lossy;
  late ApiClient
  rawApi; // "otro cliente": habla directo con el servidor, sin la app
  late AppServices services;
  late ManualConnectivityMonitor monitor;
  late LocalStore store;
  late EntityGateway productos;
  late EntityGateway pedidos;
  late EntityGateway relaciones;
  late String tag;

  Future<Map<String, dynamic>> rawCreate(
    String path,
    Map<String, Object?> body,
  ) async {
    final r = await rawApi.send('POST', path, jsonBody: body);
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> rawList(String path) async {
    final r = await rawApi.send('GET', path);
    return (jsonDecode(r.body) as List).cast<Map<String, dynamic>>();
  }

  Future<int> countNamed(String name) async =>
      (await rawList('producto')).where((p) => p['nombre'] == name).length;

  void goOffline() {
    lossy.offline = true;
    monitor.setOnline(false);
  }

  Future<void> goOnline() async {
    lossy.offline = false;
    monitor.setOnline(true);
    await services.sync.syncNow();
  }

  setUpAll(() {
    HttpOverrides.global =
        null; // flutter_test bloquea el HTTP real por defecto
    sqfliteFfiInit();
  });

  setUp(() async {
    tag = 'cu13-${DateTime.now().microsecondsSinceEpoch}';
    lossy = LossyClient(http.Client());
    rawApi = ApiClient();
    try {
      await rawApi.send('GET', 'producto');
    } on Object catch (e) {
      fail(
        'El backend no responde (${e.toString()}). Levántalo con backend_cu10\\run-h2.cmd',
      );
    }
    store = await LocalStore.open(
      path: inMemoryDatabasePath,
      factory: databaseFactoryFfi,
      singleInstance: false,
    );
    monitor = ManualConnectivityMonitor();
    services = AppServices(
      api: ApiClient(client: lossy),
      store: store,
      monitor: monitor,
      retryEvery: null,
    );
    await services.sync.start();
    productos = services.repositoryFor(const ProductoModule());
    pedidos = services.repositoryFor(const PedidoModule());
    relaciones = services.repositoryFor(const PedidoProductoModule());
  });

  tearDown(() async {
    await services.sync.whenIdle();
    services.sync.dispose();
    await store.close();
    // Limpieza: todo lo que crearon estas pruebas lleva el tag (las relaciones caen en cascada).
    for (final p in await rawList('producto')) {
      if ('${p['nombre']}'.startsWith(tag)) {
        await rawApi.send('DELETE', 'producto/${p['id']}');
      }
    }
    for (final p in await rawList('pedido')) {
      if ('${p['fecha']}'.startsWith(tag)) {
        await rawApi.send('DELETE', 'pedido/${p['id']}');
      }
    }
  });

  test('sin conexión: crear, actualizar y eliminar quedan pendientes; al reconectar llegan al servidor REAL', () async {
    final base = await rawCreate('producto', {
      'nombre': '$tag-base',
      'precio': 10.0,
    });
    final doomed = await rawCreate('producto', {
      'nombre': '$tag-borrar',
      'precio': 1.0,
    });
    await productos.list(); // la app "recuerda" lo último cargado

    goOffline();
    await productos.create(Producto(nombre: '$tag-nuevo', precio: 8.5));
    await productos.update(
      base['id'] as int,
      Producto(nombre: '$tag-base-v2', precio: 12.5),
    );
    await productos.delete(doomed['id'] as int);
    await services.sync.refreshCounts();
    expect(services.sync.pendingCount, 3);
    expect(
      await countNamed('$tag-nuevo'),
      0,
      reason: 'sin conexión no llegó nada al servidor real',
    );

    await goOnline();

    expect(await countNamed('$tag-nuevo'), 1);
    expect(await countNamed('$tag-base-v2'), 1);
    expect(await countNamed('$tag-base'), 0);
    expect(await countNamed('$tag-borrar'), 0);
    expect(
      (await store.allOps()).every((o) => o.status == OpStatus.synced),
      isTrue,
    );
    expect(services.sync.pendingCount, 0);
  });

  test('cadena creada sin conexión (Pedido + Producto + relación) llega al servidor con los ids REALES', () async {
    goOffline();
    final pedido = await pedidos.create(Pedido(fecha: '$tag-pedido'));
    final producto = await productos.create(
      Producto(nombre: '$tag-prod', precio: 3),
    );
    await relaciones.create(
      PedidoProducto(
        pedidoId: pedido.entity!.id,
        productoId: producto.entity!.id,
      ),
    );

    await goOnline();

    final realPedido = (await rawList('pedido'))
        .firstWhere((p) => p['fecha'] == '$tag-pedido');
    final realProducto = (await rawList('producto'))
        .firstWhere((p) => p['nombre'] == '$tag-prod');
    final relation = (await rawList('pedidoproducto')).firstWhere((r) {
      int? id(Object? v) => v is Map ? v['id'] as int? : v as int?;
      return id(r['pedido']) == realPedido['id'] &&
          id(r['producto']) == realProducto['id'];
    });
    expect(relation['id'], isA<int>());
    expect(
      (await store.allOps()).every((o) => o.status == OpStatus.synced),
      isTrue,
    );
  });

  test('CONFLICTO: otro cliente modificó el registro mientras estaba offline → rechazada, el servidor gana', () async {
    final p = await rawCreate('producto', {
      'nombre': '$tag-conf',
      'precio': 10.0,
    });
    await productos.list();

    goOffline();
    await productos.update(
      p['id'] as int,
      Producto(nombre: '$tag-conf', precio: 99),
    );
    await rawApi.send(
      'PUT',
      'producto/${p['id']}',
      jsonBody: {'precio': 30.0},
    ); // otro cliente

    await goOnline();

    final op = (await store.allOps()).single;
    expect(op.status, OpStatus.rejected);
    expect(op.reason, OpReason.modifiedRemotely);
    final now = (await rawList('producto'))
        .firstWhere((x) => x['id'] == p['id']);
    expect(
      now['precio'],
      30.0,
      reason: 'el servidor real conserva el cambio del otro cliente',
    );
  });

  test('update de un registro que otro cliente borró: el 500 del servidor real se interpreta como "no existe" y se rechaza', () async {
    final p = await rawCreate('producto', {
      'nombre': '$tag-borrado',
      'precio': 1.0,
    });
    await productos.list();

    goOffline();
    await productos.update(
      p['id'] as int,
      Producto(nombre: '$tag-borrado-v2', precio: 2),
    );
    await rawApi.send('DELETE', 'producto/${p['id']}');

    await goOnline();

    final op = (await store.allOps()).single;
    expect(op.status, OpStatus.rejected);
    expect(op.reason, OpReason.deletedRemotely);
    expect(await countNamed('$tag-borrado-v2'), 0, reason: 'no se recreó nada');
  });

  test('relación cuyo Pedido borró otro cliente: rechazada ANTES de enviar (el backend real la habría ignorado con 200 y null)', () async {
    final pedido = await rawCreate('pedido', {'fecha': '$tag-p'});
    final producto = await rawCreate('producto', {
      'nombre': '$tag-q',
      'precio': 1.0,
    });
    await pedidos.list();
    await productos.list();

    goOffline();
    await relaciones.create(
      PedidoProducto(
        pedidoId: pedido['id'] as int,
        productoId: producto['id'] as int,
      ),
    );
    await rawApi.send('DELETE', 'pedido/${pedido['id']}');
    final before = (await rawList('pedidoproducto')).length;

    await goOnline();

    final op = (await store.allOps()).single;
    expect(op.status, OpStatus.rejected);
    expect(op.reason, OpReason.parentMissing);
    expect(
      (await rawList('pedidoproducto')).length,
      before,
      reason: 'no quedó ninguna fila con relaciones nulas',
    );
  });

  test('DELETE de algo que otro modificó: BLOQUEADO contra el servidor real; el registro sigue existiendo', () async {
    final p = await rawCreate('producto', {
      'nombre': '$tag-del',
      'precio': 5.0,
    });
    await productos.list();

    goOffline();
    await productos.delete(p['id'] as int);
    await rawApi.send('PUT', 'producto/${p['id']}', jsonBody: {'precio': 6.0});

    await goOnline();

    final op = (await store.allOps()).single;
    expect(op.status, OpStatus.rejected);
    expect(op.reason, OpReason.modifiedRemotely);
    expect(await countNamed('$tag-del'), 1, reason: 'no se borró');
  });

  test('DEDUPLICACIÓN con el servidor REAL: procesa el POST, la respuesta se pierde, se reintenta → UNA sola fila', () async {
    goOffline();
    await productos.create(Producto(nombre: '$tag-dup', precio: 7.5));
    lossy.loseResponseOf.add(
      'POST',
    ); // el servidor real procesará el POST; la app no verá la respuesta

    await goOnline();

    expect(
      await countNamed('$tag-dup'),
      1,
      reason: 'el servidor real SÍ creó el registro',
    );
    var op = (await store.allOps()).single;
    expect(op.status, OpStatus.uncertain, reason: 'la app no sabe si llegó');

    await goOnline(); // reintento

    op = (await store.allOps()).single;
    expect(
      await countNamed('$tag-dup'),
      1,
      reason: 'NO se duplicó en el servidor real',
    );
    expect(op.status, OpStatus.synced);
    expect(op.reason, OpReason.alreadyCreated);
    expect(lossy.postsForwarded, 1, reason: 'un único POST llegó al servidor');
  });

  test('sin conexión real (petición perdida): el reintento crea el registro UNA vez', () async {
    goOffline();
    await productos.create(Producto(nombre: '$tag-drop', precio: 1));
    lossy.dropRequestOf.add('POST');

    await goOnline();
    expect(await countNamed('$tag-drop'), 0);

    await goOnline();
    expect(await countNamed('$tag-drop'), 1);
  });
}

/// Cliente HTTP REAL que puede "perder" la conexión: reenvía la petición al servidor de verdad y,
/// según se configure, descarta la petición antes de enviarla o pierde la respuesta después.
class LossyClient extends http.BaseClient {
  LossyClient(this._inner);

  final http.Client _inner;

  /// Toda petición falla como sin conexión (no llega al servidor).
  bool offline = false;

  /// La próxima petición de estos métodos llega al servidor, se procesa, y la respuesta se pierde.
  final Set<String> loseResponseOf = {};

  /// La próxima petición de estos métodos se pierde antes de llegar al servidor.
  final Set<String> dropRequestOf = {};

  int postsForwarded = 0;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    if (offline) throw const SocketException('sin conexión (simulada)');
    if (dropRequestOf.remove(request.method)) {
      throw const SocketException('petición perdida (simulada)');
    }
    if (request.method == 'POST') postsForwarded++;
    final response = await _inner.send(request);
    if (loseResponseOf.remove(request.method)) {
      await response.stream.drain<void>();
      throw const SocketException('respuesta perdida (simulada)');
    }
    return response;
  }
}
