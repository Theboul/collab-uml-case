/// Entidad del dominio generado por CU10.
///
/// El `id` es **explícito** y tipado como en el backend (`Long` → `int`), a diferencia del
/// scaffold legacy, que no lo modelaba y usaba el primer atributo como identificador.
abstract interface class Entity {
  /// Clave primaria (`Long` en Spring). `null` solo antes de que el backend la asigne.
  int? get id;

  /// Cuerpo para crear/actualizar. **Nunca incluye `id`**: viaja en la ruta (`/api/x/{id}`).
  Map<String, Object?> toJson();
}

/// Lee un `Long` del JSON: acepta `int`, `num` entero o `String` numérico; `null` si no se puede.
int? parseLong(Object? value) {
  if (value is int) return value;
  if (value is num && value == value.truncate()) return value.toInt();
  if (value is String) return int.tryParse(value);
  return null;
}

/// Lee una referencia `@ManyToOne` del JSON.
///
/// El backend usa `@JsonIdentityInfo`: la **primera** aparición de un objeto en una respuesta va
/// completa (`{"id":1,...}`) y las siguientes van solo como su id (`1`). También puede ser `null`.
int? parseRefId(Object? value) {
  if (value is Map) return parseLong(value['id']);
  return parseLong(value);
}
