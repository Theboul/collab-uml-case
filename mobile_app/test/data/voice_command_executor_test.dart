import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/data/failures.dart';
import 'package:gestion_movil/data/voice/voice_command_executor.dart';
import 'package:gestion_movil/domain/entity_module.dart';
import 'package:gestion_movil/domain/validators.dart';
import 'package:gestion_movil/models/producto.dart';
import 'package:gestion_movil/domain/voice/text_normalizer.dart';
import 'package:gestion_movil/domain/voice/voice_command.dart';
import 'package:gestion_movil/domain/voice/voice_command_parser.dart';
import 'package:gestion_movil/models/pedido.dart';

import '../support/sync_helpers.dart';
import '../support/test_env.dart';

/// CU14 · Fase 2: un comando de voz/texto produce EXACTAMENTE el mismo efecto que la ruta manual
/// equivalente de CU12 (`RecordFormScreen`/`RecordListScreen`), con el `MemoryLocalStore` y el
/// `TestEnv` de CU13: mismas operaciones en la cola, mismos registros locales, mismas escrituras al
/// servidor. No hay una ruta de prueba paralela.

const _producto = ProductoModule();
const _pedido = PedidoModule();

/// Lo que hacen las pantallas manuales, llamada por llamada (ver `record_form_screen.dart`).
typedef ManualRoute = Future<void> Function(TestEnv env);

class _Scenario {
  const _Scenario(this.name, this.phrase, this.manual);

  final String name;
  final String phrase;
  final ManualRoute manual;
}

final _scenarios = <_Scenario>[
  _Scenario('crear producto', 'crear producto camisa 20', (env) async {
    await env
        .gateway(_producto)
        .create(
          _producto.fromValues(null, {'nombre': 'camisa', 'precio': 20.0}),
        );
  }),
  _Scenario('crear pedido', 'crear pedido fecha 2026-09-21', (env) async {
    await env
        .gateway(_pedido)
        .create(_pedido.fromValues(null, {'fecha': '2026-09-21'}));
  }),
  _Scenario(
    'actualizar el precio de un producto',
    'actualizar producto 1 precio 25',
    (env) async {
      final gateway = env.gateway(_producto);
      final current = await gateway.getById(1);
      final values = {..._producto.valuesOf(current), 'precio': 25.0};
      await gateway.update(1, _producto.fromValues(1, values));
    },
  ),
  _Scenario(
    'actualizar el nombre de un producto',
    'cambiar el nombre del producto 2 a zapato rojo',
    (env) async {
      final gateway = env.gateway(_producto);
      final current = await gateway.getById(2);
      final values = {..._producto.valuesOf(current), 'nombre': 'zapato rojo'};
      await gateway.update(2, _producto.fromValues(2, values));
    },
  ),
  _Scenario(
    'actualizar la fecha de un pedido',
    'actualizar pedido 1 fecha 2026-10-01',
    (env) async {
      final gateway = env.gateway(_pedido);
      final current = await gateway.getById(1);
      await gateway.update(
        1,
        _pedido.fromValues(1, {
          ..._pedido.valuesOf(current),
          'fecha': '2026-10-01',
        }),
      );
    },
  ),
  _Scenario('eliminar un producto', 'eliminar producto 1', (env) async {
    final gateway = env.gateway(_producto);
    await gateway.getById(1); // la pantalla manual consulta antes de confirmar
    await gateway.delete(1);
  }),
  _Scenario('eliminar un pedido', 'borrar el pedido 1', (env) async {
    final gateway = env.gateway(_pedido);
    await gateway.getById(1);
    await gateway.delete(1);
  }),
  _Scenario('listar productos', 'listar productos', (env) async {
    await env.gateway(_producto).list();
  }),
  _Scenario('consultar un producto por id', 'consultar producto 2', (
    env,
  ) async {
    await env.gateway(_producto).getById(2);
  }),
];

/// Todo lo observable del estado de una app, sin lo que es aleatorio o depende del reloj.
Future<Map<String, Object?>> _snapshot(TestEnv env) async => {
  'ops': [
    for (final o in await env.ops())
      {
        'kind': o.kind.name,
        'module': o.module,
        'targetId': o.targetId,
        'values': o.values,
        'base': o.base,
        'status': o.status.name,
        'reason': o.reason.name,
      },
  ],
  'records': {
    for (final path in ['producto', 'pedido', 'pedidoproducto'])
      path: await env.store.readRecords(path),
  },
  'serverTables': {
    for (final e in env.backend.tables.entries)
      e.key: {
        for (final row in e.value.entries)
          row.key: Map<String, Object?>.from(row.value),
      },
  },
  'serverWrites': writes(env.backend),
};

Future<TestEnv> _freshEnv({required bool online}) async {
  final env = await TestEnv.memory(backend: seededBackend());
  await primeCache(env, ['producto', 'pedido', 'pedidoproducto']);
  if (!online) env.goOffline();
  return env;
}

VoiceCommand _command(String spoken) {
  final result = const VoiceCommandParser().parse(normalizeText(spoken));
  expect(
    result,
    isA<VoiceCommand>(),
    reason: 'la frase debe ser un comando válido',
  );
  return result as VoiceCommand;
}

VoiceCommandExecutor _executorFor(TestEnv env) =>
    VoiceCommandExecutor(gatewayFor: env.services.repositoryFor);

