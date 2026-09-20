import 'dart:async';
import 'dart:convert';

import 'package:sqflite/sqflite.dart';

import '../../domain/entity_module.dart';
import '../../domain/field_spec.dart';
import '../../domain/pending_op.dart';

/// Almacenamiento local: lo último cargado de cada entidad y la cola de operaciones pendientes de
/// sincronizar.
///
/// - **Caché** (`records`): solo lo que dice el **servidor** (ids reales, positivos). Lo creado sin
///   conexión no vive aquí: se deriva de la cola (ver `OfflineFirstRepository`), así nunca se mezcla
///   con la verdad del servidor.
/// - **Cola** (`pending_ops`): escrituras FIFO con su estado y motivo.
///
/// [SqliteLocalStore] es la implementación real (app y tests con SQLite); en los tests de widgets se
/// usa una en memoria porque estos no pueden esperar futuros reales de SQLite.
abstract class LocalStore {
  /// Emite cuando cambia la cola o la caché (la UI y el controlador de sincronización lo escuchan).
  Stream<void> get changes;

  Future<void> close();

  /// Abre (o crea) la base SQLite. [path] `null` = ruta estándar de la app.
  static Future<LocalStore> open({
    String? path,
    DatabaseFactory? factory,
    bool singleInstance = true,
  }) => SqliteLocalStore.open(
    path: path,
    factory: factory,
    singleInstance: singleInstance,
  );

  // ---- caché del servidor -----------------------------------------------------------------

  /// Reemplaza la caché de [module] por [records] (lo último cargado del servidor).
  Future<void> replaceRecords(
    String module,
    Map<int, Map<String, Object?>> records,
  );

  Future<void> upsertRecord(String module, int id, Map<String, Object?> values);

  Future<void> removeRecord(String module, int id);

  Future<Map<int, Map<String, Object?>>> readRecords(String module);

  Future<Map<String, Object?>?> readRecord(String module, int id);

  // ---- cola de operaciones ----------------------------------------------------------------

  /// Siguiente id temporal (negativo) para un registro creado sin conexión.
  Future<int> nextTempId();

  /// Inserta al final de la cola y devuelve la operación con su `seq`.
  Future<PendingOp> insertOp(PendingOp op);

  Future<void> saveOp(PendingOp op);

  Future<void> deleteOp(String opId);

  Future<PendingOp?> opById(String opId);

  /// Todas las operaciones en orden de encolado.
  Future<List<PendingOp>> allOps();

  // ---- derivados --------------------------------------------------------------------------

  Future<List<PendingOp>> activeOps() async =>
      (await allOps()).where((o) => o.isActive).toList();

  /// Borra las operaciones ya sincronizadas más antiguas, dejando las últimas [keep].
  Future<void> pruneSynced({int keep = 30}) async {
    final synced = (await allOps())
        .where((o) => o.status == OpStatus.synced)
        .toList();
    final excess = (synced.length - keep).clamp(0, synced.length);
    for (final op in synced.take(excess)) {
      await deleteOp(op.opId);
    }
  }

  /// Quita de la caché los registros que referencian [id] de [targetModule] (el servidor los borra
  /// en cascada al borrar el padre).
  Future<void> removeRecordsReferencing(String targetModule, int id) async {
    for (final module in allModules) {
      final refs = module.fields
          .where(
            (f) =>
                f.type == FieldType.reference && f.referenceTo == targetModule,
          )
          .map((f) => f.name);
      if (refs.isEmpty) continue;
      final records = await readRecords(module.path);
      for (final entry in records.entries) {
        if (refs.any((name) => entry.value[name] == id)) {
          await removeRecord(module.path, entry.key);
        }
      }
    }
  }

  /// Sustituye el id temporal [from] por el real [to] en toda la cola: el id del propio registro y
  /// las referencias de otras operaciones (p. ej. la relación que apunta a un Pedido creado offline).
  Future<void> remapTempId(String module, int from, int to) async {
    for (final op in await allOps()) {
      var changed = false;
      var targetId = op.targetId;
      if (op.module == module && targetId == from) {
        targetId = to;
        changed = true;
      }
      final values = Map<String, Object?>.of(op.values);
      for (final field in moduleByPath(op.module).fields) {
        if (field.type == FieldType.reference &&
            field.referenceTo == module &&
            values[field.name] == from) {
          values[field.name] = to;
          changed = true;
        }
      }
      if (changed) {
        await saveOp(op.copyWith(targetId: targetId, values: values));
      }
    }
  }
}

/// Implementación SQLite (sqflite): tablas `records`, `pending_ops` y `meta` (contador de ids temporales).
class SqliteLocalStore extends LocalStore {
  SqliteLocalStore._(this._db);

  final Database _db;
  final StreamController<void> _changes = StreamController<void>.broadcast();

  static const int _schemaVersion = 1;
  static const String _dbName = 'gestion_movil.db';

