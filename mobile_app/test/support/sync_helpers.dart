import 'package:gestion_movil/domain/entity_module.dart';
import 'package:gestion_movil/domain/pending_op.dart';

import 'fake_backend.dart';
import 'test_env.dart';

/// Backend con datos de partida: dos productos y un pedido.
FakeBackend seededBackend() => FakeBackend()
  ..insert('producto', {'nombre': 'Camisa', 'precio': 19.9})
  ..insert('producto', {'nombre': 'Zapato', 'precio': 40.0})
  ..insert('pedido', {'fecha': '2026-09-01'});

/// La app "recuerda" lo último cargado: se cachea con conexión antes de cortar la red.
Future<void> primeCache(TestEnv env, Iterable<String> paths) async {
  for (final path in paths) {
    await env.gateway(moduleByPath(path)).list();
  }
}

/// Peticiones de escritura que llegaron al servidor, en orden.
List<String> writes(FakeBackend backend) => backend.log
    .where(
      (l) =>
          l.startsWith('POST') || l.startsWith('PUT') || l.startsWith('DELETE'),
    )
    .toList();

/// Cuántos registros de [table] tienen exactamente estos valores.
int countWhere(FakeBackend backend, String table, Map<String, Object?> values) {
  return backend.tables[table]!.values
      .where((row) => values.entries.every((e) => row[e.key] == e.value))
      .length;
}

Future<List<PendingOp>> opsWith(TestEnv env, OpStatus status) async =>
    (await env.ops()).where((o) => o.status == status).toList();

/// Espera (en tiempo real) a que se cumpla una condición; falla con un mensaje si no llega.
Future<void> waitUntil(
  bool Function() condition, {
  Duration timeout = const Duration(seconds: 3),
  String reason = 'la condición nunca se cumplió',
}) async {
  final deadline = DateTime.now().add(timeout);
  while (!condition()) {
    if (DateTime.now().isAfter(deadline)) {
      throw StateError('waitUntil: $reason');
    }
    await Future<void>.delayed(const Duration(milliseconds: 5));
  }
}
