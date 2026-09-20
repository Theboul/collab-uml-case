import 'dart:async';

import '../domain/entity_module.dart';
import '../domain/entity_values.dart';
import '../domain/field_spec.dart';
import '../domain/pending_op.dart';
import '../models/entity.dart';
import 'connectivity_monitor.dart';
import 'entity_gateway.dart';
import 'entity_repository.dart';
import 'failures.dart';
import 'local/local_store.dart';
import 'sync/sync_engine.dart';

/// Repositorio que la UI usa (CU12 + CU13): combina el servidor, los datos locales y la cola.
///
/// - **Lectura**: con conexión pide al servidor y refresca la caché local; sin conexión (o si se
///   corta) usa la caché. Encima siempre se aplican las operaciones pendientes, para que el usuario
///   vea lo que hizo aunque aún no esté sincronizado.
/// - **Escritura**: se valida con las mismas reglas de siempre (`FieldValidator`), se guarda como
///   operación pendiente y, si hay conexión y la cola está vacía, se ejecuta al momento con el mismo
///   flujo y verificaciones de la sincronización. Si el servidor rechaza, se comporta como en CU12
///   (error en pantalla y nada guardado).
class OfflineFirstRepository implements EntityGateway {
  OfflineFirstRepository({
    required this.module,
    required this._remote,
    required this._store,
    required this._monitor,
    required this._engine,
  });

  @override
  final EntityModule module;

  final EntityRepository _remote;
  final LocalStore _store;
  final ConnectivityMonitor _monitor;
  final SyncEngine _engine;

  static const String _offlineNote =
      'Sin conexión: guardado en este dispositivo, pendiente de sincronizar.';

  // ---- lectura ------------------------------------------------------------------------------

  @override
  Future<ListResult> list() async {
    var fromCache = true;
    if (_monitor.isOnline) {
      try {
        final items = await _remote.list();
        await _store.replaceRecords(module.path, {
          for (final e in items)
            if (e.id != null) e.id!: module.valuesOf(e),
        });
        fromCache = false;
      } on NetworkFailure {
        _monitor.reportOffline();
      }
    }
    final view = await _localView();
    return ListResult(
      view.entities,
      fromCache: fromCache,
      pendingIds: view.pendingIds,
    );
  }

  @override
  Future<Entity> getById(int id) async {
    final view = await _localView();
    final local = view.entities.where((e) => e.id == id).firstOrNull;

    // Lo creado sin conexión o con cambios pendientes se muestra tal como el usuario lo dejó.
    if (id < 0 || view.pendingIds.contains(id)) {
      if (local != null) return local;
      throw NotFoundFailure(module.label, id);
    }

    if (_monitor.isOnline) {
      try {
        final entity = await _remote.getById(id);
        await _store.upsertRecord(module.path, id, module.valuesOf(entity));
        return entity;
      } on NotFoundFailure {
        await _store.removeRecord(module.path, id);
        rethrow;
      } on NetworkFailure {
        _monitor.reportOffline();
      }
    }
    if (local != null) return local;
    throw OfflineMissFailure(module.label, id);
  }

  // ---- escritura ----------------------------------------------------------------------------

  @override
  Future<WriteOutcome> create(Entity entity) async {
    final values = _validated(module.valuesOf(entity));
    final tempId = await _store.nextTempId();
    final op = await _store.insertOp(
      _newOp(OpKind.create, tempId, values, base: null),
    );
    return _dispatch(op, () => module.fromValues(tempId, values));
  }

  @override
  Future<WriteOutcome> update(int id, Entity entity) async {
    final values = _validated(module.valuesOf(entity));
    final ops = await _store.allOps();

    // Un registro creado sin conexión que aún no se sincronizó: se edita su propio create.
    if (id < 0) {
      final create = _opsFor(
        ops,
        id,
      ).where((o) => o.kind == OpKind.create && _editable(o)).firstOrNull;
      if (create == null) throw NotFoundFailure(module.label, id);
      await _store.saveOp(create.copyWith(values: values));
      _kickSync();
      return WriteOutcome(
        WriteStatus.pending,
        entity: module.fromValues(id, values),
        message: _offlineNote,
      );
    }

    // Ya hay un update pendiente del mismo registro: se combinan (se conserva su base).
    final pendingUpdate = _opsFor(ops, id)
        .where((o) => o.kind == OpKind.update && o.status == OpStatus.pending)
        .firstOrNull;
    if (pendingUpdate != null) {
      final merged = pendingUpdate.copyWith(values: values);
      await _store.saveOp(merged);
      return _dispatch(merged, () => module.fromValues(id, values));
    }

    final base = await _store.readRecord(module.path, id);
    final op = await _store.insertOp(
      _newOp(OpKind.update, id, values, base: base),
    );
    return _dispatch(op, () => module.fromValues(id, values));
  }

  @override
  Future<WriteOutcome> delete(int id) async {
    final ops = await _store.allOps();

    // Creado sin conexión y nunca enviado: basta con descartarlo (y lo que dependía de él).
    if (id < 0) {
      final create = _opsFor(
        ops,
        id,
      ).where((o) => o.kind == OpKind.create && _editable(o)).firstOrNull;
      if (create == null) throw NotFoundFailure(module.label, id);
      await _store.deleteOp(create.opId);
      await _rejectDependents(ops, module.path, id);
      return const WriteOutcome(
        WriteStatus.synced,
        message: 'Descartado: nunca había llegado al servidor.',
      );
    }

    final view = await _localView();
    final current = view.entities.where((e) => e.id == id).firstOrNull;
    if (current == null) throw NotFoundFailure(module.label, id);

    // Si había un update pendiente, se descarta y su base pasa al delete.
    final pendingUpdate = _opsFor(ops, id)
        .where((o) => o.kind == OpKind.update && o.status == OpStatus.pending)
        .firstOrNull;
    final base = pendingUpdate != null
        ? pendingUpdate.base
        : await _store.readRecord(module.path, id);
    if (pendingUpdate != null) await _store.deleteOp(pendingUpdate.opId);

    final op = await _store.insertOp(
      _newOp(OpKind.delete, id, module.valuesOf(current), base: base),
    );
    return _dispatch(op, () => current);
  }

