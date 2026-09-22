import '../entity_module.dart';
import '../field_spec.dart';
import 'text_normalizer.dart';
import 'voice_command.dart';

/// Entidades que se pueden gestionar por voz: las que **no tienen campos de referencia**.
///
/// Derivado de los [EntityModule] de CU12, sin una segunda lista: `PedidoProducto` (una relación
/// que exige elegir ids de otras dos entidades) queda fuera por esa misma regla.
final List<EntityModule> voiceModules = List.unmodifiable(
  allModules.where((m) => m.fields.every((f) => f.type != FieldType.reference)),
);

/// Interpreta un texto **ya normalizado** (`normalizeText`) contra un vocabulario cerrado.
///
/// Es una función pura: sin I/O, sin red, sin estado. Las entidades y sus campos salen de
/// [voiceModules] y sus `FieldSpec`; lo único escrito a mano son las palabras de acción, que son
/// gramática del comando y no del modelo.
///
/// Templates (por entidad): crear (todos los campos), consultar (todas, o una por id), actualizar
/// (un campo de un registro por id) y eliminar (por id).
///
/// Límites conocidos, por ser un vocabulario cerrado: una palabra de acción o de entidad dentro de un
/// valor (un producto llamado "lista") se lee como acción/entidad; los artículos y preposiciones
/// (`el`, `de`, `con`…) se descartan solo en los extremos de un valor, no dentro.
class VoiceCommandParser {
  const VoiceCommandParser();

  VoiceParseResult parse(String normalizedText) {
    final tokens = _tokenize(normalizedText);
    if (tokens.isEmpty) {
      return const VoiceFailure(
        VoiceErrorKind.accionInexistente,
        detail: 'No hay ninguna instrucción en el texto.',
      );
    }
    if (tokens.any(_relationWords.contains)) {
      return const VoiceFailure(
        VoiceErrorKind.accionInexistente,
        detail:
            'Las relaciones entre pedidos y productos no se gestionan por voz; '
            'usa las pantallas de la app.',
      );
    }

    // ---- 1. Acción -----------------------------------------------------------------------
    final intents = <VoiceIntent>[];
    for (final t in tokens) {
      final intent = _verbs[t];
      if (intent != null && !intents.contains(intent)) intents.add(intent);
    }
    if (intents.isEmpty && tokens.any(_weakCreate.contains)) {
      intents.add(VoiceIntent.crear);
    }
    if (intents.isEmpty) {
      return const VoiceFailure(
        VoiceErrorKind.accionInexistente,
        detail: 'No reconozco ninguna acción en lo que dijiste.',
      );
    }

    // ---- 2. Entidad ----------------------------------------------------------------------
    final entityWords = <String, EntityModule>{
      for (final m in voiceModules) ...{
        normalizeText(m.label): m,
        normalizeText(m.labelPlural): m,
      },
    };
    final entities = <EntityModule>[];
    for (final t in tokens) {
      final m = entityWords[t];
      if (m != null && !entities.contains(m)) entities.add(m);
    }

    if (intents.length > 1) {
      return VoiceFailure(
        VoiceErrorKind.intencionAmbigua,
        understood: [
          if (entities.length == 1) 'Entidad: ${entities.single.label}',
        ],
        candidates: [for (final i in intents) i.name],
      );
    }
    final intent = intents.single;
    final action = 'Acción: ${intent.name}';
    if (entities.length != 1) {
      return VoiceFailure(
        VoiceErrorKind.intencionAmbigua,
        understood: [action],
        candidates: [
          for (final m in entities.isEmpty ? voiceModules : entities) m.label,
        ],
      );
    }
    final module = entities.single;
    final base = [action, 'Entidad: ${module.label}'];

    final entityIndexes = [
      for (var i = 0; i < tokens.length; i++)
        if (entityWords[tokens[i]] == module) i,
    ];

    return switch (intent) {
      VoiceIntent.crear => _create(module, tokens, entityWords, base),
      VoiceIntent.consultar => _query(module, tokens, entityIndexes, base),
      VoiceIntent.actualizar => _update(
        module,
        tokens,
        entityWords,
        entityIndexes,
        base,
      ),
      VoiceIntent.eliminar => _delete(module, tokens, entityIndexes, base),
    };
  }

  // ---- crear -------------------------------------------------------------------------------

  VoiceParseResult _create(
    EntityModule module,
    List<String> tokens,
    Map<String, EntityModule> entityWords,
    List<String> base,
  ) {
    final rest = [
      for (final t in tokens)
        if (!_verbs.containsKey(t) && !entityWords.containsKey(t)) t,
    ];
    final values = _fillSlots(module, rest);
    final missing = [
      for (final f in module.fields)
        if (!values.containsKey(f.name)) f.label,
    ];
    final understood = [
      ...base,
      for (final f in module.fields)
        if (values.containsKey(f.name)) '${f.label}: ${values[f.name]}',
    ];
    if (missing.isNotEmpty) {
      return VoiceFailure(
        VoiceErrorKind.datosFaltantes,
        understood: understood,
        missing: missing,
      );
    }
    return VoiceCommand(
      intent: VoiceIntent.crear,
      module: module,
      values: values,
    );
  }

