import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// Backend simulado en memoria que reproduce el comportamiento **medido** del backend real
/// generado por CU10 (ver `mobile_app/README.md`):
///
/// - `GET`/`PUT` de un id inexistente → **500** (no 404).
/// - `DELETE` de un id inexistente → **200**.
/// - `POST` con un valor de tipo inválido (`"precio":"abc"`) → **200** guardando `null`.
/// - `POST` con `{}` → **200** creando una fila con todo en `null`.
/// - Las relaciones se escriben con `pedidoid` / `productoid`; cualquier otra forma, o un id que
///   no existe, se **ignora en silencio** y la relación queda en `null`.
/// - JSON malformado → 400.
///
/// Con los interruptores se provocan fallos que el backend real solo da a veces.
class FakeBackend {
  final Map<String, Map<int, Map<String, dynamic>>> tables = {};
  final Map<String, int> _sequence = {};

  /// Tabla de [name], creándola vacía la primera vez que se pide. Así una entidad que no sea
  /// Producto/Pedido/PedidoProducto (agregada a `allModules` en el futuro) no hace fallar este
  /// fixture con un `null check`: entra con la misma tabla vacía que tendría contra un backend
  /// real recién creado. `_fromBody` sigue construyendo el cuerpo campo a campo solo para las 3
  /// entidades conocidas (ahí sí hace falta el tipo real de cada campo); para cualquier otra,
  /// POST/PUT devuelven la fila con los campos crudos del `body` — no es exacto (no hay
  /// coerción de tipo), pero es igual de válido como "no hace fallar el test" que el resto de la
  /// clase ya ofrece.
  Map<int, Map<String, dynamic>> _table(String name) =>
      tables.putIfAbsent(name, () => {});

  /// Registro de peticiones recibidas, p. ej. `POST /api/producto`.
  final List<String> log = [];

  /// Sin conexión: toda petición lanza [SocketException].
  bool offline = false;

  /// `DELETE` responde 200 pero no borra nada.
  bool deleteDoesNothing = false;

  /// `PUT` responde 200 pero no aplica los cambios.
  bool ignoreUpdates = false;

  /// Si no es null, la siguiente petición responde con este estado y se restablece.
  int? failNextWith;

  MockClient get client => MockClient(handle);

  int count(String table) => _table(table).length;

  Map<String, dynamic> insert(String table, Map<String, dynamic> row) {
    final id = _sequence[table] = (_sequence[table] ?? 0) + 1;
    final saved = {'id': id, ...row};
    _table(table)[id] = saved;
    return saved;
  }

  /// Métodos HTTP (p. ej. `POST`) cuya **próxima** petición el servidor **procesa pero la respuesta
  /// se pierde** (llega un [SocketException]): el escenario que duplicaría un create al reintentar.
  final Set<String> loseResponseOf = {};

  /// Métodos cuya próxima petición se pierde **antes** de llegar al servidor (no se procesa).
  final Set<String> dropRequestOf = {};

  /// Métodos cuya próxima petición se procesa (el servidor guarda) y luego responde con este
  /// estado (p. ej. `{'POST': 500}`): el servidor falló después de escribir.
  final Map<String, int> failAfterProcessingOf = {};

  /// Hace que el servidor rechace con 400 los cuerpos para los que devuelve `true`.
  bool Function(String table, Map<String, dynamic> body)? rejectBody;

  /// Mientras exista la entrada, TODA petición de ese método falla con ese estado **sin procesarse**
  /// (p. ej. `{'PUT': 500}`): un fallo persistente del servidor.
  final Map<String, int> failAlwaysOf = {};

  /// Latencia artificial por petición (para provocar carreras entre operaciones).
  Duration? delay;

  /// Tras esta cantidad de peticiones el servidor deja de ser alcanzable (corte a mitad de una
  /// sincronización).
  int? goOfflineAfter;

  /// Atiende una petición como lo haría el backend (público para poder envolverlo en los tests).
  Future<http.Response> handle(http.Request request) async {
    if (delay != null) await Future<void>.delayed(delay!);
    if (offline) throw const SocketException('sin conexión (simulada)');
    final remaining = goOfflineAfter;
    if (remaining != null) {
      if (remaining <= 0) {
        offline = true;
        goOfflineAfter = null;
        throw const SocketException('conexión perdida a mitad (simulada)');
      }
      goOfflineAfter = remaining - 1;
    }
    if (dropRequestOf.remove(request.method)) {
      log.add(
        '${request.method} ${request.url.path} [perdida antes de llegar]',
      );
      throw const SocketException('petición perdida (simulada)');
    }

    final persistent = failAlwaysOf[request.method];
    if (persistent != null) {
      log.add('${request.method} ${request.url.path} [500 persistente]');
      return _json(persistent, {
        'status': persistent,
        'error': 'fallo persistente',
      });
    }

    final response = await _serve(request);

    if (loseResponseOf.remove(request.method)) {
      log.add(
        '  ↳ respuesta perdida (el servidor SÍ procesó ${request.method})',
      );
      throw const SocketException('respuesta perdida (simulada)');
    }
    final status = failAfterProcessingOf.remove(request.method);
    if (status != null) {
      log.add('  ↳ el servidor procesó y respondió $status');
      return _json(status, {'status': status, 'error': 'falló tras guardar'});
    }
    return response;
  }

