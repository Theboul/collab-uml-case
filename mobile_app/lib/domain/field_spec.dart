/// Tipo de un atributo del modelo UML, tal como lo expone el backend generado por CU10.
///
/// Correspondencia con Java (backend) y Dart (app):
/// - [text]      → `String`  → `String`
/// - [integer]   → `Long`    → `int`   (Dart `int` es de 64 bits, igual que `Long`)
/// - [decimal]   → `Double`  → `double`
/// - [reference] → relación (`@ManyToOne`) → id `Long` de la entidad referenciada
enum FieldType { text, integer, decimal, reference }

/// Descripción de un atributo editable de una entidad: de aquí salen el formulario y su validación.
///
/// Todos los atributos se tratan como **obligatorios** en el formulario: el modelo UML no declara
/// nulabilidad y el backend generado acepta `null` en silencio (`{}` crea una fila vacía), así que
/// es la app la que evita escribir filas incompletas.
class FieldSpec {
  const FieldSpec({
    required this.name,
    required this.label,
    required this.type,
    this.referenceTo,
    this.maxLength,
  });

  /// Nombre del atributo en el JSON del backend (p. ej. `nombre`, `precio`, `pedido`).
  final String name;

  /// Etiqueta legible para el usuario.
  final String label;

  final FieldType type;

  /// Solo para [FieldType.reference]: ruta de la entidad referenciada (p. ej. `pedido`).
  final String? referenceTo;

  /// Longitud máxima para [FieldType.text]. `String` en JPA mapea a `varchar(255)` por defecto.
  final int? maxLength;
}
