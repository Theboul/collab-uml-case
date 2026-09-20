import 'dart:convert';

import '../domain/entity_module.dart';
import '../models/entity.dart';
import 'api_client.dart';
import 'failures.dart';

/// Operaciones de gestión (consultar, crear, actualizar, eliminar) de una entidad contra el
/// backend real generado por CU10.
///
/// Su trabajo no es solo enviar peticiones: el backend responde de forma poco fiable, así que aquí
/// se **verifica** el resultado en vez de fiarse del código HTTP:
///
/// | Respuesta del backend                          | Qué hace el repositorio                          |
/// |------------------------------------------------|--------------------------------------------------|
/// | `GET`/`PUT` de id inexistente → **500**        | comprueba en el listado; si falta → [NotFoundFailure] |
/// | `DELETE` de id inexistente → **200**           | consulta antes; si no existe → [NotFoundFailure] |
/// | `DELETE` → 200 pero el registro sigue ahí      | [InconsistentResultFailure] (no se afirma éxito) |
/// | `POST`/`PUT` → 200 pero no guardó un campo     | [InconsistentResultFailure] (y se descarta la fila a medias) |
/// | `POST` con `{"precio":"abc"}` → 200 con `null` | no ocurre: la app valida los tipos antes de enviar |
class EntityRepository {
  EntityRepository(this.module, this._api);

  final EntityModule module;
  final ApiClient _api;

  /// Lista todos los registros.
  Future<List<Entity>> list() async {
    final response = await _api.send('GET', module.path);
    if (response.status != 200) throw _failureFor(response.status);
    final decoded = _decode(response.body);
    if (decoded is! List) throw _unreadable();

    final result = <Entity>[];
    for (final item in decoded) {
      if (item is Map<String, dynamic>) {
        result.add(module.fromJson(item));
      } else if (item is int) {
        // Identidad de Jackson: un objeto ya serializado antes aparece solo como su id.
        result.add(await getById(item));
      }
    }
    return result;
  }

  /// Consulta un registro por id. Lanza [NotFoundFailure] si no existe.
  Future<Entity> getById(int id) async {
    final response = await _api.send('GET', '${module.path}/$id');
    if (response.status == 200) {
      final decoded = _decode(response.body);
      if (decoded is! Map<String, dynamic>) throw _unreadable();
      return module.fromJson(decoded);
    }
    // El backend responde 500 (no 404) para un id inexistente: se desambigua con el listado.
    if (response.status == 404 || response.status >= 500) {
      if (!await _idExists(id)) throw NotFoundFailure(module.label, id);
    }
    throw _failureFor(response.status);
  }

  /// Crea un registro. Devuelve el registro tal como quedó guardado (con su `id`).
  Future<Entity> create(Entity entity) async {
    final response = await _api.send(
      'POST',
      module.path,
      jsonBody: entity.toJson(),
    );
    if (response.status != 200 && response.status != 201) {
      throw _failureFor(response.status);
    }

    final saved = _decodeEntity(response.body);
    final savedId = saved.id;
    if (savedId == null) {
      throw const InconsistentResultFailure(
        'El servidor respondió OK pero no devolvió el ID del registro creado.',
      );
    }

    final missing = _notPersisted(entity, saved);
    if (missing.isNotEmpty) {
      // El backend aceptó (200) pero dejó campos vacíos: se descarta la fila a medias.
      final discarded = await _deleteQuietly(savedId);
      throw InconsistentResultFailure(
        'El servidor respondió OK pero no guardó: ${missing.join(', ')}. '
        '${discarded ? 'Se descartó el registro incompleto que había creado.' : 'No se pudo descartar el registro incompleto #$savedId; revísalo.'}',
      );
    }
    return saved;
  }

  /// Actualiza el registro [id]. Lanza [NotFoundFailure] si ya no existe.
  Future<Entity> update(int id, Entity entity) async {
    await getById(id); // existencia real (y mensaje claro) antes de tocar nada

    final response = await _api.send(
      'PUT',
      '${module.path}/$id',
      jsonBody: entity.toJson(),
    );
    if (response.status != 200) {
      if (response.status >= 500 && !await _idExists(id)) {
        throw NotFoundFailure(module.label, id);
      }
      throw _failureFor(response.status);
    }

    final saved = _decodeEntity(response.body);
    final missing = _notPersisted(entity, saved);
    if (missing.isNotEmpty) {
      throw InconsistentResultFailure(
        'El servidor respondió OK pero no aplicó el cambio en: ${missing.join(', ')}.',
      );
    }
    return saved;
  }

  /// Elimina el registro [id]. Lanza [NotFoundFailure] si no existe y
  /// [InconsistentResultFailure] si el servidor dice OK pero el registro sigue existiendo.
  Future<void> delete(int id) async {
    await getById(
      id,
    ); // el backend responde 200 aunque no exista: se comprueba antes

    final response = await _api.send('DELETE', '${module.path}/$id');
    if (response.status != 200 && response.status != 204) {
      throw _failureFor(response.status);
    }

    if (await _idExists(id)) {
      throw InconsistentResultFailure(
        'El servidor respondió OK pero ${module.label} $id sigue existiendo; no se eliminó.',
      );
    }
  }

  /// ¿Existe el registro [id] en el servidor? (consulta el listado; el GET por id da 500 si no existe).
  Future<bool> exists(int id) => _idExists(id);

  // ---------------------------------------------------------------------------------------------

  /// ¿Existe `id` en el listado? Compara solo ids (no resuelve referencias, evita recursión).
  Future<bool> _idExists(int id) async {
    final response = await _api.send('GET', module.path);
    if (response.status != 200) throw _failureFor(response.status);
    final decoded = _decode(response.body);
    if (decoded is! List) throw _unreadable();
    return decoded.any(
      (item) => (item is Map ? parseLong(item['id']) : parseLong(item)) == id,
    );
  }

  /// Intenta borrar [id] sin lanzar. Devuelve `true` solo si **verificó** que ya no existe
  /// (un `DELETE` 200 no basta: el backend responde 200 aunque no borre).
  Future<bool> _deleteQuietly(int id) async {
    try {
      final response = await _api.send('DELETE', '${module.path}/$id');
      if (response.status != 200 && response.status != 204) return false;
      return !await _idExists(id);
    } on AppFailure {
      return false;
    }
  }

  /// Etiquetas de los campos que se enviaron con valor y el servidor no guardó tal cual.
  List<String> _notPersisted(Entity sent, Entity saved) {
    final sentValues = module.valuesOf(sent);
    final savedValues = module.valuesOf(saved);
    return [
      for (final field in module.fields)
        if (!_sameValue(sentValues[field.name], savedValues[field.name]))
          field.label,
    ];
  }

  bool _sameValue(Object? a, Object? b) {
    if (a is double && b is double) return (a - b).abs() < 1e-9;
    return a == b;
  }

  Entity _decodeEntity(String body) {
    final decoded = _decode(body);
    if (decoded is! Map<String, dynamic>) throw _unreadable();
    return module.fromJson(decoded);
  }

  Object? _decode(String body) {
    try {
      return jsonDecode(body);
    } on FormatException {
      throw _unreadable();
    }
  }

  AppFailure _unreadable() => const InconsistentResultFailure(
    'El servidor devolvió una respuesta que la app no pudo interpretar.',
  );

  AppFailure _failureFor(int status) => status >= 400 && status < 500
      ? RejectedFailure(status)
      : ServerFailure(status);
}
