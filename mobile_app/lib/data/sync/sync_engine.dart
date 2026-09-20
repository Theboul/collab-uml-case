import 'dart:async';

import '../../domain/entity_module.dart';
import '../../domain/entity_values.dart';
import '../../domain/field_spec.dart';
import '../../domain/pending_op.dart';
import '../../models/entity.dart';
import '../connectivity_monitor.dart';
import '../entity_repository.dart';
import '../failures.dart';
import '../local/local_store.dart';

/// Resultado de procesar una operación.
class OpOutcome {
  const OpOutcome(
    this.status, {
    this.reason = OpReason.none,
    this.detail,
    this.entity,
    this.failure,
    this.interrupted = false,
    this.skipped = false,
  });

  final OpStatus status;
  final OpReason reason;
  final String? detail;

  /// Registro resultante (en operaciones sincronizadas).
  final Entity? entity;

  /// Fallo original del servidor (en `failed`): el modo interactivo lo muestra tal cual, como en CU12.
  final AppFailure? failure;

  /// Se cortó la conexión: la sincronización se detiene y se reanuda sola al volver.
  final bool interrupted;

  /// Espera a otra operación (su padre); se deja como está.
  final bool skipped;
}

/// Resumen de una pasada de sincronización.
class SyncReport {
  int synced = 0;
  int rejected = 0;
  int failed = 0;
  int needsReview = 0;
  int uncertain = 0;
  bool interrupted = false;

  bool get isEmpty => synced + rejected + failed + needsReview + uncertain == 0;

  /// Suma otra pasada a este informe (varias pasadas seguidas forman una misma sincronización).
  void merge(SyncReport other) {
    synced += other.synced;
    rejected += other.rejected;
    failed += other.failed;
    needsReview += other.needsReview;
    uncertain += other.uncertain;
    interrupted = other.interrupted; // manda el estado de la última pasada
  }

  @override
  String toString() =>
      'SyncReport(synced: $synced, rejected: $rejected, failed: $failed, '
      'needsReview: $needsReview, uncertain: $uncertain, interrupted: $interrupted)';
}

/// Envía la cola de operaciones al backend real aplicando la **política de conflictos**:
///
/// - **El servidor gana.** Antes de aplicar un update/delete se consulta el registro real y se
///   compara con la instantánea base; si cambió (o ya no existe) la operación se rechaza y sus datos
///   se conservan. Nada se sobrescribe ni se resucita solo.
/// - **Verificación**: crear una relación comprueba antes que los ids existan (el backend los
///   ignoraría con 200 y `null`), y todo envío se verifica (ver `EntityRepository`).
/// - **Orden FIFO y dependencias**: lo que depende de un registro creado offline espera a que este
///   se cree; si se rechaza, sus dependientes se rechazan en cascada.
/// - **Respuesta perdida**: un create en estado ambiguo jamás se reenvía a ciegas (ver
///   [_resolveUncertainCreate]).
class SyncEngine {
  SyncEngine({
    required this.store,
    required this._remotes,
    required this.monitor,
    this.maxAttempts = 3,
  });

  final LocalStore store;
  final ConnectivityMonitor monitor;
  final Map<String, EntityRepository> _remotes;

  /// Intentos automáticos para un fallo transitorio (5xx) antes de pedir reintento manual.
  final int maxAttempts;

  Future<void> _tail = Future.value();

  Future<T> _exclusive<T>(Future<T> Function() action) {
    final completer = Completer<T>();
    _tail = _tail.then((_) async {
      try {
        completer.complete(await action());
      } catch (error, stack) {
        completer.completeError(error, stack);
      }
    });
    return completer.future;
  }

  // ---- API ----------------------------------------------------------------------------------

  /// Procesa la cola en orden. Se detiene en el primer corte de red y deja el resto pendiente.
  Future<SyncReport> syncAll() => _exclusive(() async {
    final report = SyncReport();
    for (final queued in await store.activeOps()) {
      final op = await store.opById(queued.opId);
      if (op == null || !op.isActive) continue;
      if (op.status == OpStatus.needsReview) continue;
      if (op.status == OpStatus.failed && op.attempts >= maxAttempts) continue;

      final outcome = await _process(op);
      if (outcome.skipped) continue;
      switch (outcome.status) {
        case OpStatus.synced:
          report.synced++;
        case OpStatus.rejected:
          report.rejected++;
        case OpStatus.failed:
          report.failed++;
        case OpStatus.needsReview:
          report.needsReview++;
        case OpStatus.uncertain:
          report.uncertain++;
        case OpStatus.pending || OpStatus.sending:
          break;
      }
      if (outcome.interrupted) {
        report.interrupted = true;
        break;
      }
    }
    await store.pruneSynced();
    return report;
  });

