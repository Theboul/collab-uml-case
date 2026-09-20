import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';

/// Estado de conexión "efectivo" de la app: hay interfaz de red **y** el backend responde.
///
/// `connectivity_plus` solo dice si hay una interfaz (WiFi, datos…); no garantiza que el backend
/// sea alcanzable, así que [DeviceConnectivityMonitor] lo combina con una sonda al backend.
abstract class ConnectivityMonitor {
  /// ¿Se puede hablar con el backend ahora mismo?
  bool get isOnline;

  /// Emite solo cuando [isOnline] cambia.
  Stream<bool> get changes;

  /// Vuelve a comprobar y devuelve el estado.
  Future<bool> refresh();

  /// Una petición real falló por red: se pasa a "sin conexión" sin esperar a la sonda.
  void reportOffline();

  Future<void> dispose();
}

/// Implementación real: `connectivity_plus` + sonda al backend, con reintento periódico mientras
/// haya interfaz pero el backend no responda.
class DeviceConnectivityMonitor implements ConnectivityMonitor {
  DeviceConnectivityMonitor({
    required this._probe,
    Connectivity? connectivity,
    this.retryEvery = const Duration(seconds: 5),
  }) : _connectivity = connectivity ?? Connectivity();

  final Future<bool> Function() _probe;
  final Connectivity _connectivity;
  final Duration retryEvery;

  final StreamController<bool> _changes = StreamController<bool>.broadcast();
  StreamSubscription<List<ConnectivityResult>>? _subscription;
  Timer? _retryTimer;
  bool _online = false;
  bool _interfaceUp = false;

  @override
  bool get isOnline => _online;

  @override
  Stream<bool> get changes => _changes.stream;

  /// Empieza a escuchar. Hace la comprobación inicial.
  Future<void> start() async {
    _subscription = _connectivity.onConnectivityChanged.listen(
      _onInterfaceChanged,
    );
    _onInterfaceChanged(await _connectivity.checkConnectivity());
    _retryTimer = Timer.periodic(retryEvery, (_) {
      if (_interfaceUp && !_online) refresh();
    });
  }

  Future<void> _onInterfaceChanged(List<ConnectivityResult> results) async {
    _interfaceUp = results.any((r) => r != ConnectivityResult.none);
    if (!_interfaceUp) {
      _set(false);
      return;
    }
    await refresh();
  }

  @override
  Future<bool> refresh() async {
    if (!_interfaceUp) {
      _set(false);
      return false;
    }
    _set(await _probe());
    return _online;
  }

  @override
  void reportOffline() => _set(false);

  void _set(bool value) {
    if (value == _online) return;
    _online = value;
    if (!_changes.isClosed) _changes.add(value);
  }

  @override
  Future<void> dispose() async {
    _retryTimer?.cancel();
    await _subscription?.cancel();
    await _changes.close();
  }
}

/// Monitor controlable a mano, para tests.
class ManualConnectivityMonitor implements ConnectivityMonitor {
  ManualConnectivityMonitor({this._online = true});

  final StreamController<bool> _changes = StreamController<bool>.broadcast(
    sync: true,
  );
  bool _online;

  @override
  bool get isOnline => _online;

  @override
  Stream<bool> get changes => _changes.stream;

  void setOnline(bool value) {
    if (value == _online) return;
    _online = value;
    _changes.add(value);
  }

  @override
  Future<bool> refresh() async => _online;

  @override
  void reportOffline() => setOnline(false);

  @override
  Future<void> dispose() => _changes.close();
}
