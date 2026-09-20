import 'entity_module.dart';
import 'validators.dart';

/// Utilidades sobre los **valores tipados** de una entidad (los que guarda la cola y la caché).
///
/// La validación reutiliza [FieldValidator]: no hay una segunda copia de las reglas de tipo.
class EntityValues {
  const EntityValues._();

  /// Errores de validación por campo (vacío si todo es válido).
  ///
  /// Un valor tipado se valida como lo haría el texto equivalente del formulario. Las referencias
  /// pueden ser ids temporales negativos (registros creados sin conexión).
  static Map<String, String> validate(
    EntityModule module,
    Map<String, Object?> values,
  ) {
    final errors = <String, String>{};
    for (final field in module.fields) {
      final error = FieldValidator.validate(
        field,
        values[field.name]?.toString(),
        allowLocalIds: true,
      );
      if (error != null) errors[field.name] = error;
    }
    return errors;
  }

  /// ¿Coinciden los valores de todos los campos del módulo? (doubles con tolerancia).
  static bool same(
    EntityModule module,
    Map<String, Object?> a,
    Map<String, Object?> b,
  ) {
    for (final field in module.fields) {
      if (!_sameValue(a[field.name], b[field.name])) return false;
    }
    return true;
  }

  /// Texto legible: `Nombre: Camisa, Precio: 19.9`.
  static String describe(EntityModule module, Map<String, Object?> values) => [
    for (final field in module.fields)
      '${field.label}: ${values[field.name] ?? '—'}',
  ].join(', ');

  static bool _sameValue(Object? a, Object? b) {
    if (a is num && b is num) return (a - b).abs() < 1e-9;
    return a == b;
  }
}