  /// Reparte [tokens] entre los campos de [module]: primero por palabra clave del campo
  /// (`precio 20`), luego por posición (números → campo numérico, el resto → campo de texto).
  Map<String, String> _fillSlots(EntityModule module, List<String> tokens) {
    final byKeyword = _fieldKeywords(module);
    final pre = <String>[];
    final segments = <FieldSpec, List<String>>{};
    List<String> current = pre;
    for (final t in tokens) {
      final field = byKeyword[t];
      if (field != null && !segments.containsKey(field)) {
        current = segments[field] = [];
      } else {
        current.add(t);
      }
    }

    final values = <String, String>{};
    segments.forEach((field, segment) {
      final value = _slotValue(field, _trim(segment));
      if (value.isNotEmpty) values[field.name] = value;
    });

    // Lo que quedó sin palabra clave se reparte por posición.
    var leftover = _trim(pre);
    for (final field in module.fields) {
      if (segments.containsKey(field) || !_isNumeric(field)) continue;
      final run = _lastNumericRun(leftover);
      if (run == null) continue;
      values[field.name] = run.text;
      leftover = _trim([
        ...leftover.sublist(0, run.start),
        ...leftover.sublist(run.end),
      ]);
    }
    if (leftover.isNotEmpty) {
      for (final field in module.fields) {
        if (segments.containsKey(field) ||
            values.containsKey(field.name) ||
            _isNumeric(field)) {
          continue;
        }
        values[field.name] = leftover.join(' ');
        break;
      }
    }
    return values;
  }

  // ---- consultar ---------------------------------------------------------------------------

  VoiceParseResult _query(
    EntityModule module,
    List<String> tokens,
    List<int> entityIndexes,
    List<String> base,
  ) {
    final ref = _idAfterEntity(tokens, entityIndexes);
    if (ref.id != null) {
      return VoiceCommand(
        intent: VoiceIntent.consultar,
        module: module,
        id: ref.id,
      );
    }
    if (ref.markerWithoutNumber) {
      return VoiceFailure(
        VoiceErrorKind.datosFaltantes,
        understood: base,
        missing: const ['ID'],
      );
    }
    return VoiceCommand(intent: VoiceIntent.consultar, module: module);
  }

  // ---- eliminar ----------------------------------------------------------------------------

  VoiceParseResult _delete(
    EntityModule module,
    List<String> tokens,
    List<int> entityIndexes,
    List<String> base,
  ) {
    final ref = _idAfterEntity(tokens, entityIndexes);
    if (ref.id == null) {
      return VoiceFailure(
        VoiceErrorKind.datosFaltantes,
        understood: base,
        missing: const ['ID'],
      );
    }
    return VoiceCommand(
      intent: VoiceIntent.eliminar,
      module: module,
      id: ref.id,
    );
  }

  // ---- actualizar --------------------------------------------------------------------------

  VoiceParseResult _update(
    EntityModule module,
    List<String> tokens,
    Map<String, EntityModule> entityWords,
    List<int> entityIndexes,
    List<String> base,
  ) {
    final ref = _idAfterEntity(tokens, entityIndexes);
    final removed = <int>{
      for (var i = 0; i < tokens.length; i++)
        if (_verbs.containsKey(tokens[i]) || entityWords.containsKey(tokens[i]))
          i,
      ...ref.consumed,
    };
    final rest = [
      for (var i = 0; i < tokens.length; i++)
        if (!removed.contains(i)) tokens[i],
    ];
    final understood = [...base, if (ref.id != null) 'ID: ${ref.id}'];
    final fieldLabels = [for (final f in module.fields) f.label];

    final byKeyword = _fieldKeywords(module);
    final fields = <FieldSpec>[];
    for (final t in rest) {
      final f = byKeyword[t];
      if (f != null && !fields.contains(f)) fields.add(f);
    }
    if (fields.length > 1) {
      return VoiceFailure(
        VoiceErrorKind.intencionAmbigua,
        understood: understood,
        candidates: [for (final f in fields) f.label],
      );
    }

    final missing = <String>[if (ref.id == null) 'ID'];
    if (fields.isEmpty) {
      final hasValue = _trim(rest).isNotEmpty;
      return VoiceFailure(
        VoiceErrorKind.datosFaltantes,
        understood: understood,
        missing: [...missing, 'Campo', if (!hasValue) 'Valor'],
        candidates: fieldLabels,
      );
    }

    final field = fields.single;
    final at = rest.indexWhere((t) => byKeyword[t] == field);
    var valueTokens = _trim(rest.sublist(at + 1));
    if (valueTokens.isEmpty) valueTokens = _trim(rest.sublist(0, at));
    final value = _slotValue(field, valueTokens);
    understood.add('Campo: ${field.label}');
    if (value.isEmpty) missing.add('Valor');
    if (missing.isNotEmpty) {
      return VoiceFailure(
        VoiceErrorKind.datosFaltantes,
        understood: understood,
        missing: missing,
      );
    }
    return VoiceCommand(
      intent: VoiceIntent.actualizar,
      module: module,
      id: ref.id,
      values: {field.name: value},
    );
  }

