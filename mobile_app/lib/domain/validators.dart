import 'field_spec.dart';

/// Validación de entrada según el **tipo real** del atributo (no solo "campo requerido").
///
/// Existe porque el backend generado por CU10 valida casi nada: `{"precio":"abc"}` responde 200 y
/// guarda `null`, y `{}` crea una fila vacía. Por eso el rechazo tiene que ocurrir aquí, *antes* de
/// enviar nada.
class FieldValidator {
  const FieldValidator._();

  /// Longitud máxima por defecto de un `String` (varchar(255) en JPA).
  static const int defaultTextMaxLength = 255;

  static final BigInt _longMin = BigInt.parse('-9223372036854775808');
  static final BigInt _longMax = BigInt.parse('9223372036854775807');
  static final RegExp _integerPattern = RegExp(r'^[+-]?\d+$');
  static final RegExp _decimalPattern = RegExp(r'^[+-]?\d+([.,]\d+)?$');

  /// Devuelve el mensaje de error para [raw], o `null` si es válido.
  ///
  /// [allowLocalIds]: una referencia puede ser un id **temporal negativo** (un registro creado sin
  /// conexión que aún no tiene id real). Solo lo activa la cola de sincronización.
  static String? validate(
    FieldSpec field,
    String? raw, {
    bool allowLocalIds = false,
  }) {
    final value = (raw ?? '').trim();
    switch (field.type) {
      case FieldType.text:
        if (value.isEmpty) return '${field.label} es obligatorio.';
        final max = field.maxLength ?? defaultTextMaxLength;
        if (value.length > max) {
          return '${field.label} admite como máximo $max caracteres (tiene ${value.length}).';
        }
        return null;
      case FieldType.integer:
        if (value.isEmpty) return '${field.label} es obligatorio.';
        if (!_integerPattern.hasMatch(value)) {
          return '${field.label} debe ser un número entero (sin decimales ni letras).';
        }
        final n = BigInt.tryParse(
          value.startsWith('+') ? value.substring(1) : value,
        );
        if (n == null || n < _longMin || n > _longMax) {
          return '${field.label} está fuera del rango permitido.';
        }
        return null;
      case FieldType.decimal:
        if (value.isEmpty) return '${field.label} es obligatorio.';
        if (!_decimalPattern.hasMatch(value)) {
          return '${field.label} debe ser un número, por ejemplo 19.90 (sin letras ni símbolos).';
        }
        final d = double.tryParse(value.replaceAll(',', '.'));
        if (d == null || !d.isFinite) {
          return '${field.label} está fuera del rango permitido.';
        }
        return null;
      case FieldType.reference:
        if (value.isEmpty) return 'Selecciona ${field.label.toLowerCase()}.';
        final id = int.tryParse(value);
        if (id == null || id == 0 || (id < 0 && !allowLocalIds)) {
          return '${field.label} no es válido.';
        }
        return null;
      case FieldType.boolean:
        if (_parseBool(value) == null) {
          return '${field.label} debe ser sí/no.';
        }
        return null;
    }
  }

  /// `true`/`si`/`verdadero`/`1` o `false`/`no`/`falso`/`0` (sin distinguir mayúsculas); cualquier
  /// otra cosa no es un booleano válido.
  static bool? _parseBool(String value) {
    switch (value.toLowerCase()) {
      case 'true':
      case 'si':
      case 'sí':
      case 'verdadero':
      case '1':
        return true;
      case 'false':
      case 'no':
      case 'falso':
      case '0':
        return false;
      default:
        return null;
    }
  }

  /// Convierte una entrada **ya validada** al tipo Dart del atributo.
  ///
  /// Llamar solo si [validate] devolvió `null`; lanza [FormatException] en caso contrario.
  static Object parse(FieldSpec field, String raw) {
    final value = raw.trim();
    switch (field.type) {
      case FieldType.text:
        return value;
      case FieldType.integer:
      case FieldType.reference:
        return int.parse(value.startsWith('+') ? value.substring(1) : value);
      case FieldType.decimal:
        return double.parse(value.replaceAll(',', '.'));
      case FieldType.boolean:
        return _parseBool(value)!;
    }
  }
}