  /// Procesa **una** operación ahora (escritura hecha con conexión y cola vacía).
  Future<OpOutcome> runInteractive(String opId) => _exclusive(() async {
    final op = await store.opById(opId);
    if (op == null) return const OpOutcome(OpStatus.synced);
    return _process(op);
  });

  // ---- acciones del usuario sobre operaciones con problemas ---------------------------------

  /// Descartar: la operación se elimina y sus datos se pierden a propósito.
  Future<void> discard(String opId) => store.deleteOp(opId);

  /// Reintentar una operación `failed` (fallo transitorio).
  Future<void> retry(String opId) => _mutate(
    opId,
    (op) => op.copyWith(
      status: OpStatus.pending,
      attempts: 0,
      reason: OpReason.none,
      detail: null,
    ),
  );

  /// "Aplicar igualmente" / "Eliminar igualmente": el usuario acepta pisar el cambio ajeno.
  Future<void> applyAnyway(String opId) => _mutate(
    opId,
    (op) => op.copyWith(
      status: OpStatus.pending,
      force: true,
      attempts: 0,
      reason: OpReason.none,
      detail: null,
    ),
  );

  /// "Reenviar igualmente" un create dudoso (puede duplicar: lo decide el usuario).
  Future<void> resendAnyway(String opId) => applyAnyway(opId);

  /// "Crear como nuevo": un update rechazado porque el registro fue borrado se convierte en un
  /// create explícito (id nuevo). Nunca ocurre solo.
  Future<void> createAsNew(String opId) async {
    final op = await store.opById(opId);
    if (op == null || op.kind != OpKind.update) return;
    final tempId = await store.nextTempId();
    await store.saveOp(
      op.copyWith(
        kind: OpKind.create,
        targetId: tempId,
        base: null,
        status: OpStatus.pending,
        reason: OpReason.none,
        detail: null,
        attempts: 0,
        force: false,
        preSendIds: null,
      ),
    );
  }

  Future<void> _mutate(
    String opId,
    PendingOp Function(PendingOp) change,
  ) async {
    final op = await store.opById(opId);
    if (op != null) await store.saveOp(change(op));
  }

  // ---- procesamiento de una operación -------------------------------------------------------

  Future<OpOutcome> _process(PendingOp queued) async {
    var op = queued;
    // La app murió (o se cortó) mientras se enviaba: un create pasa a ambiguo; el resto se repite.
    if (op.status == OpStatus.sending) {
      op = await _save(
        op.copyWith(
          status: op.kind == OpKind.create
              ? OpStatus.uncertain
              : OpStatus.pending,
        ),
      );
    }
    final module = moduleByPath(op.module);

    try {
      final waiting = await _checkDependencies(op, module);
      if (waiting != null) return waiting;

      return switch (op.kind) {
        OpKind.create => await _create(op, module),
        OpKind.update => await _update(op, module),
        OpKind.delete => await _delete(op, module),
      };
    } on NetworkFailure {
      monitor.reportOffline();
      return OpOutcome(op.status, interrupted: true);
    } on AppFailure catch (failure) {
      // Un error del servidor en una consulta previa (listado, existencia) no tumba la cola:
      // esta operación queda `failed` (reintentable) y las demás siguen.
      final fresh = (await store.opById(op.opId)) ?? op;
      final detail = failure.userMessage;
      await _save(
        fresh.copyWith(
          status:
              fresh.kind == OpKind.create && fresh.status == OpStatus.uncertain
              ? OpStatus.uncertain
              : OpStatus.failed,
          reason: OpReason.transient,
          detail: detail,
          attempts: fresh.attempts + 1,
        ),
      );
      return OpOutcome(
        OpStatus.failed,
        reason: OpReason.transient,
        detail: detail,
        failure: failure,
      );
    }
  }

