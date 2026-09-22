// ignore_for_file: avoid_print
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// CU14 · FASE 0 — ¿hay reconocimiento de voz OFFLINE en español en ESTE teléfono?
///
/// No es parte de la app: es un sondeo aislado que solo mide y reporta. Lo orquesta
/// `tool/device-asr-probe.ps1` (modo avión con adb, permiso de micrófono, frase de prueba).
///
///     flutter test integration_test/cu14_asr_probe_test.dart -d <id> --dart-define=ASR_LOCALE=es_ES
///
/// Cada dato sale como una línea `ASR:*` en el log. Las marcas `MARK:*` sincronizan al orquestador.
const _locale = String.fromEnvironment('ASR_LOCALE', defaultValue: 'es_ES');
const _listenSeconds = int.fromEnvironment(
  'ASR_LISTEN_SECONDS',
  defaultValue: 30,
);
const _onDevice = bool.fromEnvironment('ASR_ON_DEVICE', defaultValue: true);
const _skipListen = bool.fromEnvironment('ASR_SKIP_LISTEN');
const _nativeSeconds = int.fromEnvironment(
  'ASR_NATIVE_SECONDS',
  defaultValue: 12,
);

/// Idiomas a barrer con la escucha nativa, separados por comas (vacío = solo `ASR_LOCALE`).
const _nativeTags = String.fromEnvironment('ASR_NATIVE_TAGS');

