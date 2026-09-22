import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/app.dart';
import 'package:gestion_movil/data/voice/speech_input.dart';
import 'package:gestion_movil/domain/pending_op.dart';
import 'package:gestion_movil/domain/voice/voice_command.dart';
import 'package:gestion_movil/ui/voice/voice_failure_messages.dart';

import '../support/fake_backend.dart';
import '../support/fake_speech_input.dart';
import '../support/sync_helpers.dart';
import '../support/test_env.dart';

/// CU14 · el asistente: dos entradas (voz y texto) al mismo parser y al mismo repositorio, con los
/// estados del flujo y un mensaje distinto por cada excepción de la ficha.
void main() {
  late FakeBackend backend;
  late TestEnv env;
  late FakeSpeechInput speech;

  Future<void> openAssistant(
    WidgetTester tester, {
    bool online = true,
    SpeechCapture? heard,
  }) async {
    backend = seededBackend();
    speech = FakeSpeechInput(heard);
    env = await TestEnv.memory(
      online: online,
      backend: backend,
      speech: speech,
    );
    await primeCache(env, ['producto', 'pedido', 'pedidoproducto']);
    if (!online) env.goOffline();
    await tester.pumpWidget(GestionApp(services: env.services));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('open-voice')));
    await tester.pumpAndSettle();
  }

  Future<void> type(WidgetTester tester, String text) async {
    await tester.enterText(find.byKey(const Key('voice-text')), text);
    await tester.pump();
  }

  Future<void> send(WidgetTester tester, String text) async {
    await type(tester, text);
    await tester.tap(find.byKey(const Key('voice-send')));
    await tester.pumpAndSettle();
  }

  Future<void> tapAndSettle(WidgetTester tester, String key) async {
    await tester.tap(find.byKey(Key(key)));
    await tester.pumpAndSettle();
  }

  String textOf(WidgetTester tester, String key) =>
      tester.widget<Text>(find.byKey(Key(key))).data ?? '';

  Finder phase(VoicePhaseName name) => find.byKey(Key('phase-$name'));

  group('texto: el flujo y sus estados', () {
    testWidgets('empieza listo; al escribir pasa a "escribiendo"', (
      tester,
    ) async {
      await openAssistant(tester);
      expect(phase('idle'), findsOneWidget);

      await type(tester, 'crear producto');

      expect(phase('typing'), findsOneWidget);
    });

    testWidgets('crear: procesa, pide confirmar y solo entonces escribe', (
      tester,
    ) async {
      await openAssistant(tester);

      await send(tester, 'crear producto camisa 20');

      expect(phase('confirming'), findsOneWidget);
      expect(textOf(tester, 'voice-summary'), contains('Crear Producto'));
      expect(textOf(tester, 'voice-summary'), contains('Nombre: camisa'));
      expect(textOf(tester, 'voice-summary'), contains('Precio: 20'));
      expect(backend.count('producto'), 2, reason: 'aún no se escribió nada');

      await tapAndSettle(tester, 'voice-confirm');

      expect(phase('executed'), findsOneWidget);
      expect(textOf(tester, 'voice-result'), contains('creado correctamente'));
      expect(backend.count('producto'), 3);
      expect(
        countWhere(backend, 'producto', {'nombre': 'camisa', 'precio': 20.0}),
        1,
      );
    });

    testWidgets(
      'SIN conexión: se guarda local y queda PENDIENTE (igual que el formulario)',
      (tester) async {
        await openAssistant(tester, online: false);

        await send(tester, 'crear producto camisa 20');
        await tapAndSettle(tester, 'voice-confirm');

        expect(phase('executed'), findsOneWidget);
        expect(
          textOf(tester, 'voice-result'),
          contains('pendiente de sincronizar'),
        );
        expect(backend.count('producto'), 2, reason: 'nada llegó al servidor');
        final ops = await env.ops();
        expect(ops, hasLength(1));
        expect(ops.single.kind, OpKind.create);
        expect(ops.single.status, OpStatus.pending);
        expect(ops.single.values, {'nombre': 'camisa', 'precio': 20.0});
      },
    );

    testWidgets('consultar no pide confirmación: ejecuta y muestra los datos', (
      tester,
    ) async {
      await openAssistant(tester);

      await send(tester, 'listar productos');

      expect(phase('executed'), findsOneWidget);
      expect(textOf(tester, 'voice-result'), contains('2 registro(s)'));
      expect(find.byKey(const Key('voice-item-1')), findsOneWidget);
      expect(find.byKey(const Key('voice-confirm')), findsNothing);
    });

    testWidgets('eliminar avisa de que no se puede deshacer y pide confirmar', (
      tester,
    ) async {
      await openAssistant(tester);

      await send(tester, 'eliminar producto 1');

      expect(phase('confirming'), findsOneWidget);
      expect(find.byKey(const Key('voice-delete-warning')), findsOneWidget);
      expect(backend.count('producto'), 2);

      await tapAndSettle(tester, 'voice-confirm');

      expect(
        textOf(tester, 'voice-result'),
        contains('eliminado correctamente'),
      );
      expect(backend.count('producto'), 1);
    });

    testWidgets('un segundo comando tras "Nuevo comando" también se procesa', (
      tester,
    ) async {
      await openAssistant(tester, online: false);
      await send(tester, 'crear producto camisa 20');
      await tapAndSettle(tester, 'voice-confirm');
      expect(phase('executed'), findsOneWidget);

      await tapAndSettle(tester, 'voice-new');
      expect(phase('idle'), findsOneWidget);
      await send(tester, 'listar productos');

      expect(
        phase('executed'),
        findsOneWidget,
        reason: 'el segundo comando llegó a ejecutarse',
      );
      expect(
        find.text('camisa'),
        findsOneWidget,
        reason: 'la consulta ve lo creado sin red',
      );
    });

    testWidgets('cancelar descarta lo entendido sin ejecutar nada', (
      tester,
    ) async {
      await openAssistant(tester);
      await send(tester, 'crear producto camisa 20');

      await tapAndSettle(tester, 'voice-cancel');

      expect(phase('idle'), findsOneWidget);
      expect(backend.count('producto'), 2);
      expect(await env.ops(), isEmpty);
    });

    testWidgets(
      'un fallo del repositorio se muestra con el mismo texto que las pantallas manuales',
      (tester) async {
        await openAssistant(tester);
        await send(tester, 'eliminar producto 99');
        await tapAndSettle(tester, 'voice-confirm');

        expect(phase('failed'), findsOneWidget);
        expect(find.byKey(const Key('voice-error')), findsOneWidget);
        expect(
          textOf(tester, 'voice-failure-body'),
          contains('No existe Producto con ID 99'),
        );
      },
    );
  });

  group('las 5 excepciones: cada una con su mensaje específico', () {
    testWidgets('accionInexistente', (tester) async {
      await openAssistant(tester);

      await send(tester, 'hola buenos dias');

      expect(phase('failed'), findsOneWidget);
      expect(
        find.byKey(const Key('voice-failure-accionInexistente')),
        findsOneWidget,
      );
      expect(textOf(tester, 'voice-failure-title'), 'Esa acción no existe');
      expect(
        textOf(tester, 'voice-failure-body'),
        contains('crear, consultar'),
      );
    });

    testWidgets('intencionAmbigua: muestra qué entendió y entre qué duda', (
      tester,
    ) async {
      await openAssistant(tester);

      await send(tester, 'crear camisa 20');

      expect(
        find.byKey(const Key('voice-failure-intencionAmbigua')),
        findsOneWidget,
      );
      final body = textOf(tester, 'voice-failure-body');
      expect(body, contains('Entendí: Acción: crear'));
      expect(body, contains('Dudo entre: Pedido o Producto'));
    });

    testWidgets('datosFaltantes: muestra qué falta', (tester) async {
      await openAssistant(tester);

      await send(tester, 'crear producto camisa');

      expect(
        find.byKey(const Key('voice-failure-datosFaltantes')),
        findsOneWidget,
      );
      final body = textOf(tester, 'voice-failure-body');
      expect(body, contains('Nombre: camisa'), reason: 'lo que sí entendió');
      expect(body, contains('Falta: Precio'), reason: 'lo que falta');
    });

    testWidgets(
      'datosFaltantes por un slot inválido: no llega a pedir confirmación ni escribe',
      (tester) async {
        await openAssistant(tester);

        await send(tester, 'crear producto camisa precio abc');

        expect(phase('failed'), findsOneWidget);
        expect(
          find.byKey(const Key('voice-failure-datosFaltantes')),
          findsOneWidget,
        );
        expect(find.byKey(const Key('voice-confirm')), findsNothing);
        final body = textOf(tester, 'voice-failure-body');
        expect(body, contains('Falta: Precio'));
        expect(
          body,
          contains('debe ser un número'),
          reason: 'el mensaje del validador de CU12',
        );
        expect(backend.count('producto'), 2);
        expect(await env.ops(), isEmpty);
      },
    );

    testWidgets(
      'recursosInsuficientes: voz sin conexión, sin intentar escuchar',
      (tester) async {
        await openAssistant(tester, online: false);

        await tapAndSettle(tester, 'voice-mic');

        expect(phase('failed'), findsOneWidget);
        expect(
          find.byKey(const Key('voice-failure-recursosInsuficientes')),
          findsOneWidget,
        );
        expect(
          textOf(tester, 'voice-failure-body'),
          contains('necesita conexión'),
        );
        expect(
          textOf(tester, 'voice-failure-body'),
          contains('campo de texto'),
        );
        expect(speech.listenCalls, 0, reason: 'sin red ni se intenta escuchar');
      },
    );

    testWidgets('vozNoReconocida', (tester) async {
      await openAssistant(
        tester,
        heard: SpeechFailed(speechErrorToFailure('error_no_match')),
      );

      await tapAndSettle(tester, 'voice-mic');

      expect(
        find.byKey(const Key('voice-failure-vozNoReconocida')),
        findsOneWidget,
      );
      expect(textOf(tester, 'voice-failure-title'), 'No se reconoció la voz');
    });

    testWidgets(
      'recursosInsuficientes desde el reconocedor: idioma no disponible',
      (tester) async {
        await openAssistant(
          tester,
          heard: SpeechFailed(
            speechErrorToFailure('error_language_not_supported'),
          ),
        );

        await tapAndSettle(tester, 'voice-mic');

        expect(
          find.byKey(const Key('voice-failure-recursosInsuficientes')),
          findsOneWidget,
        );
        expect(
          textOf(tester, 'voice-failure-body'),
          contains('español no está disponible'),
        );
      },
    );

    test('los 5 mensajes tienen título y texto distintos', () {
      final failures = [
        for (final kind in VoiceErrorKind.values)
          VoiceFailure(
            kind,
            understood: const ['Acción: crear'],
            candidates: const ['A', 'B'],
          ),
      ];
      final messages = [for (final f in failures) voiceMessageFor(f)];

      expect({for (final m in messages) m.title}, hasLength(5));
      expect({for (final m in messages) m.body}, hasLength(5));
    });
  });

  group('voz: la misma tubería que el texto', () {
    testWidgets(
      'lo dictado llega al mismo comando y conserva tildes y mayúsculas',
      (tester) async {
        await openAssistant(
          tester,
          heard: const SpeechHeard('Crear producto Camisón 20'),
        );

        await tapAndSettle(tester, 'voice-mic');

        expect(phase('confirming'), findsOneWidget);
        expect(textOf(tester, 'voice-summary'), contains('Nombre: Camisón'));
        expect(
          textOf(tester, 'voice-transcript'),
          '"Crear producto Camisón 20"',
        );
        await tapAndSettle(tester, 'voice-confirm');
        expect(
          countWhere(backend, 'producto', {
            'nombre': 'Camisón',
            'precio': 20.0,
          }),
          1,
        );
      },
    );

    testWidgets('voz y texto producen el mismo resumen', (tester) async {
      await openAssistant(
        tester,
        heard: const SpeechHeard('crear producto camisa 20'),
      );
      await tapAndSettle(tester, 'voice-mic');
      final byVoice = textOf(tester, 'voice-summary');
      await tapAndSettle(tester, 'voice-cancel');

      await send(tester, 'crear producto camisa 20');

      expect(textOf(tester, 'voice-summary'), byVoice);
    });

    testWidgets(
      'hasta que el micrófono está abierto dice "Abriendo micrófono…", y luego "Escuchando…"',
      (tester) async {
        await openAssistant(tester);
        speech
          ..hold = true
          ..deferReady = true;

        await tester.tap(find.byKey(const Key('voice-mic')));
        await tester.pump();
        await tester.pump();

        expect(phase('listening'), findsOneWidget);
        expect(find.text('Abriendo micrófono…'), findsOneWidget);
        expect(find.text('Escuchando…'), findsNothing);

        speech.markReady();
        await tester.pump();

        expect(find.text('Escuchando…'), findsOneWidget);
        expect(find.text('Abriendo micrófono…'), findsNothing);
      },
    );

    testWidgets(
      'el idioma de reconocimiento es el del dispositivo salvo que se elija otro',
      (tester) async {
        await openAssistant(
          tester,
          heard: const SpeechHeard('listar productos'),
        );
        await tapAndSettle(tester, 'voice-mic');
        expect(
          speech.lastLocale,
          isNull,
          reason: 'automático: decide el dispositivo',
        );
        await tapAndSettle(tester, 'voice-new');

        await tapAndSettle(tester, 'voice-locale');
        await tester.tap(find.text('Español (Latinoamérica)').last);
        await tester.pumpAndSettle();
        await tapAndSettle(tester, 'voice-mic');

        expect(speech.lastLocale, 'es_419');
      },
    );

    testWidgets('mientras escucha se ve "escuchando" y se puede detener', (
      tester,
    ) async {
      await openAssistant(tester);
      speech.hold = true;

      await tester.tap(find.byKey(const Key('voice-mic')));
      await tester.pump();
      await tester.pump();

      expect(phase('listening'), findsOneWidget);
      expect(find.text('Detener'), findsOneWidget);

      await tester.tap(find.byKey(const Key('voice-mic')));
      await tester.pumpAndSettle();

      expect(phase('idle'), findsOneWidget);
      expect(speech.cancelCalls, 1);
    });

    testWidgets('el resultado tardío de una escucha cancelada se ignora', (
      tester,
    ) async {
      await openAssistant(tester);
      speech.hold = true;
      speech.completeOnCancel = false;
      await tester.tap(find.byKey(const Key('voice-mic')));
      await tester.pump();
      await tester.pump();
      await tester.tap(find.byKey(const Key('voice-mic'))); // detener
      await tester.pumpAndSettle();

      speech.complete(const SpeechHeard('crear producto camisa 20'));
      await tester.pumpAndSettle();

      expect(phase('idle'), findsOneWidget);
      expect(find.byKey(const Key('voice-confirm')), findsNothing);
    });
  });
}

typedef VoicePhaseName = String;
