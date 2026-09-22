// ignore_for_file: avoid_print
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/app.dart';
import 'package:gestion_movil/app_scope.dart';
import 'package:gestion_movil/data/api_client.dart';
import 'package:gestion_movil/domain/voice/text_normalizer.dart';
import 'package:integration_test/integration_test.dart';

/// CU14 en un teléfono REAL, CON red: el botón de voz de punta a punta.
///
/// Micrófono real → reconocedor de Google (`speech_to_text`, `onDevice: false`) → parser → confirmación
/// → repositorio → backend Spring real. Hay que decirle al teléfono "crear producto camisa 20" (o
/// reproducirlo con una voz sintetizada delante del micrófono: ver `tool/device-voice-test.ps1`).
///
/// No fija la frase exacta: comprueba que lo que llegó a hablarse produjo un `VoiceCommand` válido y
/// que ESE comando quedó en el servidor real.
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('con red: hablarle al teléfono crea un registro real a través del asistente', (
    tester,
  ) async {
    final server = ApiClient();

    Future<Map<int, String>> products() async {
      final response = await server.send('GET', 'producto');
      return {
        for (final m in RegExp(
          '"id":(\\d+),"nombre":"([^"]*)"',
        ).allMatches(response.body))
          int.parse(m[1]!): m[2]!,
      };
    }

    Future<void> settle() => tester.pumpAndSettle(
      const Duration(milliseconds: 100),
      EnginePhase.sendSemanticsUpdate,
      const Duration(seconds: 30),
    );

    Future<void> waitFor(
      bool Function() condition, {
      required Duration timeout,
      required String reason,
    }) async {
      final deadline = DateTime.now().add(timeout);
      while (!condition()) {
        if (DateTime.now().isAfter(deadline)) fail('Tiempo agotado: $reason');
        await tester.pump(const Duration(milliseconds: 200));
      }
    }

    bool shown(String key) => tester.any(find.byKey(Key(key)));
    String textOf(String key) =>
        tester.widget<Text>(find.byKey(Key(key))).data ?? '';

    final before = await products();

    final services = await AppServices.bootstrap();
    await tester.pumpWidget(GestionApp(services: services));
    await waitFor(
      () => services.monitor.isOnline,
      timeout: const Duration(seconds: 30),
      reason: 'la app no llegó a "en línea" al iniciar',
    );
    await settle();
    print(
      'EVIDENCIA 1 · con conexión: monitor.isOnline=${services.monitor.isOnline}, productos en el servidor: ${before.length}',
    );

    await tester.tap(find.byKey(const Key('open-voice')));
    await settle();
    expect(find.byKey(const Key('phase-idle')), findsOneWidget);

    // ---- El micrófono real (hasta 4 intentos: el reconocedor a veces no capta la frase) -----
    var understood = false;
    for (var attempt = 1; attempt <= 4 && !understood; attempt++) {
      await tester.tap(find.byKey(const Key('voice-mic')));
      await waitFor(
        () =>
            shown('phase-listening') ||
            shown('phase-failed') ||
            shown('phase-confirming'),
        timeout: const Duration(seconds: 20),
        reason: 'el asistente no pasó a "escuchando"',
      );
      // Solo cuando el micrófono ya está abierto ("Escuchando…"; antes dice "Abriendo micrófono…").
      await waitFor(
        () =>
            tester.any(find.text('Escuchando…')) ||
            shown('phase-failed') ||
            shown('phase-confirming'),
        timeout: const Duration(seconds: 20),
        reason: 'el micrófono no llegó a abrirse',
      );
      if (tester.any(find.text('Escuchando…'))) {
        print(
          'EVIDENCIA · intento $attempt: fase "Escuchando…" con el micrófono abierto',
        );
        print(
          'MARK:SPEAK_NOW hora_telefono=${DateTime.now().toIso8601String().substring(11, 23)}',
        );
      }
      await waitFor(
        () => shown('phase-confirming') || shown('phase-failed'),
        timeout: const Duration(seconds: 60),
        reason: 'no llegó ni un comando ni una excepción (intento $attempt)',
      );
      if (shown('phase-confirming')) {
        understood = true;
      } else {
        final heard = shown('voice-transcript')
            ? textOf('voice-transcript')
            : '(el reconocedor no devolvió texto)';
        print(
          'EVIDENCIA · intento $attempt: el reconocedor oyó $heard → excepción '
          '"${textOf('voice-failure-title')}": ${textOf('voice-failure-body')}',
        );
        await tester.tap(find.byKey(const Key('voice-new')));
        await settle();
        // El reconocedor necesita liberar el micrófono antes de otra escucha (si no: error de audio).
        await tester.pump(const Duration(seconds: 3));
      }
    }
    expect(
      understood,
      isTrue,
      reason: 'ningún intento produjo un comando válido',
    );

    final transcript = textOf('voice-transcript');
    final summary = textOf('voice-summary');
    print('EVIDENCIA 2 · el reconocedor transcribió: $transcript');
    print('EVIDENCIA 3 · el parser lo entendió como: $summary');
    expect(
      summary,
      startsWith('Crear Producto'),
      reason: 'se esperaba "crear producto …": $transcript',
    );
    print('MARK:SHOT_CONFIRM');
    await tester.pump(const Duration(seconds: 2));

    // ---- Confirmar: llega al repositorio y al backend real -------------------------------------
    await tester.tap(find.byKey(const Key('voice-confirm')));
    await settle();
    expect(find.byKey(const Key('phase-executed')), findsOneWidget);
    print('EVIDENCIA 4 · resultado en pantalla: ${textOf('voice-result')}');

    final after = await products();
    final created = {
      for (final e in after.entries)
        if (!before.containsKey(e.key)) e.key: e.value,
    };
    expect(
      created,
      hasLength(1),
      reason: 'debe haber exactamente un producto nuevo en el servidor',
    );
    final name = created.values.single;
    expect(
      normalizeText(transcript),
      contains(normalizeText(name)),
      reason: 'el nombre guardado sale de lo que se dijo',
    );
    print(
      'EVIDENCIA 5 · en el servidor REAL: nuevo producto id=${created.keys.single} nombre="$name" (sale de la transcripción)',
    );
    print('MARK:SHOT_EXECUTED');
    await tester.pump(const Duration(seconds: 2));

    // ---- limpieza en el servidor real ------------------------------------------------------------
    await server.send('DELETE', 'producto/${created.keys.single}');
    print('MARK:DONE');
  }, timeout: const Timeout(Duration(minutes: 8)));
}
