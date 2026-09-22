import '../field_spec.dart';
import 'text_normalizer.dart';
import 'voice_command.dart';

/// Devuelve [command] con los valores de sus campos de **texto** tomados de [original] (lo que dijo o
/// escribió el usuario), para conservar mayúsculas y tildes que la normalización quitó.
///
/// El parser trabaja sobre texto normalizado y no se toca; esto es un paso aparte y también puro.
/// Los campos numéricos se dejan como están. Si un valor no es un trozo contiguo del original
/// (p. ej. `camisa 20 azul` → `camisa azul`), o el original no se corresponde con el texto
/// normalizado, ese valor queda como lo entendió el parser.
VoiceCommand restoreOriginalText(VoiceCommand command, String original) {
  final normalized = normalizeText(original);
  final map = _indexMap(original, normalized);
  if (map == null) return command;
  final values = {
    for (final entry in command.values.entries)
      entry.key: _isText(command, entry.key)
          ? _restore(original, normalized, map, entry.value) ?? entry.value
          : entry.value,
  };
  return VoiceCommand(
    intent: command.intent,
    module: command.module,
    id: command.id,
    values: values,
  );
}

bool _isText(VoiceCommand command, String fieldName) => command.module.fields
    .any((f) => f.name == fieldName && f.type == FieldType.text);

/// Posición en [original] de cada carácter de [normalized] (`null` si no se pueden alinear).
///
/// La normalización conserva el largo de cada carácter (minúsculas y quitar tildes son 1:1) y solo
/// colapsa/recorta espacios, así que se alinea recorriendo ambos textos a la vez.
List<int>? _indexMap(String original, String normalized) {
  final map = <int>[];
  var i = 0;
  while (i < original.length && _isSpace(original[i])) {
    i++;
  }
  var previousWasSpace = false;
  for (; i < original.length; i++) {
    if (_isSpace(original[i])) {
      if (!previousWasSpace) map.add(i);
      previousWasSpace = true;
    } else {
      map.add(i);
      previousWasSpace = false;
    }
  }
  if (map.isNotEmpty && _isSpace(original[map.last])) map.removeLast();
  return map.length == normalized.length ? map : null;
}

bool _isSpace(String c) => c.trim().isEmpty;

final RegExp _boundary = RegExp(r'[\s.,;:!?¿¡"()]');

/// La primera aparición de [value] en [normalized] como palabras enteras, tomada del original.
String? _restore(
  String original,
  String normalized,
  List<int> map,
  String value,
) {
  if (value.isEmpty) return null;
  var from = 0;
  while (true) {
    final at = normalized.indexOf(value, from);
    if (at < 0) return null;
    final end = at + value.length;
    final startsWord = at == 0 || normalized[at - 1] == ' ';
    final endsWord =
        end == normalized.length || _boundary.hasMatch(normalized[end]);
    if (startsWord && endsWord) {
      return original
          .substring(map[at], map[end - 1] + 1)
          .replaceAll(RegExp(r'\s+'), ' ');
    }
    from = at + 1;
  }
}
