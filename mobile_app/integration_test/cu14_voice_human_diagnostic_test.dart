// ignore_for_file: avoid_print
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/app.dart';
import 'package:gestion_movil/app_scope.dart';
import 'package:gestion_movil/data/voice/speech_input.dart';
import 'package:integration_test/integration_test.dart';

/// CU14 · diagnóstico de voz HUMANA real (no sintetizada), en el teléfono real, CON red.
///
/// Con audio sintetizado (TTS del PC) el reconocedor funcionó 5 de 9 veces (ver
/// `docs/decisions.md` sección 6.4). Con la voz real del usuario no reconoció nada. Este test
/// compara dos capas para la MISMA pregunta, sin asumir la causa:
///
///   A) el camino de PRODUCCIÓN (`VoiceAssistantScreen`, plugin `speech_to_text`) — lo que ve el
///      usuario de verdad.
///   B) el listener NATIVO directo (`AsrProbe.kt`, sin el plugin) — código de error real de Android
///      y nivel de audio (`onRmsChanged`), para no depender de lo que el plugin decida exponer.
///
/// Lo orquesta `tool/device-voice-human-test.ps1`: NUNCA reproduce audio sintetizado. En cada marca
/// `MARK:SPEAK_NOW` hay que decirle la frase al teléfono en voz alta, de verdad, ahí mismo.
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
    'diagnóstico: voz humana real — capa de producción (2 intentos) + listener nativo (5 intentos)',
    (tester) async {
      const probe = MethodChannel('gestion_movil/asr_probe');
      const phrase = 'crear producto camisa con precio veinte';

      Future<void> settle() => tester.pumpAndSettle(
        const Duration(milliseconds: 100),
        EnginePhase.sendSemanticsUpdate,
        const Duration(seconds: 30),
      );

      Future<bool> waitUntil(
        bool Function() condition, {
        required Duration timeout,
      }) async {
        final deadline = DateTime.now().add(timeout);
        while (!condition()) {
          if (DateTime.now().isAfter(deadline)) return false;
          await tester.pump(const Duration(milliseconds: 200));
        }
        return true;
      }

      String? textOf(String key) => tester.any(find.byKey(Key(key)))
          ? tester.widget<Text>(find.byKey(Key(key))).data
          : null;

      print('DIAG:PHRASE la frase a decir en cada MARK:SPEAK_NOW es: "$phrase"');

      // ---- 0. Idioma: lo que el dispositivo REPORTA de verdad, sin asumir nada --------------
      final dispatcher = WidgetsBinding.instance.platformDispatcher;
      final resolved = spanishLocaleFor(dispatcher.locale);
      print(
        'DIAG:LOCALE primary=${dispatcher.locale} all=${dispatcher.locales} '
        'resolved_por_spanishLocaleFor=$resolved (esto es lo que usa el asistente real: '
        'SpeechToTextInput._defaultLocale llama a la misma función con el mismo valor)',
      );

      // ---- A. Camino de PRODUCCIÓN: VoiceAssistantScreen, 2 intentos reales -----------------
      final services = await AppServices.bootstrap();
      await tester.pumpWidget(GestionApp(services: services));
      await waitUntil(
        () => services.monitor.isOnline,
        timeout: const Duration(seconds: 30),
      );
      await settle();
      await tester.tap(find.byKey(const Key('open-voice')));
      await settle();

      for (var attempt = 1; attempt <= 2; attempt++) {
        await tester.tap(find.byKey(const Key('voice-mic')));
        final micOpened = await waitUntil(
          () =>
              tester.any(find.text('Escuchando…')) ||
              tester.any(find.byKey(const Key('phase-failed'))),
          timeout: const Duration(seconds: 15),
        );
        print(
          'DIAG:UI intento $attempt micrófono abierto=${micOpened && tester.any(find.text('Escuchando…'))}',
        );
        if (micOpened && tester.any(find.text('Escuchando…'))) {
          print('MARK:SPEAK_NOW ui$attempt');
        }
        final answered = await waitUntil(
          () =>
              tester.any(find.byKey(const Key('phase-confirming'))) ||
              tester.any(find.byKey(const Key('phase-failed'))),
          timeout: const Duration(seconds: 30),
        );
        if (!answered) {
          print('DIAG:UI intento $attempt SIN RESPUESTA (agotó el tiempo)');
        } else if (tester.any(find.byKey(const Key('phase-confirming')))) {
          print(
            'DIAG:UI intento $attempt EXITO transcript="${textOf('voice-transcript')}" '
            'entendido="${textOf('voice-summary')}"',
          );
          await tester.tap(find.byKey(const Key('voice-cancel')));
          await settle();
        } else {
          print(
            'DIAG:UI intento $attempt FALLO titulo="${textOf('voice-failure-title')}" '
            'cuerpo="${textOf('voice-failure-body')}" transcript="${textOf('voice-transcript')}"',
          );
          await tester.tap(find.byKey(const Key('voice-new')));
          await settle();
        }
        await tester.pump(const Duration(seconds: 2));
      }

      // ---- B. Listener NATIVO directo (AsrProbe): 5 intentos, con RMS y codigo real ----------
      final rmsMins = <double>[];
      final rmsMaxs = <double>[];
      for (var attempt = 1; attempt <= 5; attempt++) {
        print('MARK:SPEAK_NOW native$attempt');
        final raw = Map<String, Object?>.from(
          await probe.invokeMethod<Map<Object?, Object?>>('listen', {
                'tag': resolved.replaceAll('_', '-'),
                'preferOffline': false,
                'seconds': 15,
              }) ??
              {},
        );
        final rmsMin = raw['rmsMin'] as double?;
        final rmsMax = raw['rmsMax'] as double?;
        if (rmsMin != null) rmsMins.add(rmsMin);
        if (rmsMax != null) rmsMaxs.add(rmsMax);
        print('DIAG:NATIVE intento $attempt ${jsonEncode(raw)}');
        await tester.pump(const Duration(seconds: 2));
      }

      if (rmsMins.isNotEmpty) {
        print(
          'DIAG:SUMMARY rango de audio (RMS) en los ${rmsMins.length} intentos con sonido: '
          'min=${rmsMins.reduce((a, b) => a < b ? a : b)} '
          'max=${rmsMaxs.reduce((a, b) => a > b ? a : b)} '
          '(referencia de la Fase 0 con voz sintetizada del PC: min=-2.0 max=10.0)',
        );
      } else {
        print(
          'DIAG:SUMMARY ningun intento nativo registro sonido (rmsCount=0 en todos): '
          'el microfono no captó nada, no es un problema de reconocimiento de la frase',
        );
      }

      print('MARK:DONE');
    },
    timeout: const Timeout(Duration(minutes: 8)),
  );
}