  /// ¿Depende de algo creado offline que aún no llegó al servidor (o que fue rechazado)?
  Future<OpOutcome?> _checkDependencies(
    PendingOp op,
    EntityModule module,
  ) async {
    final needed = <(String, int)>[
      if (op.kind != OpKind.create && op.targetId < 0) (op.module, op.targetId),
      for (final field in module.fields)
        if (field.type == FieldType.reference &&
            (op.values[field.name] as int? ?? 1) < 0)
          (field.referenceTo!, op.values[field.name]! as int),
    ];
    if (needed.isEmpty) return null;

    final ops = await store.allOps();
    for (final (parentModule, tempId) in needed) {
      final parent = ops
          .where(
            (o) =>
                o.kind == OpKind.create &&
                o.module == parentModule &&
                o.targetId == tempId,
          )
          .firstOrNull;
      if (parent == null || parent.status == OpStatus.rejected) {
        return _reject(
          op,
          OpReason.parentRejected,
          '${moduleByPath(parentModule).label} del que depende (creado sin conexión) fue rechazado o '
          'descartado; esta operación no se aplicó.',
        );
      }
      if (parent.status != OpStatus.synced) {
        return const OpOutcome(OpStatus.pending, skipped: true);
      }
    }
    return null;
  }

  // ---- create -------------------------------------------------------------------------------

  Future<OpOutcome> _create(PendingOp op, EntityModule module) async {
    final repo = _remotes[op.module]!;

    // 1. Los registros referenciados deben existir (el backend ignoraría un id inexistente: 200 + null).
    for (final field in module.fields.where(
      (f) => f.type == FieldType.reference,
    )) {
      final id = op.values[field.name] as int?;
      if (id == null) continue;
      final target = moduleByPath(field.referenceTo!);
      if (!await _remotes[target.path]!.exists(id)) {
        return _reject(
          op,
          OpReason.parentMissing,
          '${target.label} $id ya no existe en el servidor; ${module.label} no se creó.',
        );
      }
    }

    // 2. Estado ambiguo (se perdió la respuesta de un intento anterior): buscar antes de reenviar.
    final serverItems = await repo.list();
    if (op.status == OpStatus.uncertain && !op.force) {
      final resolved = await _resolveUncertainCreate(op, module, serverItems);
      if (resolved != null) return resolved;
    }

    // 3. Foto de ids previa al envío + estado `sending`, persistidos ANTES del POST.
    final sending = await _save(
      op.copyWith(
        status: OpStatus.sending,
        attempts: op.attempts + 1,
        preSendIds: [for (final item in serverItems) ?item.id],
        reason: OpReason.none,
        detail: null,
      ),
    );

    try {
      final saved = await repo.create(module.fromValues(null, op.values));
      return await _markCreated(sending, module, saved);
    } on NetworkFailure {
      // ¿Llegó el POST? No se sabe: ambiguo. No se reenvía a ciegas.
      await _save(sending.copyWith(status: OpStatus.uncertain));
      rethrow;
    } on ServerFailure catch (failure) {
      final saved = await _save(
        sending.copyWith(
          status: OpStatus.uncertain,
          reason: OpReason.transient,
          detail:
              '${failure.userMessage} No se sabe si el servidor llegó a crear el registro; se '
              'verificará antes de reintentar para no duplicarlo.',
        ),
      );
      return OpOutcome(
        saved.status,
        reason: saved.reason,
        detail: saved.detail,
      );
    } on RejectedFailure catch (failure) {
      return _reject(sending, OpReason.serverRejected, failure.userMessage);
    } on InconsistentResultFailure catch (failure) {
      return _reject(sending, OpReason.inconsistent, failure.userMessage);
    }
  }

