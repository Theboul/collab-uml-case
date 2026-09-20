import '../domain/entity_module.dart';
import '../models/entity.dart';

/// Resultado de listar: los datos, de dónde salen y cuáles tienen cambios sin sincronizar.
class ListResult {
  const ListResult(
    this.items, {
    this.fromCache = false,
    this.pendingIds = const {},
  });

  final List<Entity> items;

  /// `true` si no se pudo hablar con el servidor y son los últimos datos guardados en el dispositivo.
  final bool fromCache;

  /// Ids (reales o temporales negativos) con una operación pendiente de sincronizar.
  final Set<int> pendingIds;
}

/// Qué pasó con una escritura.
enum WriteStatus {
  /// Ya está aplicada en el servidor (y verificada).
  synced,

  /// Guardada en el dispositivo; se enviará cuando haya conexión.
  pending,
}

class WriteOutcome {
  const WriteOutcome(this.status, {this.entity, this.message});

  final WriteStatus status;

  /// El registro tal como quedó (con su id real si [status] es `synced`; temporal si `pending`).
  final Entity? entity;

  /// Aviso adicional para el usuario (p. ej. "ya estaba eliminado").
  final String? message;

  bool get isPending => status == WriteStatus.pending;
}

/// Lo que la UI usa para gestionar una entidad. Detrás hay datos locales, cola de sincronización y
/// servidor (`OfflineFirstRepository`).
abstract interface class EntityGateway {
  EntityModule get module;

  Future<ListResult> list();

  Future<Entity> getById(int id);

  Future<WriteOutcome> create(Entity entity);

  Future<WriteOutcome> update(int id, Entity entity);

  Future<WriteOutcome> delete(int id);
}
