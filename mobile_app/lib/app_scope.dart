import 'package:flutter/widgets.dart';

import 'data/api_client.dart';
import 'data/connectivity_monitor.dart';
import 'data/entity_gateway.dart';
import 'data/entity_repository.dart';
import 'data/failures.dart';
import 'data/local/local_store.dart';
import 'data/offline_first_repository.dart';
import 'data/sync/sync_controller.dart';
import 'data/sync/sync_engine.dart';
import 'data/voice/speech_input.dart';
import 'data/voice/voice_command_executor.dart';
import 'domain/entity_module.dart';

/// Dependencias de la app: cliente HTTP, almacenamiento local, conectividad, motor de
/// sincronización y un repositorio "offline-first" por entidad.
///
/// Se inyecta con [AppScope] para que los tests puedan sustituir cualquier pieza.
class AppServices {
  AppServices({
    required this.api,
    required this.store,
    required this.monitor,
    Duration? retryEvery = const Duration(seconds: 30),
    SpeechInput? speech,
  }) : speech = speech ?? SpeechToTextInput() {
    final remotes = {
      for (final m in allModules) m.path: EntityRepository(m, api),
    };
    engine = SyncEngine(store: store, remotes: remotes, monitor: monitor);
    _gateways = {
      for (final m in allModules)
        m.path: OfflineFirstRepository(
          module: m,
          remote: remotes[m.path]!,
          store: store,
          monitor: monitor,
          engine: engine,
        ),
    };
    sync = SyncController(
      store: store,
      engine: engine,
      monitor: monitor,
      retryEvery: retryEvery,
    );
  }

  final ApiClient api;
  final LocalStore store;
  final ConnectivityMonitor monitor;
  late final SyncEngine engine;
  late final SyncController sync;
  late final Map<String, EntityGateway> _gateways;

  /// Entrada de voz del asistente (CU14). Requiere red: ver `docs/decisions.md`.
  final SpeechInput speech;

  /// Ejecuta los comandos del asistente contra los MISMOS repositorios que las pantallas manuales.
  late final VoiceCommandExecutor voiceExecutor = VoiceCommandExecutor(
    gatewayFor: repositoryFor,
  );

  EntityGateway repositoryFor(EntityModule module) => _gateways[module.path]!;

  /// Arranque de producción: abre SQLite, empieza a vigilar la conexión y sincroniza lo pendiente.
  static Future<AppServices> bootstrap() async {
    final api = ApiClient();
    final store = await LocalStore.open();
    final monitor = DeviceConnectivityMonitor(
      // Cualquier respuesta HTTP (incluso un error) significa que el backend es alcanzable.
      probe: () async {
        try {
          await api.send('GET', 'producto');
          return true;
        } on AppFailure {
          return false;
        }
      },
    );
    await monitor.start();
    final services = AppServices(api: api, store: store, monitor: monitor);
    await services.sync.start();
    return services;
  }
}

class AppScope extends InheritedWidget {
  const AppScope({super.key, required this.services, required super.child});

  final AppServices services;

  static AppServices of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppScope>();
    assert(scope != null, 'AppScope no encontrado en el árbol de widgets');
    return scope!.services;
  }

  @override
  bool updateShouldNotify(AppScope oldWidget) => services != oldWidget.services;
}
