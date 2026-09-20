import 'dart:async';

import 'package:gestion_movil/data/local/local_store.dart';
import 'package:gestion_movil/domain/pending_op.dart';

/// [LocalStore] en memoria, solo para tests de **widgets**: sus futuros se resuelven con microtareas
/// y `pumpAndSettle` puede esperarlos (los de SQLite real no, por el `FakeAsync` de `testWidgets`).
/// Las pruebas de sincronización y de almacenamiento usan SQLite real.
class MemoryLocalStore extends LocalStore {
  final Map<String, Map<int, Map<String, Object?>>> _records = {};
  final List<PendingOp> _ops = [];
  final StreamController<void> _changes = StreamController<void>.broadcast();
  int _nextSeq = 0;
  int _tempId = 0;

  @override
  Stream<void> get changes => _changes.stream;

  void _notify() {
    if (!_changes.isClosed) _changes.add(null);
  }

  @override
  Future<void> close() => _changes.close();

  @override
  Future<void> replaceRecords(
    String module,
    Map<int, Map<String, Object?>> records,
  ) async {
    _records[module] = {
      for (final e in records.entries) e.key: Map.of(e.value),
    };
    _notify();
  }

  @override
  Future<void> upsertRecord(
    String module,
    int id,
    Map<String, Object?> values,
  ) async {
    (_records[module] ??= {})[id] = Map.of(values);
    _notify();
  }

  @override
  Future<void> removeRecord(String module, int id) async {
    _records[module]?.remove(id);
    _notify();
  }

  @override
  Future<Map<int, Map<String, Object?>>> readRecords(String module) async => {
    for (final e in (_records[module] ?? {}).entries) e.key: Map.of(e.value),
  };

  @override
  Future<Map<String, Object?>?> readRecord(String module, int id) async {
    final values = _records[module]?[id];
    return values == null ? null : Map.of(values);
  }

  @override
  Future<int> nextTempId() async => --_tempId;

  @override
  Future<PendingOp> insertOp(PendingOp op) async {
    final saved = PendingOp.fromRow({...op.toRow(), 'seq': ++_nextSeq});
    _ops.add(saved);
    _notify();
    return saved;
  }

  @override
  Future<void> saveOp(PendingOp op) async {
    final i = _ops.indexWhere((o) => o.opId == op.opId);
    if (i >= 0) {
      _ops[i] = PendingOp.fromRow({...op.toRow(), 'seq': _ops[i].seq});
    }
    _notify();
  }

  @override
  Future<void> deleteOp(String opId) async {
    _ops.removeWhere((o) => o.opId == opId);
    _notify();
  }

  @override
  Future<PendingOp?> opById(String opId) async =>
      _ops.where((o) => o.opId == opId).firstOrNull;

  @override
  Future<List<PendingOp>> allOps() async => List.of(_ops);
}
