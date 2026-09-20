import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../domain/pending_op.dart';
import '../connectivity_monitor.dart';
import '../local/local_store.dart';
import 'sync_engine.dart';

/// Estado de sincronización que observa la UI, y disparador automático de la sincronización:
/// al recuperar la conexión envía la cola **sin intervención manual**.
class SyncController extends ChangeNotifier {
  SyncController({
    required this.store,
    required this.engine,
    required this.monitor,
    this.retryEvery = const Duration(seconds: 30),
  });

  final LocalStore store;
  final SyncEngine engine;
  final ConnectivityMonitor monitor;

  /// Reintento periódico de lo que quedó pendiente/fallido mientras haya conexión (`null` = sin timer).
  final Duration? retryEvery;

  bool online = false;
  bool syncing = false;

  /// Operaciones esperando enviarse (pendientes, en envío o dudosas).
  int pendingCount = 0;

  /// Operaciones que necesitan una decisión del usuario (rechazadas, fallidas, a revisar).
  int attentionCount = 0;

  /// Sube cada vez que termina una sincronización: las pantallas recargan sus datos.
  int revision = 0;

  SyncReport? lastReport;

  StreamSubscription<bool>? _connectivitySub;
  StreamSubscription<void>? _storeSub;
  Timer? _timer;
  Future<void>? _running;
  bool _rerun = false;
  bool _disposed = false;

  Future<void> start() async {
    online = monitor.isOnline;
    _connectivitySub = monitor.changes.listen((value) {
      online = value;
      notifyListeners();
      if (value) unawaited(syncNow());
    });
    _storeSub = store.changes.listen((_) => unawaited(refreshCounts()));
    final period = retryEvery;
    if (period != null) {
      _timer = Timer.periodic(period, (_) {
        if (online && pendingCount + attentionCount > 0) unawaited(syncNow());
      });
    }
    await refreshCounts();
    if (online) unawaited(syncNow());
  }

  /// Envía la cola ahora. Si ya hay una pasada en curso NO se pierde la petición: la pasada actual
  /// pudo haber leído la cola antes de que llegara lo nuevo, así que al terminar se hace otra.
  /// El futuro devuelto se completa cuando ya no queda ninguna pasada pendiente.
  Future<void> syncNow() {
    final running = _running;
    if (running != null) {
      _rerun = true;
      return running;
    }
    return _running = _runLoop();
  }

  Future<void> _runLoop() async {
    final total = SyncReport();
    try {
      do {
        _rerun = false;
        final report = await _runOnce();
        total.merge(report);
        lastReport = total;
        // Si se cortó la conexión no se insiste: se reanuda sola cuando vuelva (monitor.changes).
        if (report.interrupted) break;
      } while (_rerun && !_disposed);
    } finally {
      _running = null;
    }
  }

  /// Se completa cuando no hay una sincronización en curso.
  Future<void> whenIdle() async {
    while (_running != null) {
      await _running;
    }
  }

  Future<SyncReport> _runOnce() async {
    syncing = true;
    if (!_disposed) notifyListeners();
    try {
      final report = await engine.syncAll();
      if (kDebugMode && !report.isEmpty) debugPrint('[sync] $report');
      return report;
    } finally {
      syncing = false;
      revision++;
      await refreshCounts();
    }
  }

  Future<void> refreshCounts() async {
    if (_disposed) return;
    try {
      final ops = await store.allOps();
      pendingCount = ops
          .where(
            (o) =>
                o.status == OpStatus.pending ||
                o.status == OpStatus.sending ||
                o.status == OpStatus.uncertain,
          )
          .length;
      attentionCount = ops.where((o) => o.needsAttention).length;
    } on Object {
      // La base se cerró mientras se leía (la app o el test terminaron): no hay nada que refrescar.
      if (_disposed) return;
      rethrow;
    }
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _timer?.cancel();
    unawaited(_connectivitySub?.cancel());
    unawaited(_storeSub?.cancel());
    super.dispose();
  }
}
