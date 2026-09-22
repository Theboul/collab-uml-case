// ignore_for_file: avoid_print
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/app.dart';
import 'package:gestion_movil/app_scope.dart';
import 'package:gestion_movil/data/api_client.dart';
import 'package:gestion_movil/domain/pending_op.dart';
import 'package:integration_test/integration_test.dart';

/// CU14 en un teléfono REAL, en MODO AVIÓN real, por el CAMPO DE TEXTO (la voz no es testeable
/// offline en este hardware: ver `docs/decisions.md`).
///
/// Lo orquesta `tool/device-voice-test.ps1 -Mode offline`, que activa/desactiva el modo avión con
/// `adb` al ver las marcas `MARK:*` y saca capturas.
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('modo avión: el asistente por texto crea y consulta en local, dispara las excepciones sin red '
      'y lo pendiente se sincroniza solo', (tester) async {
    final name = 'Voz${DateTime.now().millisecondsSinceEpoch}';
    final server =
        ApiClient(); // "otro observador": lo que hay REALMENTE en el servidor

    Future<int> onServer() async {
      final response = await server.send('GET', 'producto');
      return RegExp('"nombre":"$name"').allMatches(response.body).length;
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
        await tester.pump(const Duration(milliseconds: 250));
      }
    }

    Future<void> tapKey(String key) async {
      await tester.tap(find.byKey(Key(key)));
      await settle();
    }

    /// Como un usuario: toca el campo (lo enfoca), escribe y pulsa "Enviar". Sin el toque, tras un
    /// `unfocus()` el campo no tiene conexión de teclado y `enterText` no surte efecto en el teléfono.
    Future<void> say(String text) async {
      await tester.tap(find.byKey(const Key('voice-text')));
      await tester.pump(const Duration(milliseconds: 200));
      await tester.enterText(find.byKey(const Key('voice-text')), text);
      await tester.pump();
      expect(
        tester
            .widget<TextField>(find.byKey(const Key('voice-text')))
            .controller
            ?.text,
        text,
        reason: 'el campo debe contener lo escrito antes de enviar',
      );
      await tester.tap(find.byKey(const Key('voice-send')));
      await settle();
    }

    String textOf(String key) =>
        tester.widget<Text>(find.byKey(Key(key))).data ?? '';

    /// La fase que muestra el asistente ahora (y el error, si lo hay): para diagnosticar.
    String phaseNow() {
      const phases = [
        'idle',
        'typing',
        'listening',
        'processing',
        'confirming',
        'executing',
        'executed',
        'failed',
      ];
      final shown = [
        for (final p in phases)
          if (tester.any(find.byKey(Key('phase-$p')))) p,
      ];
      final failure = tester.any(find.byKey(const Key('voice-failure-title')))
          ? ' · error="${textOf('voice-failure-title')}: ${textOf('voice-failure-body')}"'
          : '';
      return '${shown.join('+')}$failure';
    }

    void expectPhase(String name, String how) => expect(
      find.byKey(Key('phase-$name')),
      findsOneWidget,
      reason: '$how: se esperaba la fase "$name" y hay "${phaseNow()}"',
    );

    // ---- 1. Sesión normal, con conexión ---------------------------------------------------
    final services = await AppServices.bootstrap();
    await tester.pumpWidget(GestionApp(services: services));
    await waitFor(
      () => services.monitor.isOnline,
      timeout: const Duration(seconds: 30),
      reason: 'la app no llegó a "en línea" al iniciar',
    );
    await settle();
    print(
      'EVIDENCIA 1 · con conexión: monitor.isOnline=${services.monitor.isOnline}',
    );

    // ---- 2. Modo avión REAL ---------------------------------------------------------------
    print('MARK:AIRPLANE_ON');
    await waitFor(
      () => !services.monitor.isOnline,
      timeout: const Duration(seconds: 60),
      reason: 'la app no detectó el modo avión',
    );
    await settle();
    expect(find.byKey(const Key('banner-offline')), findsOneWidget);
    print(
      'EVIDENCIA 2 · modo avión detectado: monitor.isOnline=${services.monitor.isOnline}, banner "Sin conexión" visible',
    );

    await tapKey('open-voice');
    expectPhase('idle', 'al abrir el asistente');

    // ---- 3. ÉXITO: crear por texto, sin red ------------------------------------------------
    await say('crear producto $name 20');
    expectPhase('confirming', 'tras escribir el comando de crear');
    print(
      'EVIDENCIA 3 · escrito "crear producto $name 20" → entendido: ${textOf('voice-summary')}',
    );
    await tapKey('voice-confirm');
    expectPhase('executed', 'tras confirmar la creación');
    expect(textOf('voice-result'), contains('pendiente de sincronizar'));

    final pending = (await services.store.allOps()).single;
    expect(pending.kind, OpKind.create);
    expect(pending.status, OpStatus.pending);
    expect(
      pending.values['nombre'],
      name,
      reason: 'mayúsculas conservadas del texto original',
    );
    expect(pending.values['precio'], 20.0);
    expect(
      await onServer(),
      0,
      reason: 'sin conexión NO llegó nada al servidor',
    );
    print(
      'EVIDENCIA 4 · resultado en pantalla: "${textOf('voice-result')}" · SQLite del teléfono: '
      'op=${pending.opId} kind=${pending.kind.name} status=${pending.status.name} '
      'nombre=${pending.values['nombre']} precio=${pending.values['precio']} · en el servidor: ${await onServer()} filas',
    );
    print('MARK:SHOT_CREATED');
    await tester.pump(const Duration(seconds: 3));

    // ---- 4. ÉXITO: consultar por texto, sin red (ve lo pendiente) --------------------------
    await tapKey('voice-new');
    await say('listar productos');
    expectPhase('executed', 'tras "listar productos" sin red');
    expect(
      find.text(name),
      findsOneWidget,
      reason: 'la consulta ve el registro pendiente',
    );
    print(
      'EVIDENCIA 5 · "listar productos" sin red → ${textOf('voice-result')} · incluye el pendiente "$name"',
    );

    // ---- 5. EXCEPCIONES reales, sin red ------------------------------------------------------
    Future<void> expectFailure(
      String how,
      String kind,
      String title,
      List<String> bodyHas,
    ) async {
      expectPhase('failed', how);
      expect(
        find.byKey(Key('voice-failure-$kind')),
        findsOneWidget,
        reason: '$how: ${phaseNow()}',
      );
      expect(textOf('voice-failure-title'), title);
      final body = textOf('voice-failure-body');
      for (final part in bodyHas) {
        expect(body, contains(part), reason: '$how: $kind');
      }
      print(
        'EVIDENCIA · EXCEPCIÓN $kind ($how) → título="${textOf('voice-failure-title')}" · texto="$body"',
      );
    }

    await tapKey('voice-new');
    await say('hola buenos dias');
    await expectFailure(
      'texto "hola buenos dias"',
      'accionInexistente',
      'Esa acción no existe',
      ['crear, consultar'],
    );

    await tapKey('voice-new');
    await say('crear camisa 20');
    await expectFailure(
      'texto "crear camisa 20"',
      'intencionAmbigua',
      'La intención es ambigua',
      ['Entendí: Acción: crear', 'Dudo entre: Pedido o Producto'],
    );

    await tapKey('voice-new');
    await say('crear producto camisa');
    await expectFailure(
      'texto "crear producto camisa"',
      'datosFaltantes',
      'Faltan datos',
      ['Nombre: camisa', 'Falta: Precio'],
    );
    print('MARK:SHOT_EXCEPTION');
    await tester.pump(const Duration(seconds: 3));

    await tapKey('voice-new');
    await tapKey(
      'voice-mic',
    ); // la voz necesita red: sin conexión ni intenta escuchar
    await expectFailure(
      'botón de voz sin red',
      'recursosInsuficientes',
      'Reconocimiento de voz no disponible',
      ['necesita conexión', 'campo de texto'],
    );

    expect(
      (await services.store.allOps()).length,
      1,
      reason: 'ninguna excepción encoló nada: solo existe la creación válida',
    );
    print(
      'EVIDENCIA · las 4 excepciones no tocaron los datos: sigue habiendo 1 sola operación en la cola',
    );

    // ---- 6. Vuelve la red: NADIE toca nada y lo pendiente se sincroniza ----------------------
    print('MARK:AIRPLANE_OFF');
    final deadline = DateTime.now().add(const Duration(seconds: 90));
    var synced = false;
    while (DateTime.now().isBefore(deadline)) {
      final ops = await services.store.allOps();
      if (ops.isNotEmpty && ops.every((o) => o.status == OpStatus.synced)) {
        synced = true;
        break;
      }
      await tester.pump(const Duration(milliseconds: 500));
    }
    expect(
      synced,
      isTrue,
      reason: 'la app no sincronizó sola al recuperar la conexión',
    );
    expect(await onServer(), 1, reason: 'llegó exactamente una vez');
    print(
      'EVIDENCIA · red recuperada: la operación pasó a synced SOLA, en el servidor: ${await onServer()} fila',
    );
    print('MARK:SHOT_SYNCED');
    await tester.pump(const Duration(seconds: 3));

    // ---- limpieza en el servidor real --------------------------------------------------------
    final list = await server.send('GET', 'producto');
    final id = RegExp('"id":(\\d+),"nombre":"$name"')
        .firstMatch(list.body)
        ?.group(1);
    if (id != null) await server.send('DELETE', 'producto/$id');
    print('MARK:DONE');
  }, timeout: const Timeout(Duration(minutes: 8)));
}
