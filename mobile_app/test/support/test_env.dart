import 'package:gestion_movil/app_scope.dart';
import 'package:gestion_movil/data/api_client.dart';
import 'package:gestion_movil/data/connectivity_monitor.dart';
import 'package:gestion_movil/data/entity_gateway.dart';
import 'package:gestion_movil/data/local/local_store.dart';
import 'package:gestion_movil/data/voice/speech_input.dart';
import 'package:gestion_movil/domain/entity_module.dart';
import 'package:gestion_movil/domain/pending_op.dart';
import 'package:http/http.dart' as http;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'fake_backend.dart';
import 'memory_local_store.dart';

/// Pila completa de la app para tests: backend simulado + almacenamiento local + conectividad
/// controlable + motor de sincronización. Sin timers (`retryEvery: null`).
class TestEnv {
  TestEnv._(this.backend, this.store, this.monitor, this.services);

  final FakeBackend backend;
  final LocalStore store;
  final ManualConnectivityMonitor monitor;
  final AppServices services;

  /// SQLite real (base en memoria aislada por prueba) — para tests de datos y sincronización.
  static Future<TestEnv> sqlite({
    bool online = true,
    FakeBackend? backend,
    String? path,
    http.Client Function(FakeBackend)? clientFor,
    SpeechInput? speech,
  }) async {
    sqfliteFfiInit();
    final store = await LocalStore.open(
      path: path ?? inMemoryDatabasePath,
      factory: databaseFactoryFfi,
      singleInstance: false,
    );
    return _build(
      store,
      online: online,
      backend: backend,
      clientFor: clientFor,
      speech: speech,
    );
  }

  /// Almacén en memoria — para tests de **widgets** (ver [MemoryLocalStore]).
  static Future<TestEnv> memory({
    bool online = true,
    FakeBackend? backend,
    SpeechInput? speech,
  }) async => _build(
    MemoryLocalStore(),
    online: online,
    backend: backend,
    speech: speech,
  );

  static Future<TestEnv> _build(
    LocalStore store, {
    required bool online,
    FakeBackend? backend,
    http.Client Function(FakeBackend)? clientFor,
    SpeechInput? speech,
  }) async {
    final fake = backend ?? FakeBackend();
    final monitor = ManualConnectivityMonitor(online: online);
    final api = ApiClient(
      client: clientFor?.call(fake) ?? fake.client,
      baseUrl: 'http://fake/api',
    );
    final services = AppServices(
      api: api,
      store: store,
      monitor: monitor,
      retryEvery: null,
      speech: speech,
    );
    await services.sync.start();
    return TestEnv._(fake, store, monitor, services);
  }

  EntityGateway gateway(EntityModule module) => services.repositoryFor(module);

  /// Pasa a "sin conexión": el monitor lo declara Y el backend deja de responder.
  void goOffline() {
    monitor.setOnline(false);
    backend.offline = true;
  }

  /// Vuelve la conexión: el controlador sincroniza solo (sin llamar a `syncNow`); se espera a que termine.
  Future<void> goOnline() async {
    backend.offline = false;
    monitor.setOnline(true);
    await services.sync.syncNow();
  }

  Future<List<PendingOp>> ops() => store.allOps();

  Future<PendingOp> opOf(OpKind kind, {String? module}) async =>
      (await ops()).lastWhere(
        (o) => o.kind == kind && (module == null || o.module == module),
      );

  Future<void> dispose() async {
    await services.sync.whenIdle();
    services.sync.dispose();
    await store.close();
  }
}