  /// Un create ambiguo se resuelve **buscando en el servidor**, no reenviando:
  /// candidatos = registros con los mismos datos exactos cuyo id no estaba en la foto previa al
  /// envío ni fue reclamado por otra operación nuestra.
  ///
  /// - 0 candidatos → el POST nunca se aplicó: devuelve `null` (es seguro reenviar).
  /// - 1 candidato  → ya estaba creado: se adopta (no se duplica).
  /// - varios       → otro cliente creó uno idéntico: no se puede saber cuál es el nuestro; lo decide el usuario.
  Future<OpOutcome?> _resolveUncertainCreate(
    PendingOp op,
    EntityModule module,
    List<Entity> serverItems,
  ) async {
    final claimed = {
      for (final other in await store.allOps())
        if (other.module == op.module && other.resultId != null)
          other.resultId!,
    };
    final before = (op.preSendIds ?? const <int>[]).toSet();
    final candidates = serverItems
        .where(
          (e) =>
              e.id != null &&
              !before.contains(e.id) &&
              !claimed.contains(e.id) &&
              EntityValues.same(module, module.valuesOf(e), op.values),
        )
        .toList();

    if (candidates.isEmpty) return null;

    if (candidates.length == 1) {
      return _markCreated(
        op,
        module,
        candidates.single,
        reason: OpReason.alreadyCreated,
        detail:
            'Se perdió la respuesta del servidor, pero el registro ya estaba creado (ID '
            '${candidates.single.id}). Se adoptó; no se duplicó.',
      );
    }

    final ids = candidates.map((e) => e.id).join(', ');
    final saved = await _save(
      op.copyWith(
        status: OpStatus.needsReview,
        reason: OpReason.duplicatesFound,
        detail:
            'No se pudo confirmar si ${module.label} llegó a crearse: hay ${candidates.length} '
            'registros idénticos en el servidor (ID $ids). No se reenvió para no duplicar.',
      ),
    );
    return OpOutcome(saved.status, reason: saved.reason, detail: saved.detail);
  }

  Future<OpOutcome> _markCreated(
    PendingOp op,
    EntityModule module,
    Entity saved, {
    OpReason reason = OpReason.none,
    String? detail,
  }) async {
    final realId = saved.id!;
    final tempId = op.targetId;
    await store.upsertRecord(module.path, realId, module.valuesOf(saved));
    await store.remapTempId(module.path, tempId, realId);
    final fresh = (await store.opById(op.opId)) ?? op;
    await _save(
      fresh.copyWith(
        status: OpStatus.synced,
        resultId: realId,
        targetId: realId,
        reason: reason,
        detail: detail,
      ),
    );
    return OpOutcome(
      OpStatus.synced,
      reason: reason,
      detail: detail,
      entity: saved,
    );
  }

  // ---- update -------------------------------------------------------------------------------

  Future<OpOutcome> _update(PendingOp op, EntityModule module) async {
    final repo = _remotes[op.module]!;
    final id = op.targetId;

    // Estado real del registro (consulta previa: "el servidor gana").
    final Entity remote;
    try {
      remote = await repo.getById(id);
    } on NotFoundFailure {
      return _deletedRemotely(op, module);
    }
    final remoteValues = module.valuesOf(remote);

    // Ya aplicado (p. ej. se perdió la respuesta de un intento anterior): no es un conflicto.
    if (EntityValues.same(module, remoteValues, op.values)) {
      await store.upsertRecord(module.path, id, remoteValues);
      return _synced(
        op,
        OpReason.alreadyApplied,
        'Ya estaba aplicado en el servidor.',
        remote,
      );
    }

    if (!op.force &&
        op.base != null &&
        !EntityValues.same(module, remoteValues, op.base!)) {
      await store.upsertRecord(module.path, id, remoteValues);
      return _reject(
        op,
        OpReason.modifiedRemotely,
        '${module.label} $id fue modificado por otro usuario desde que lo viste; tu cambio no se '
        'aplicó (el servidor gana). Ahora es: ${EntityValues.describe(module, remoteValues)}. '
        'Tu cambio era: ${EntityValues.describe(module, op.values)}.',
      );
    }

    final sending = await _save(
      op.copyWith(status: OpStatus.sending, attempts: op.attempts + 1),
    );
    try {
      final saved = await repo.update(id, module.fromValues(id, op.values));
      await store.upsertRecord(module.path, id, module.valuesOf(saved));
      return await _synced(sending, OpReason.none, null, saved);
    } on NotFoundFailure {
      return _deletedRemotely(sending, module);
    } on RejectedFailure catch (failure) {
      return _reject(sending, OpReason.serverRejected, failure.userMessage);
    } on InconsistentResultFailure catch (failure) {
      return _reject(sending, OpReason.inconsistent, failure.userMessage);
    } on ServerFailure catch (failure) {
      return _fail(sending, failure);
    } on NetworkFailure {
      await _save(
        sending.copyWith(status: OpStatus.pending),
      ); // PUT es idempotente: se repite
      rethrow;
    }
  }