void main() {
  for (final online in [true, false]) {
    group(online ? 'CON conexión' : 'SIN conexión', () {
      for (final s in _scenarios) {
        test(
          '${s.name}: la voz deja el mismo estado que la ruta manual',
          () async {
            final manual = await _freshEnv(online: online);
            final voice = await _freshEnv(online: online);
            addTearDown(manual.dispose);
            addTearDown(voice.dispose);

            await s.manual(manual);
            final execution = await _executorFor(voice)
                .execute(_command(s.phrase));

            expect(
              execution,
              isA<VoiceExecuted>(),
              reason: 'obtuvo: $execution',
            );
            expect(await _snapshot(voice), await _snapshot(manual));
          },
        );
      }
    });
  }

  test('sin conexión, crear por voz encola exactamente UNA operación pendiente (igual que el formulario)', () async {
    final env = await _freshEnv(online: false);
    addTearDown(env.dispose);

    final execution = await _executorFor(env)
        .execute(_command('crear producto camisa 20'));

    expect(execution, isA<VoiceExecuted>());
    expect((execution as VoiceExecuted).outcome?.isPending, isTrue);
    final ops = await env.ops();
    expect(ops, hasLength(1));
    expect(ops.single.values, {'nombre': 'camisa', 'precio': 20.0});
    expect(
      writes(env.backend),
      isEmpty,
      reason: 'sin conexión no llegó nada al servidor',
    );
  });

  group(
    'un slot que no valida es datosFaltantes, no un crash, y no escribe nada',
    () {
      final invalid = <(String, String, List<String>)>[
        ('crear producto camisa precio abc', 'crear', ['Precio']),
        ('actualizar producto 1 precio abc', 'actualizar', ['Precio']),
        (
          'crear pedido fecha ${'x' * 300}',
          'crear',
          ['Fecha'],
        ), // supera los 255 caracteres de un varchar
      ];
      for (final (phrase, _, missing) in invalid) {
        test(
          '"${phrase.length > 60 ? '${phrase.substring(0, 60)}…' : phrase}"',
          () async {
            final env = await _freshEnv(online: true);
            addTearDown(env.dispose);
            final before = await _snapshot(env);

            final execution = await _executorFor(env).execute(_command(phrase));

            expect(
              execution,
              isA<VoiceRejected>(),
              reason: 'obtuvo: $execution',
            );
            final failure = (execution as VoiceRejected).failure;
            expect(failure.kind, VoiceErrorKind.datosFaltantes);
            expect(failure.missing, missing);
            expect(
              failure.detail,
              isNotEmpty,
              reason: 'explica por qué no es válido (mensaje del validador)',
            );
            expect(await _snapshot(env), before, reason: 'no se tocó nada');
          },
        );
      }

      test(
        'el mensaje sale del MISMO validador que el formulario manual',
        () async {
          final env = await _freshEnv(online: true);
          addTearDown(env.dispose);

          final execution = await _executorFor(env)
              .execute(_command('crear producto camisa precio abc'));

          final priceField = _producto.fields.firstWhere(
            (f) => f.name == 'precio',
          );
          final expected = FieldValidator.validate(priceField, 'abc');
          expect((execution as VoiceRejected).failure.detail, expected);
        },
      );
    },
  );

  group('un fallo del repositorio llega como el mismo AppFailure que en la ruta manual', () {
    for (final online in [true, false]) {
      test(
        '${online ? 'con' : 'sin'} conexión: eliminar un producto que no existe',
        () async {
          final manual = await _freshEnv(online: online);
          final voice = await _freshEnv(online: online);
          addTearDown(manual.dispose);
          addTearDown(voice.dispose);
          Object? manualFailure;
          try {
            await manual.gateway(_producto).getById(99);
          } on AppFailure catch (f) {
            manualFailure = f;
          }
          expect(
            manualFailure,
            isA<AppFailure>(),
            reason: 'la ruta manual también falla',
          );

          final execution = await _executorFor(voice)
              .execute(_command('eliminar producto 99'));

          expect(
            execution,
            isA<VoiceExecutionError>(),
            reason: 'obtuvo: $execution',
          );
          expect(
            (execution as VoiceExecutionError).failure.userMessage,
            (manualFailure as AppFailure).userMessage,
          );
          expect(await _snapshot(voice), await _snapshot(manual));
        },
      );
    }
  });

  group('consultas: devuelven lo que devuelve el repositorio', () {
    test('listar', () async {
      final env = await _freshEnv(online: true);
      addTearDown(env.dispose);

      final execution = await _executorFor(env)
          .execute(_command('listar productos'));

      final direct = (await env.gateway(_producto).list()).items;
      expect(
        (execution as VoiceExecuted).items.map((e) => e.id),
        direct.map((e) => e.id),
      );
      expect(execution.items.length, 2);
    });

    test('por id, con el mensaje del propio módulo', () async {
      final env = await _freshEnv(online: false);
      addTearDown(env.dispose);

      final execution = await _executorFor(env)
          .execute(_command('consultar producto 1'));

      final direct = await env.gateway(_producto).getById(1) as Producto;
      expect((execution as VoiceExecuted).items.single.id, 1);
      expect(execution.message, contains(_producto.title(direct)));
    });

    test('un pedido nuevo creado por voz aparece al listar', () async {
      final env = await _freshEnv(online: false);
      addTearDown(env.dispose);
      final executor = _executorFor(env);

      await executor.execute(_command('crear pedido fecha 2026-12-01'));
      final listed = await executor.execute(_command('listar pedidos'));

      final fechas = (listed as VoiceExecuted).items.map(
        (e) => (e as Pedido).fecha,
      );
      expect(fechas, contains('2026-12-01'));
    });
  });
}