/// `false` = CONTROL con red: mismo sondeo sin modo avión, para distinguir "el offline no funciona"
/// de "el micrófono/reconocedor no funciona en absoluto".
const _airplane = bool.fromEnvironment('ASR_AIRPLANE', defaultValue: true);

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('sondeo de ASR offline (español) en el dispositivo real', (
    tester,
  ) async {
    final clock = Stopwatch()..start();
    String t() => '+${(clock.elapsedMilliseconds / 1000).toStringAsFixed(1)}s';
    final summary = <String, Object?>{
      'locale': _locale,
      'onDeviceRequested': _onDevice,
    };

    // ---- 1. Qué dice el SISTEMA (API nativa de Android 13+) -----------------------------
    const probe = MethodChannel('gestion_movil/asr_probe');
    final native = Map<String, Object?>.from(
      await probe.invokeMethod<Map<Object?, Object?>>('check', {
            'tag': _locale.replaceAll('_', '-'),
          }) ??
          {},
    );
    summary['native'] = native;
    print('ASR:NATIVE ${jsonEncode(native)}');

    // ---- 2. Permiso de micrófono + inicialización ---------------------------------------
    final speech = SpeechToText();
    final events = <String>[];
    var maxSound = -100.0;
    var minSound = 100.0;
    var soundEvents = 0;
    final finished = Completer<String>();
    void finish(String why) {
      if (!finished.isCompleted) finished.complete(why);
    }

    print('MARK:PERMISSION_REQUEST');
    final initOk = await speech
        .initialize(
          debugLogging: true,
          onStatus: (s) {
            events.add('${t()} status=$s');
            print('ASR:STATUS ${t()} $s');
            if (s == 'listening') print('MARK:SPEAK_NOW');
            if (s == 'done') finish('status:done');
          },
          onError: (e) {
            events.add('${t()} error=${e.errorMsg} permanent=${e.permanent}');
            print('ASR:ERROR ${t()} ${e.errorMsg} permanent=${e.permanent}');
            finish('error:${e.errorMsg}');
          },
        )
        .timeout(const Duration(seconds: 60), onTimeout: () => false);
    final hasPermission = await speech.hasPermission;
    summary.addAll({
      'initOk': initOk,
      'hasPermission': hasPermission,
      'isAvailable': speech.isAvailable,
    });
    print(
      'ASR:INIT ok=$initOk hasPermission=$hasPermission isAvailable=${speech.isAvailable}',
    );

    // ---- 3. Idiomas que reporta el plugin (con timeout: en Android 13+ puede no responder) --
    List<LocaleName>? locales;
    try {
      locales = await speech.locales().timeout(const Duration(seconds: 10));
    } on TimeoutException {
      locales = null;
    }
    final spanish = (locales ?? [])
        .where((l) => l.localeId.toLowerCase().startsWith('es'))
        .toList();
    summary['localesAnswered'] = locales != null;
    summary['localesCount'] = locales?.length;
    summary['spanishLocales'] = spanish.map((l) => l.localeId).toList();
    print(
      'ASR:LOCALES answered=${locales != null} total=${locales?.length} '
      'spanish=${spanish.map((l) => l.localeId).toList()}',
    );
    try {
      final sys = await speech.systemLocale().timeout(
        const Duration(seconds: 5),
      );
      summary['systemLocale'] = sys?.localeId;
      print('ASR:SYSTEM_LOCALE ${sys?.localeId}');
    } on TimeoutException {
      print('ASR:SYSTEM_LOCALE (sin respuesta)');
    }

    if (!initOk || _skipListen) {
      summary['outcome'] = !initOk ? 'init_failed' : 'listen_skipped';
      print('ASR:SUMMARY ${jsonEncode(summary)}');
      print('MARK:DONE');
      return;
    }

    // ---- 4. Modo avión REAL: se espera a que la red esté caída de verdad ------------------
    var networkDown = false;
    if (_airplane) {
      print('MARK:AIRPLANE_ON');
      final netDeadline = DateTime.now().add(const Duration(seconds: 45));
      while (DateTime.now().isBefore(netDeadline)) {
        try {
          await InternetAddress.lookup('example.com')
              .timeout(const Duration(seconds: 3));
          await Future<void>.delayed(const Duration(seconds: 1));
        } on Object {
          networkDown = true;
          break;
        }
      }
    } else {
      try {
        await InternetAddress.lookup('example.com')
            .timeout(const Duration(seconds: 5));
      } on Object {
        networkDown = true;
      }
    }
    summary['airplane'] = _airplane;
    summary['networkDown'] = networkDown;
    print('ASR:NETWORK_DOWN $networkDown airplane=$_airplane ${t()}');

    // ---- 5. Escuchar: ¿se resuelve sin red? -------------------------------------------------
    print('MARK:LISTEN_BEGIN');
    final results = <Map<String, Object?>>[];
    await speech.listen(
      onResult: (r) {
        results.add({
          'words': r.recognizedWords,
          'final': r.finalResult,
          'confidence': r.confidence,
        });
        print(
          'ASR:RESULT ${t()} final=${r.finalResult} conf=${r.confidence} words="${r.recognizedWords}"',
        );
        if (r.finalResult) finish('final_result');
      },
      onSoundLevelChange: (level) {
        soundEvents++;
        if (level > maxSound) maxSound = level;
        if (level < minSound) minSound = level;
      },
      listenOptions: SpeechListenOptions(
        onDevice: _onDevice,
        partialResults: false,
        cancelOnError: false,
        localeId: _locale,
        listenFor: const Duration(seconds: _listenSeconds),
        pauseFor: const Duration(seconds: 6),
      ),
    );
    final why = await finished.future.timeout(
      const Duration(seconds: _listenSeconds + 15),
      onTimeout: () => 'test_timeout',
    );
    await speech.stop();

    summary.addAll({
      'finishedBecause': why,
      'events': events,
      'results': results,
      'soundEvents': soundEvents,
      'soundMin': soundEvents == 0 ? null : minSound,
      'soundMax': soundEvents == 0 ? null : maxSound,
      'lastError': speech.lastError?.errorMsg,
    });
    print('ASR:SOUND events=$soundEvents min=$minSound max=$maxSound');

    // ---- 6. Escucha DIRECTA del sistema (sin el plugin): cada callback con su tiempo ---------
    // Distingue "el reconocedor del teléfono falla" de "el plugin oculta el error".
    // Barrido por idiomas: un error devuelve en milisegundos; un idioma aceptado espera audio.
    print('MARK:NATIVE_LISTEN_BEGIN');
    final tags = _nativeTags.isEmpty
        ? [_locale.replaceAll('_', '-')]
        : _nativeTags.split(',');
    final sweep = <String, Object?>{};
    for (final tag in tags) {
      final direct = Map<String, Object?>.from(
        await probe.invokeMethod<Map<Object?, Object?>>('listen', {
              'tag': tag,
              'preferOffline': _onDevice,
              'seconds': _nativeSeconds,
            }) ??
            {},
      );
      sweep[tag] = direct['finishedBecause'];
      print(
        'ASR:NATIVE_LISTEN tag=$tag preferOffline=$_onDevice net=${networkDown ? 'DOWN' : 'UP'} '
        '=> ${direct['finishedBecause']}  events=${jsonEncode(direct['events'])}',
      );
      await Future<void>.delayed(const Duration(milliseconds: 500));
    }
    summary['nativeSweep'] = sweep;
    print('ASR:SWEEP ${jsonEncode(sweep)}');
    print('ASR:SUMMARY ${jsonEncode(summary)}');
    print('MARK:DONE');
  }, timeout: const Timeout(Duration(minutes: 6)));
}