  // ---- utilidades --------------------------------------------------------------------------

  /// Palabra clave (normalizada) → campo, derivada de `FieldSpec.name` y `FieldSpec.label`.
  Map<String, FieldSpec> _fieldKeywords(EntityModule module) => {
    for (final f in module.fields) ...{
      normalizeText(f.name): f,
      normalizeText(f.label): f,
    },
  };

  /// Id que sigue a la palabra de entidad: `producto 3`, `producto numero 3`, `pedido con id 2`.
  _IdRef _idAfterEntity(List<String> tokens, List<int> entityIndexes) {
    var markerWithoutNumber = false;
    for (final at in entityIndexes) {
      var i = at + 1;
      var sawMarker = false;
      while (i < tokens.length && _idSkippable.contains(tokens[i])) {
        if (tokens[i] == 'numero' || tokens[i] == 'id') sawMarker = true;
        i++;
      }
      final run = i < tokens.length ? _numericRunAt(tokens, i) : null;
      final id = run == null ? null : int.tryParse(run.text);
      if (run != null && id != null) {
        return _IdRef(id, [for (var k = at + 1; k < run.end; k++) k]);
      }
      if (sawMarker) markerWithoutNumber = true;
    }
    return _IdRef(null, const [], markerWithoutNumber: markerWithoutNumber);
  }

  /// Valor crudo de un campo a partir de sus tokens: en un campo numérico, el número (dígitos o
  /// palabras); si no hay ninguno, el texto tal cual (lo rechazará `FieldValidator`).
  String _slotValue(FieldSpec field, List<String> tokens) {
    if (tokens.isEmpty) return '';
    if (_isNumeric(field)) {
      final run = _lastNumericRun(tokens);
      if (run != null) return run.text;
    }
    return tokens.join(' ');
  }

  bool _isNumeric(FieldSpec f) =>
      f.type == FieldType.decimal || f.type == FieldType.integer;

  /// Quita artículos y preposiciones de los extremos (no de dentro: `camisa de algodon`).
  List<String> _trim(List<String> tokens) {
    var start = 0;
    var end = tokens.length;
    while (start < end && _fillers.contains(tokens[start])) {
      start++;
    }
    while (end > start && _fillers.contains(tokens[end - 1])) {
      end--;
    }
    return tokens.sublist(start, end);
  }

  /// Separa en palabras, quita la puntuación de los extremos y descarta "por favor".
  List<String> _tokenize(String text) {
    final edge = RegExp(r'^[.,;:!?¿¡"()\[\]{}$€%#]+|[.,;:!?¿¡"()\[\]{}$€%]+$');
    final words = [
      for (final w in text.split(' '))
        if (w.replaceAll(edge, '').isNotEmpty) w.replaceAll(edge, ''),
    ];
    final out = <String>[];
    for (var i = 0; i < words.length; i++) {
      if (words[i] == 'por' &&
          i + 1 < words.length &&
          words[i + 1] == 'favor') {
        i++;
        continue;
      }
      out.add(words[i]);
    }
    return out;
  }

  // ---- números -----------------------------------------------------------------------------

  static final RegExp _digits = RegExp(r'^\d+([.,]\d+)?$');

  /// El último grupo numérico de [tokens] (dígitos o palabras), o `null`.
  _NumRun? _lastNumericRun(List<String> tokens) {
    _NumRun? last;
    var i = 0;
    while (i < tokens.length) {
      final run = _numericRunAt(tokens, i);
      if (run == null) {
        i++;
      } else {
        last = run;
        i = run.end;
      }
    }
    return last;
  }

