/// Fallos de una operación contra el backend, ya traducidos a mensajes para el usuario.
///
/// El backend generado por CU10 responde de forma poco precisa (500 en vez de 404 para ids
/// inexistentes, 200 en un DELETE de algo que no existe, 200 con `null` ante datos inválidos), así
/// que el repositorio interpreta esas respuestas y lanza uno de estos fallos en vez de mostrar un
/// error crudo o dar por buena una operación que no ocurrió.
sealed class AppFailure implements Exception {
  const AppFailure();

  /// Mensaje listo para mostrar al usuario.
  String get userMessage;

  @override
  String toString() => userMessage;
}

/// Sin conexión con el backend: red caída, timeout o servidor apagado.
class NetworkFailure extends AppFailure {
  const NetworkFailure(this.detail);

  /// Detalle técnico (para logs; no se muestra al usuario).
  final String detail;

  @override
  String get userMessage =>
      'No se pudo conectar con el servidor. Revisa la conexión e inténtalo de nuevo.';
}

/// El registro no existe (nunca existió o lo eliminó otro usuario).
class NotFoundFailure extends AppFailure {
  const NotFoundFailure(this.entityLabel, this.id);

  final String entityLabel;
  final int id;

  @override
  String get userMessage =>
      'No existe $entityLabel con ID $id (puede haber sido eliminado).';
}

/// El servidor rechazó la petición (HTTP 4xx, p. ej. 400 por un cuerpo mal formado).
class RejectedFailure extends AppFailure {
  const RejectedFailure(this.status);

  final int status;

  @override
  String get userMessage =>
      'El servidor rechazó los datos (HTTP $status). Revísalos e inténtalo de nuevo; '
      'no se guardó nada.';
}

/// Error interno del servidor (HTTP 5xx) que no corresponde a un registro inexistente.
class ServerFailure extends AppFailure {
  const ServerFailure(this.status);

  final int status;

  @override
  String get userMessage =>
      'El servidor tuvo un error interno (HTTP $status). La operación no se pudo completar; '
      'inténtalo más tarde.';
}

/// El servidor respondió "OK" pero el estado real no coincide con lo pedido
/// (no guardó un campo, el registro sigue existiendo tras un DELETE…).
class InconsistentResultFailure extends AppFailure {
  const InconsistentResultFailure(this.detail);

  final String detail;

  @override
  String get userMessage => detail;
}

/// Sin conexión y el dato pedido no está en el almacenamiento local.
class OfflineMissFailure extends AppFailure {
  const OfflineMissFailure(this.entityLabel, this.id);

  final String entityLabel;
  final int id;

  @override
  String get userMessage =>
      'Sin conexión: $entityLabel $id no está en los datos guardados en este dispositivo.';
}

/// Los datos no pasan la validación de la app (no llega a encolarse ni a enviarse).
class InvalidInputFailure extends AppFailure {
  const InvalidInputFailure(this.errors);

  /// Mensaje de error por nombre de campo.
  final Map<String, String> errors;

  @override
  String get userMessage => errors.values.join(' ');
}

/// Conflicto con el estado del servidor: el servidor gana y la operación no se aplicó.
class ConflictFailure extends AppFailure {
  const ConflictFailure(this.message);

  final String message;

  @override
  String get userMessage => message;
}
