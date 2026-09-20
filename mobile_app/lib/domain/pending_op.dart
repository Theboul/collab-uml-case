import 'dart:convert';
import 'dart:math';

/// Tipo de operación de escritura que se encola mientras no hay conexión.
enum OpKind { create, update, delete }

/// Estado de una operación en la cola de sincronización.
///
/// ```
///  pending ──► sending ──► synced
///     │           │
///     │           ├──► uncertain ──► (búsqueda en el servidor) ──► synced | needsReview | (reenvío)
///     │           ├──► rejected   (el servidor gana / datos rechazados; con motivo)
///     │           └──► failed     (fallo transitorio del servidor; reintentable)
///     └──► rejected | needsReview
/// ```
enum OpStatus {
  /// Guardada localmente, esperando conexión o su turno.
  pending,

  /// Se está enviando (o se estaba enviando cuando la app murió / se cortó la red).
  sending,

  /// Se envió pero no se sabe si el servidor la aplicó (timeout, corte, 5xx). Un create en este
  /// estado **nunca se reenvía a ciegas**: primero se busca en el servidor.
  uncertain,

  /// No se puede decidir sola (p. ej. hay varios registros idénticos en el servidor); lo decide el usuario.
  needsReview,

  /// Aplicada (o ya estaba aplicada) en el servidor.
  synced,

  /// Rechazada: el servidor gana. Conserva sus datos y el motivo.
  rejected,

  /// Falló de forma transitoria (p. ej. 500 del servidor); se reintenta hasta agotar los intentos.
  failed,
}

/// Por qué una operación terminó como está. Decide qué acciones se le ofrecen al usuario.
enum OpReason {
  none,

  /// El registro que se iba a actualizar ya no existe (lo borró otro cliente).
  deletedRemotely,

  /// El registro cambió en el servidor desde lo que el usuario vio (update/delete bloqueado).
  modifiedRemotely,

  /// Un registro referenciado ya no existe (p. ej. el Pedido de una relación).
  parentMissing,

  /// Depende de otra operación que fue rechazada.
  parentRejected,

  /// El servidor rechazó los datos (HTTP 4xx).
  serverRejected,

  /// El servidor respondió OK pero el estado real no coincide (campo no guardado, delete que no borró).
  inconsistent,

  /// Fallo transitorio del servidor (5xx).
  transient,

  /// Se perdió la respuesta de un create pero el registro sí se había creado: se adoptó, no se duplicó.
  alreadyCreated,

  /// Ya estaba aplicada en el servidor (update con los mismos valores / delete de algo ya borrado).
  alreadyApplied,

  /// Hay varios registros idénticos en el servidor; no se reenvió para no duplicar.
  duplicatesFound,

  /// Se descartó localmente antes de llegar al servidor.
  discardedLocally,
}

/// Operación de escritura pendiente de sincronizar (fila de `pending_ops`).
class PendingOp {
  const PendingOp({
    required this.opId,
    this.seq,
    required this.module,
    required this.kind,
    required this.targetId,
    required this.values,
    this.base,
    this.status = OpStatus.pending,
    this.reason = OpReason.none,
    this.detail,
    this.attempts = 0,
    this.force = false,
    this.preSendIds,
    this.resultId,
    required this.createdAt,
    required this.updatedAt,
  });

  /// Identidad propia de la operación (UUID v4 generado en la app).
  final String opId;

  /// Orden de encolado (FIFO); la asigna la base de datos.
  final int? seq;

  /// Ruta REST del módulo (`producto`, `pedido`, `pedidoproducto`).
  final String module;

  final OpKind kind;

  /// Id del registro afectado. En un `create` es un id **temporal negativo**, hasta que el servidor
  /// asigna el real.
  final int targetId;

  /// Valores nuevos (tipados) por nombre de campo. En un `delete`, los del registro al borrarlo.
  final Map<String, Object?> values;

  /// Instantánea de lo que el cliente sabía del servidor al crear la operación (update/delete).
  /// Sirve para detectar cambios ajenos; `null` si no había datos locales.
  final Map<String, Object?>? base;

  final OpStatus status;
  final OpReason reason;

  /// Texto para el usuario: motivo del rechazo o nota de una operación ya aplicada.
  final String? detail;

  final int attempts;