  Future<http.Response> _serve(http.Request request) async {
    log.add('${request.method} ${request.url.path}');

    final forced = failNextWith;
    if (forced != null) {
      failNextWith = null;
      return _json(forced, {'status': forced, 'error': 'forzado'});
    }

    final segments = request.url.pathSegments; // ['api', 'producto', '3']
    final table = segments[1];
    final id = segments.length > 2 ? int.tryParse(segments[2]) : null;
    if (segments.length > 2 && id == null) {
      return _json(400, {'error': 'Bad Request'});
    }

    switch (request.method) {
      case 'GET':
        if (id == null) return _json(200, _table(table).values.toList());
        final row = _table(table)[id];
        return row == null
            ? _json(500, {'error': 'Internal Server Error'})
            : _json(200, row);
      case 'POST':
        final body = _decodeBody(request);
        if (body == null || (rejectBody?.call(table, body) ?? false)) {
          return _json(400, {'error': 'Bad Request'});
        }
        return _json(200, insert(table, _fromBody(table, body)));
      case 'PUT':
        final body = _decodeBody(request);
        if (body == null || (rejectBody?.call(table, body) ?? false)) {
          return _json(400, {'error': 'Bad Request'});
        }
        final row = _table(table)[id];
        if (row == null) return _json(500, {'error': 'Internal Server Error'});
        if (!ignoreUpdates) {
          row.addAll(_fromBody(table, body, keepNulls: false));
        }
        return _json(200, row);
      case 'DELETE':
        if (!deleteDoesNothing && id != null) {
          _table(table).remove(id);
          _cascade(table, id);
        }
        return http.Response('', 200);
    }
    return _json(405, {'error': 'Method Not Allowed'});
  }

  /// El backend real borra en cascada las relaciones al borrar un Pedido o un Producto (verificado).
  void _cascade(String table, int id) {
    if (table != 'pedido' && table != 'producto') return;
    _table('pedidoproducto').removeWhere((_, row) {
      final ref = row[table];
      return ref is Map && ref['id'] == id;
    });
  }

  Map<String, dynamic>? _decodeBody(http.Request request) {
    try {
      final decoded = jsonDecode(request.body);
      return decoded is Map<String, dynamic> ? decoded : null;
    } on FormatException {
      return null;
    }
  }

  /// Imita `updateEntityFromMap` del controlador generado: conversión reflexiva campo a campo que
  /// **ignora** en silencio lo que no puede convertir.
  Map<String, dynamic> _fromBody(
    String table,
    Map<String, dynamic> body, {
    bool keepNulls = true,
  }) {
    final row = <String, dynamic>{};
    void put(String key, Object? value) {
      if (value != null || keepNulls) row[key] = value;
    }

    switch (table) {
      case 'producto':
        put('nombre', body['nombre'] is String ? body['nombre'] : null);
        put('precio', _toDouble(body['precio']));
        put('pedidoproducto', const <Object?>[]);
      case 'pedido':
        put('fecha', body['fecha'] is String ? body['fecha'] : null);
        put('pedidoproducto', const <Object?>[]);
      case 'pedidoproducto':
        put('pedido', _relation('pedido', body['pedidoid']));
        put('producto', _relation('producto', body['productoid']));
    }
    return row;
  }

  /// Imita `convertToLong` + `findXById(...).ifPresent(...)`: id numérico existente, si no se ignora.
  Map<String, dynamic>? _relation(String table, Object? value) {
    final id = value is num
        ? value.toInt()
        : (value is String ? int.tryParse(value) : null);
    final target = id == null ? null : _table(table)[id];
    if (target == null) return null;
    return Map<String, dynamic>.of(target)..remove('pedidoproducto');
  }

  double? _toDouble(Object? value) {
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }

  http.Response _json(int status, Object body) => http.Response(
    jsonEncode(body),
    status,
    headers: {'content-type': 'application/json; charset=utf-8'},
  );
}