  /// Grupo numérico que empieza en [i]: un token de dígitos (`19,90`) o palabras (`treinta y cinco`).
  _NumRun? _numericRunAt(List<String> t, int i) {
    if (_digits.hasMatch(t[i])) return _NumRun(i, i + 1, t[i]);
    var j = i;
    var total = 0;
    var any = false;
    if (j < t.length && _hundreds.containsKey(t[j])) {
      total += _hundreds[t[j]]!;
      j++;
      any = true;
    }
    if (j < t.length) {
      final tens = _tens[t[j]];
      if (tens != null) {
        var v = tens;
        j++;
        any = true;
        if (j + 1 < t.length &&
            t[j] == 'y' &&
            _units.containsKey(t[j + 1]) &&
            _units[t[j + 1]]! >= 1 &&
            _units[t[j + 1]]! <= 9) {
          v += _units[t[j + 1]]!;
          j += 2;
        }
        total += v;
      } else if (_units.containsKey(t[j])) {
        total += _units[t[j]]!;
        j++;
        any = true;
      }
    }
    return any ? _NumRun(i, j, '$total') : null;
  }
}

class _IdRef {
  const _IdRef(this.id, this.consumed, {this.markerWithoutNumber = false});

  final int? id;

  /// Índices de los tokens que pertenecen al id (marcadores incluidos): se quitan del resto.
  final List<int> consumed;

  /// Se dijo "número"/"id" pero sin ningún número detrás.
  final bool markerWithoutNumber;
}

class _NumRun {
  const _NumRun(this.start, this.end, this.text);

  final int start;
  final int end; // exclusivo
  final String text;
}

// ---- vocabulario cerrado (gramática del comando, no del modelo) -------------------------------

final Map<String, VoiceIntent> _verbs = {
  for (final w in [
    'crear',
    'crea',
    'agregar',
    'agrega',
    'añadir',
    'añade',
    'anadir',
    'anade',
    'registrar',
    'registra',
  ])
    w: VoiceIntent.crear,
  for (final w in [
    'listar',
    'lista',
    'mostrar',
    'muestra',
    'ver',
    'consultar',
    'consulta',
    'buscar',
    'busca',
  ])
    w: VoiceIntent.consultar,
  for (final w in [
    'actualizar',
    'actualiza',
    'modificar',
    'modifica',
    'cambiar',
    'cambia',
    'editar',
    'edita',
  ])
    w: VoiceIntent.actualizar,
  for (final w in ['eliminar', 'elimina', 'borrar', 'borra', 'quitar', 'quita'])
    w: VoiceIntent.eliminar,
};

/// "nuevo producto…" implica crear, pero solo si no hay una acción explícita.
const Set<String> _weakCreate = {'nuevo', 'nueva'};

/// Frases sobre la relación Pedido-Producto: no se gestionan por voz en esta fase.
const Set<String> _relationWords = {
  'relacion',
  'relaciones',
  'pedidoproducto',
  'pedidoproductos',
  'pedido-producto',
};

/// Se descartan en los extremos de un valor.
const Set<String> _fillers = {
  'el',
  'la',
  'los',
  'las',
  'un',
  'una',
  'unos',
  'unas',
  'de',
  'del',
  'al',
  'a',
  'con',
  'por',
  'para',
  'que',
  'se',
  'es',
  'en',
  'y',
  'llamado',
  'llamada',
  'llamados',
  'llamadas',
  'nuevo',
  'nueva',
  'numero',
  'id',
  'quiero',
  'quisiera',
  'favor',
  'gracias',
  'pesos',
  'bolivianos',
  'boliviano',
  'dolares',
  'bs',
};

/// Palabras que pueden ir entre la entidad y su número: `producto con id 7`, `pedido numero 2`.
const Set<String> _idSkippable = {
  'con',
  'el',
  'de',
  'numero',
  'id',
  'la',
  'un',
  'una',
};

const Map<String, int> _units = {
  'cero': 0,
  'uno': 1,
  'dos': 2,
  'tres': 3,
  'cuatro': 4,
  'cinco': 5,
  'seis': 6,
  'siete': 7,
  'ocho': 8,
  'nueve': 9,
  'diez': 10,
  'once': 11,
  'doce': 12,
  'trece': 13,
  'catorce': 14,
  'quince': 15,
  'dieciseis': 16,
  'diecisiete': 17,
  'dieciocho': 18,
  'diecinueve': 19,
  'veinte': 20,
  'veintiuno': 21,
  'veintidos': 22,
  'veintitres': 23,
  'veinticuatro': 24,
  'veinticinco': 25,
  'veintiseis': 26,
  'veintisiete': 27,
  'veintiocho': 28,
  'veintinueve': 29,
};

const Map<String, int> _tens = {
  'treinta': 30,
  'cuarenta': 40,
  'cincuenta': 50,
  'sesenta': 60,
  'setenta': 70,
  'ochenta': 80,
  'noventa': 90,
};

const Map<String, int> _hundreds = {
  'cien': 100,
  'ciento': 100,
  'doscientos': 200,
  'trescientos': 300,
  'cuatrocientos': 400,
  'quinientos': 500,
  'seiscientos': 600,
  'setecientos': 700,
  'ochocientos': 800,
  'novecientos': 900,
};