  /// El usuario aceptó pisar el conflicto ("Aplicar igualmente" / "Eliminar igualmente").
  final bool force;

  /// Solo `create`: ids que el servidor ya tenía justo antes del envío (para reconocer un registro
  /// creado por un POST cuya respuesta se perdió).
  final List<int>? preSendIds;

  /// Solo `create` sincronizado: id real asignado por el servidor.
  final int? resultId;

  final int createdAt;
  final int updatedAt;

  bool get isActive =>
      status == OpStatus.pending ||
      status == OpStatus.sending ||
      status == OpStatus.uncertain ||
      status == OpStatus.needsReview ||
      status == OpStatus.failed;

  /// Necesita una decisión o una revisión del usuario.
  bool get needsAttention =>
      status == OpStatus.rejected ||
      status == OpStatus.failed ||
      status == OpStatus.needsReview;

  PendingOp copyWith({
    Map<String, Object?>? values,
    Object? base = _keep,
    OpStatus? status,
    OpReason? reason,
    Object? detail = _keep,
    int? attempts,
    bool? force,
    Object? preSendIds = _keep,
    Object? resultId = _keep,
    int? targetId,
    OpKind? kind,
    int? updatedAt,
  }) {
    return PendingOp(
      opId: opId,
      seq: seq,
      module: module,
      kind: kind ?? this.kind,
      targetId: targetId ?? this.targetId,
      values: values ?? this.values,
      base: identical(base, _keep) ? this.base : base as Map<String, Object?>?,
      status: status ?? this.status,
      reason: reason ?? this.reason,
      detail: identical(detail, _keep) ? this.detail : detail as String?,
      attempts: attempts ?? this.attempts,
      force: force ?? this.force,
      preSendIds: identical(preSendIds, _keep)
          ? this.preSendIds
          : preSendIds as List<int>?,
      resultId: identical(resultId, _keep) ? this.resultId : resultId as int?,
      createdAt: createdAt,
      updatedAt: updatedAt ?? DateTime.now().millisecondsSinceEpoch,
    );
  }

  Map<String, Object?> toRow() => {
    'op_id': opId,
    if (seq != null) 'seq': seq,
    'module': module,
    'kind': kind.name,
    'target_id': targetId,
    'values_json': jsonEncode(values),
    'base_json': base == null ? null : jsonEncode(base),
    'status': status.name,
    'reason_code': reason.name,
    'detail': detail,
    'attempts': attempts,
    'force': force ? 1 : 0,
    'pre_send_ids': preSendIds == null ? null : jsonEncode(preSendIds),
    'result_id': resultId,
    'created_at': createdAt,
    'updated_at': updatedAt,
  };

  factory PendingOp.fromRow(Map<String, Object?> row) => PendingOp(
    opId: row['op_id']! as String,
    seq: row['seq'] as int?,
    module: row['module']! as String,
    kind: OpKind.values.byName(row['kind']! as String),
    targetId: row['target_id']! as int,
    values: _decodeMap(row['values_json']! as String)!,
    base: _decodeMap(row['base_json'] as String?),
    status: OpStatus.values.byName(row['status']! as String),
    reason: OpReason.values.byName((row['reason_code'] as String?) ?? 'none'),
    detail: row['detail'] as String?,
    attempts: row['attempts']! as int,
    force: (row['force'] as int? ?? 0) == 1,
    preSendIds: row['pre_send_ids'] == null
        ? null
        : (jsonDecode(row['pre_send_ids']! as String) as List).cast<int>(),
    resultId: row['result_id'] as int?,
    createdAt: row['created_at']! as int,
    updatedAt: row['updated_at']! as int,
  );

  static Map<String, Object?>? _decodeMap(String? json) =>
      json == null ? null : Map<String, Object?>.from(jsonDecode(json) as Map);
}

const Object _keep = Object();

/// UUID v4 generado en la app para identificar cada operación.
String newOpId() {
  final bytes = List<int>.generate(16, (_) => _random.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  String hex(int b) => b.toRadixString(16).padLeft(2, '0');
  final h = bytes.map(hex).join();
  return '${h.substring(0, 8)}-${h.substring(8, 12)}-${h.substring(12, 16)}-'
      '${h.substring(16, 20)}-${h.substring(20)}';
}

final Random _random = Random.secure();