  static Future<SqliteLocalStore> open({
    String? path,
    DatabaseFactory? factory,
    bool singleInstance = true,
  }) async {
    final f = factory ?? databaseFactory;
    final dbPath = path ?? '${await f.getDatabasesPath()}/$_dbName';
    final db = await f.openDatabase(
      dbPath,
      options: OpenDatabaseOptions(
        version: _schemaVersion,
        singleInstance: singleInstance,
        onCreate: (db, _) async {
          await db.execute('''
            CREATE TABLE records (
              module TEXT NOT NULL,
              id INTEGER NOT NULL,
              json TEXT NOT NULL,
              PRIMARY KEY (module, id)
            )''');
          await db.execute('''
            CREATE TABLE pending_ops (
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              op_id TEXT NOT NULL UNIQUE,
              module TEXT NOT NULL,
              kind TEXT NOT NULL,
              target_id INTEGER NOT NULL,
              values_json TEXT NOT NULL,
              base_json TEXT,
              status TEXT NOT NULL,
              reason_code TEXT,
              detail TEXT,
              attempts INTEGER NOT NULL DEFAULT 0,
              force INTEGER NOT NULL DEFAULT 0,
              pre_send_ids TEXT,
              result_id INTEGER,
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            )''');
          await db.execute(
            'CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)',
          );
        },
      ),
    );
    return SqliteLocalStore._(db);
  }

  @override
  Stream<void> get changes => _changes.stream;

  @override
  Future<void> close() async {
    await _changes.close();
    await _db.close();
  }

  void _notify() {
    if (!_changes.isClosed) _changes.add(null);
  }

  // ---- caché ------------------------------------------------------------------------------

  @override
  Future<void> replaceRecords(
    String module,
    Map<int, Map<String, Object?>> records,
  ) async {
    await _db.transaction((txn) async {
      await txn.delete('records', where: 'module = ?', whereArgs: [module]);
      final batch = txn.batch();
      records.forEach((id, values) {
        batch.insert('records', {
          'module': module,
          'id': id,
          'json': jsonEncode(values),
        });
      });
      await batch.commit(noResult: true);
    });
    _notify();
  }

  @override
  Future<void> upsertRecord(
    String module,
    int id,
    Map<String, Object?> values,
  ) async {
    await _db.insert('records', {
      'module': module,
      'id': id,
      'json': jsonEncode(values),
    }, conflictAlgorithm: ConflictAlgorithm.replace);
    _notify();
  }

  @override
  Future<void> removeRecord(String module, int id) async {
    await _db.delete(
      'records',
      where: 'module = ? AND id = ?',
      whereArgs: [module, id],
    );
    _notify();
  }

  @override
  Future<Map<int, Map<String, Object?>>> readRecords(String module) async {
    final rows = await _db.query(
      'records',
      where: 'module = ?',
      whereArgs: [module],
      orderBy: 'id',
    );
    return {
      for (final row in rows)
        row['id']! as int: Map<String, Object?>.from(
          jsonDecode(row['json']! as String) as Map,
        ),
    };
  }

  @override
  Future<Map<String, Object?>?> readRecord(String module, int id) async {
    final rows = await _db.query(
      'records',
      where: 'module = ? AND id = ?',
      whereArgs: [module, id],
    );
    if (rows.isEmpty) return null;
    return Map<String, Object?>.from(
      jsonDecode(rows.single['json']! as String) as Map,
    );
  }

  // ---- cola -------------------------------------------------------------------------------

  @override
  Future<int> nextTempId() {
    return _db.transaction((txn) async {
      final rows = await txn.query(
        'meta',
        where: 'key = ?',
        whereArgs: ['temp_id'],
      );
      final next =
          (rows.isEmpty ? 0 : int.parse(rows.single['value']! as String)) - 1;
      await txn.insert('meta', {
        'key': 'temp_id',
        'value': '$next',
      }, conflictAlgorithm: ConflictAlgorithm.replace);
      return next;
    });
  }

  @override
  Future<PendingOp> insertOp(PendingOp op) async {
    final seq = await _db.insert('pending_ops', op.toRow()..remove('seq'));
    _notify();
    return PendingOp.fromRow({...op.toRow(), 'seq': seq});
  }

  @override
  Future<void> saveOp(PendingOp op) async {
    await _db.update(
      'pending_ops',
      op.toRow()..remove('seq'),
      where: 'op_id = ?',
      whereArgs: [op.opId],
    );
    _notify();
  }

  @override
  Future<void> deleteOp(String opId) async {
    await _db.delete('pending_ops', where: 'op_id = ?', whereArgs: [opId]);
    _notify();
  }

  @override
  Future<PendingOp?> opById(String opId) async {
    final rows = await _db.query(
      'pending_ops',
      where: 'op_id = ?',
      whereArgs: [opId],
    );
    return rows.isEmpty ? null : PendingOp.fromRow(rows.single);
  }

  @override
  Future<List<PendingOp>> allOps() async {
    final rows = await _db.query('pending_ops', orderBy: 'seq');
    return rows.map(PendingOp.fromRow).toList();
  }
}
