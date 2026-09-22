/// Normalización del texto de un comando (dictado o escrito), previa al parser.
///
/// Solo hace tres cosas: pasar a minúsculas, quitar tildes y colapsar espacios. Es una función
/// pura, sin I/O.
///
/// La **ñ se conserva**: es una letra distinta de la n (`año` ≠ `ano`), no una tilde.
String normalizeText(String input) {
  final lower = input.toLowerCase().replaceAllMapped(
    _accented,
    (m) => _withoutAccent[m[0]]!,
  );
  return lower.replaceAll(RegExp(r'\s+'), ' ').trim();
}

final RegExp _accented = RegExp('[áàâäéèêëíìîïóòôöúùûü]');

const Map<String, String> _withoutAccent = {
  'á': 'a',
  'à': 'a',
  'â': 'a',
  'ä': 'a',
  'é': 'e',
  'è': 'e',
  'ê': 'e',
  'ë': 'e',
  'í': 'i',
  'ì': 'i',
  'î': 'i',
  'ï': 'i',
  'ó': 'o',
  'ò': 'o',
  'ô': 'o',
  'ö': 'o',
  'ú': 'u',
  'ù': 'u',
  'û': 'u',
  'ü': 'u',
};
