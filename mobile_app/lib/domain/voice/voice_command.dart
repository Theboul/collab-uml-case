import '../entity_module.dart';

/// Lo que el usuario quiere hacer. Coincide con las operaciones de gestión de CU12.
enum VoiceIntent {
  crear('Crear'),
  consultar('Consultar'),
  actualizar('Actualizar'),
  eliminar('Eliminar');

  const VoiceIntent(this.title);

  final String title;
}

/// Las 5 categorías de excepción de la ficha de CU14.
///
/// Quién dispara cada una:
/// - El **parser** (capa pura): [intencionAmbigua], [datosFaltantes] y [accionInexistente]. Una
///   transcripción vacía o sin sentido cuenta como [accionInexistente] (no hay ninguna acción
///   que ejecutar): no se añadió un quinto caso propio al parser.
/// - La **capa de ASR** (solo voz): [vozNoReconocida] y [recursosInsuficientes] (sin red, sin
///   permiso de micrófono, sin reconocedor o idioma no disponible en el dispositivo).
/// - El **ejecutor**: [datosFaltantes] cuando un slot no supera `FieldValidator`.
enum VoiceErrorKind {
  vozNoReconocida,
  intencionAmbigua,
  datosFaltantes,
  accionInexistente,
  recursosInsuficientes,
}

/// Resultado de interpretar un texto: un comando completo o un fallo con su categoría.
sealed class VoiceParseResult {
  const VoiceParseResult();
}

/// Comando tipado y completo: acción + entidad + slots.
///
/// Los valores de [values] son texto **crudo** (`'19,90'`): convertirlos y validarlos es trabajo
/// de `FieldValidator` al ejecutar, para que la app tenga una sola definición de "válido".
final class VoiceCommand extends VoiceParseResult {
  const VoiceCommand({
    required this.intent,
    required this.module,
    this.id,
    this.values = const {},
  });

  final VoiceIntent intent;
  final EntityModule module;

  /// Registro sobre el que se actúa (consultar uno, actualizar, eliminar). `null` en crear/listar.
  final int? id;

  /// Crear: todos los campos de la entidad. Actualizar: exactamente el campo a cambiar.
  final Map<String, String> values;

  /// Frase legible de lo que se va a ejecutar: `Crear Producto · Nombre: camisa, Precio: 20`.
  String get summary {
    final target = switch (intent) {
      VoiceIntent.consultar when id == null => module.labelPlural,
      _ when id != null => '${module.label} $id',
      _ => module.label,
    };
    final slots = [
      for (final field in module.fields)
        if (values.containsKey(field.name))
          '${field.label}: ${values[field.name]}',
    ];
    return '${intent.title} $target${slots.isEmpty ? '' : ' · ${slots.join(', ')}'}';
  }
}

/// No se pudo llegar a un comando: [kind] dice por qué y el resto qué mostrarle al usuario.
final class VoiceFailure extends VoiceParseResult {
  const VoiceFailure(
    this.kind, {
    this.understood = const [],
    this.missing = const [],
    this.candidates = const [],
    this.detail,
  });

  final VoiceErrorKind kind;

  /// Lo que SÍ se entendió (`Acción: crear`, `Entidad: Producto`, `Nombre: camisa`).
  final List<String> understood;

  /// Lo que falta para poder ejecutar (`Precio`, `ID`).
  final List<String> missing;

  /// Opciones entre las que no se pudo decidir (acciones, entidades o campos), o las válidas
  /// cuando falta el campo.
  final List<String> candidates;

  /// Aclaración adicional (p. ej. por qué una frase no aplica).
  final String? detail;
}