  Future<OpOutcome> _deletedRemotely(PendingOp op, EntityModule module) async {
    await store.removeRecord(module.path, op.targetId);
    await store.removeRecordsReferencing(module.path, op.targetId);
    return _reject(
      op,
      OpReason.deletedRemotely,
      '${module.label} ${op.targetId} fue eliminado por otro usuario; tu cambio '
      '(${EntityValues.describe(module, op.values)}) no se aplicó. Puedes crearlo como nuevo o descartarlo.',
    );
  }

  // ---- delete -------------------------------------------------------------------------------

  Future<OpOutcome> _delete(PendingOp op, EntityModule module) async {
    final repo = _remotes[op.module]!;
    final id = op.targetId;

    final Entity remote;
    try {
      remote = await repo.getById(id);
    } on NotFoundFailure {
      await store.removeRecord(module.path, id);
      await store.removeRecordsReferencing(module.path, id);
      return _synced(
        op,
        OpReason.alreadyApplied,
        'Ya estaba eliminado en el servidor.',
        null,
      );
    }
    final remoteValues = module.valuesOf(remote);

    // Delete bloqueado si alguien más modificó el registro.
    if (!op.force &&
        op.base != null &&
        !EntityValues.same(module, remoteValues, op.base!)) {
      await store.upsertRecord(module.path, id, remoteValues);
      return _reject(
        op,
        OpReason.modifiedRemotely,
        '${module.label} $id fue modificado por otro usuario; no se eliminó (el servidor gana). '
        'Ahora es: ${EntityValues.describe(module, remoteValues)}. Si aun así quieres borrarlo, '
        'elige "Eliminar igualmente".',
      );
    }

    final sending = await _save(
      op.copyWith(status: OpStatus.sending, attempts: op.attempts + 1),
    );
    try {
      await repo.delete(id);
      await store.removeRecord(module.path, id);
      await store.removeRecordsReferencing(module.path, id);
      return await _synced(sending, OpReason.none, null, null);
    } on NotFoundFailure {
      await store.removeRecord(module.path, id);
      return _synced(
        sending,
        OpReason.alreadyApplied,
        'Ya estaba eliminado en el servidor.',
        null,
      );
    } on InconsistentResultFailure catch (failure) {
      return _reject(sending, OpReason.inconsistent, failure.userMessage);
    } on RejectedFailure catch (failure) {
      return _reject(sending, OpReason.serverRejected, failure.userMessage);
    } on ServerFailure catch (failure) {
      return _fail(sending, failure);
    } on NetworkFailure {
      await _save(
        sending.copyWith(status: OpStatus.pending),
      ); // DELETE es idempotente
      rethrow;
    }
  }

  // ---- transiciones de estado ---------------------------------------------------------------

  Future<PendingOp> _save(PendingOp op) async {
    await store.saveOp(op);
    return op;
  }

  Future<OpOutcome> _synced(
    PendingOp op,
    OpReason reason,
    String? detail,
    Entity? entity,
  ) async {
    await _save(
      op.copyWith(status: OpStatus.synced, reason: reason, detail: detail),
    );
    return OpOutcome(
      OpStatus.synced,
      reason: reason,
      detail: detail,
      entity: entity,
    );
  }

  Future<OpOutcome> _reject(
    PendingOp op,
    OpReason reason,
    String detail,
  ) async {
    await _save(
      op.copyWith(status: OpStatus.rejected, reason: reason, detail: detail),
    );
    return OpOutcome(OpStatus.rejected, reason: reason, detail: detail);
  }

  Future<OpOutcome> _fail(PendingOp op, ServerFailure failure) async {
    final detail = op.attempts >= maxAttempts
        ? '${failure.userMessage} Se agotaron los reintentos automáticos.'
        : '${failure.userMessage} Se reintentará.';
    await _save(
      op.copyWith(
        status: OpStatus.failed,
        reason: OpReason.transient,
        detail: detail,
      ),
    );
    return OpOutcome(
      OpStatus.failed,
      reason: OpReason.transient,
      detail: detail,
      failure: failure,
    );
  }
}