  // ---- internos -----------------------------------------------------------------------------

  Map<String, Object?> _validated(Map<String, Object?> values) {
    final errors = EntityValues.validate(module, values);
    if (errors.isNotEmpty) throw InvalidInputFailure(errors);
    return values;
  }

  PendingOp _newOp(
    OpKind kind,
    int targetId,
    Map<String, Object?> values, {
    required Map<String, Object?>? base,
  }) {
    final now = DateTime.now().millisecondsSinceEpoch;
    return PendingOp(
      opId: newOpId(),
      module: module.path,
      kind: kind,
      targetId: targetId,
      values: values,
      base: base,
      createdAt: now,
      updatedAt: now,
    );
  }

  Iterable<PendingOp> _opsFor(List<PendingOp> ops, int id) => ops.where(
    (o) => o.module == module.path && o.targetId == id && o.isActive,
  );

  /// ¿Se puede modificar la operación sin riesgo? (aún no salió hacia el servidor)
  bool _editable(PendingOp op) =>
      op.status == OpStatus.pending || op.status == OpStatus.failed;

  /// Las operaciones que referenciaban un registro temporal descartado se rechazan (con motivo visible).
  Future<void> _rejectDependents(
    List<PendingOp> ops,
    String parentModule,
    int tempId,
  ) async {
    for (final other in ops.where((o) => o.isActive)) {
      final owner = moduleByPath(other.module);
      final refers = owner.fields.any(
        (f) =>
            f.type == FieldType.reference &&
            f.referenceTo == parentModule &&
            other.values[f.name] == tempId,
      );
      if (refers) {
        await _store.saveOp(
          other.copyWith(
            status: OpStatus.rejected,
            reason: OpReason.parentRejected,
            detail: 'El registro del que dependía (creado sin conexión) fue descartado antes de sincronizarse.',
          ),
        );
      }
    }
  }

  void _kickSync() {
    if (_monitor.isOnline) unawaited(_engine.syncAll());
  }

  /// Ejecuta ya la operación si hay conexión y no hay nada delante en la cola; si no, queda pendiente.
  Future<WriteOutcome> _dispatch(PendingOp op, Entity Function() local) async {
    if (!_monitor.isOnline) {
      return WriteOutcome(
        WriteStatus.pending,
        entity: local(),
        message: _offlineNote,
      );
    }
    final ahead = (await _store.activeOps()).any(
      (o) => o.opId != op.opId && (o.seq ?? 0) < (op.seq ?? 0),
    );
    if (ahead) {
      _kickSync();
      return WriteOutcome(
        WriteStatus.pending,
        entity: local(),
        message:
            'Guardado; hay operaciones anteriores por sincronizar primero.',
      );
    }

    final outcome = await _engine.runInteractive(op.opId);
    switch (outcome.status) {
      case OpStatus.synced:
        return WriteOutcome(
          WriteStatus.synced,
          entity: outcome.entity ?? local(),
          message: outcome.detail,
        );
      case OpStatus.rejected || OpStatus.failed:
        // Modo interactivo (como CU12): el error se muestra y no queda nada guardado.
        await _store.deleteOp(op.opId);
        throw outcome.failure ??
            ConflictFailure(
              outcome.detail ?? 'La operación no se pudo aplicar.',
            );
      case OpStatus.uncertain || OpStatus.needsReview:
        return WriteOutcome(
          WriteStatus.pending,
          entity: local(),
          message: outcome.detail,
        );
      case OpStatus.pending || OpStatus.sending:
        return WriteOutcome(
          WriteStatus.pending,
          entity: local(),
          message: _offlineNote,
        );
    }
  }

  /// Datos locales: caché del servidor + operaciones activas aplicadas encima.
  Future<_LocalView> _localView() async {
    final records = await _store.readRecords(module.path);
    final ops = await _store.allOps();
    final map = <int, Map<String, Object?>>{...records};
    final pending = <int>{};

    for (final op in ops.where((o) => o.module == module.path && o.isActive)) {
      pending.add(op.targetId);
      switch (op.kind) {
        case OpKind.create:
          map[op.targetId] = op.values;
        case OpKind.update:
          if (map.containsKey(op.targetId)) map[op.targetId] = op.values;
        case OpKind.delete:
          map.remove(op.targetId);
      }
    }

    // El servidor borra en cascada; la vista local hace lo mismo con los padres borrados pendientes.
    for (final field in module.fields.where(
      (f) => f.type == FieldType.reference,
    )) {
      final deleted = {
        for (final op in ops)
          if (op.isActive &&
              op.kind == OpKind.delete &&
              op.module == field.referenceTo)
            op.targetId,
      };
      map.removeWhere((_, values) => deleted.contains(values[field.name]));
    }

    final ids = map.keys.toList()
      ..sort((a, b) {
        int rank(int id) => id > 0 ? id : (1 << 40) - id;
        return rank(a).compareTo(rank(b));
      });
    return _LocalView([
      for (final id in ids) module.fromValues(id, map[id]!),
    ], pending);
  }
}

class _LocalView {
  const _LocalView(this.entities, this.pendingIds);

  final List<Entity> entities;
  final Set<int> pendingIds;
}
