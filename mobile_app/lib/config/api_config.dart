/// Configuración del acceso al backend generado por CU10.
class ApiConfig {
  const ApiConfig._();

  /// URL base de la API. Se cambia al compilar con `--dart-define=API_BASE_URL=...`.
  ///
  /// El valor por defecto (`127.0.0.1:9000`) sirve para un teléfono por USB con
  /// `adb reverse tcp:9000 tcp:9000` (el `127.0.0.1` del teléfono llega al backend del PC).
  /// Para un emulador Android usar `http://10.0.2.2:9000/api`; para WiFi, la IP del PC.
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:9000/api',
  );

  /// Tiempo máximo de espera por petición.
  static const Duration timeout = Duration(seconds: 10);
}
