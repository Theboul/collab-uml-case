// ignore_for_file: avoid_print
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/app.dart';
import 'package:gestion_movil/app_scope.dart';
import 'package:gestion_movil/data/api_client.dart';
import 'package:gestion_movil/domain/pending_op.dart';
import 'package:integration_test/integration_test.dart';

/// CU13 en un teléfono REAL, contra el backend real, con modo avión de verdad.
///
/// No se ejecuta a mano: lo orquesta `tool/device-offline-test.ps1`, que lee las marcas `MARK:*`
/// que imprime este test y activa/desactiva el modo avión del teléfono con `adb` justo entonces.
///
///     adb reverse tcp:9000 tcp:9000      # el backend del PC, por USB (independiente del modo avión)
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
    'modo avión a mitad de sesión: la operación queda pendiente en local y, al desactivarlo, sincroniza sola',
    (tester) async {
      final name = 'Avion-${DateTime.now().millisecondsSinceEpoch}';
      final server = ApiClient(); // "otro observador": mide lo que hay REALMENTE en el servidor

      Future<int> onServer() async {
        final response = await server.send('GET', 'producto');
        return RegExp('"nombre":"$name"').allMatches(response.body).length;
      }

      Future<void> waitFor(
        Future<bool> Function() condition, {
        required Duration timeout,
        required String reason,
      }) async {
        final deadline = DateTime.now().add(timeout);
        while (!await condition()) {
          if (DateTime.now().isAfter(deadline)) fail('Tiempo agotado: $reason');
          await tester.pump(const Duration(milliseconds: 250));
        }
      }

      Future<void> tapKey(String key) async {
        await tester.tap(find.byKey(Key(key)));
        await tester.pumpAndSettle(
          const Duration(milliseconds: 100),
          EnginePhase.sendSemanticsUpdate,
          const Duration(seconds: 30),
        );
      }

      // ---- 1. Sesión normal, con conexión -------------------------------------------------
      final services = await AppServices.bootstrap();
      await tester.pumpWidget(GestionApp(services: services));
      await waitFor(
        () async => services.monitor.isOnline,
        timeout: const Duration(seconds: 30),
        reason: 'la app no llegó a "en línea" al iniciar',
      );
      await tester.pumpAndSettle(
        const Duration(milliseconds: 100),
        EnginePhase.sendSemanticsUpdate,
        const Duration(seconds: 30),
      );
      expect(find.textContaining('registro(s)'), findsNWidgets(3));
      expect(find.byKey(const Key('banner-hidden')), findsOneWidget);
      print(
        'EVIDENCIA 1 · con conexión: monitor.isOnline=${services.monitor.isOnline}, sin banner',
      );

      // ---- 2. Modo avión A MITAD DE LA SESIÓN --------------------------------------------
      print('MARK:AIRPLANE_ON');
      await waitFor(
        () async => !services.monitor.isOnline,
        timeout: const Duration(seconds: 60),
        reason: 'la app no detectó el modo avión',
      );
      await tester.pumpAndSettle(
        const Duration(milliseconds: 100),
        EnginePhase.sendSemanticsUpdate,
        const Duration(seconds: 30),
      );
      expect(find.byKey(const Key('banner-offline')), findsOneWidget);
      print(
        'EVIDENCIA 2 · modo avión detectado: monitor.isOnline=${services.monitor.isOnline}, banner "Sin conexión" visible',
      );

      // ---- 3. Una operación SIN conexión, desde la UI -------------------------------------
      await tapKey('module-producto');
      await tapKey('op-crear');
      await tester.enterText(find.byKey(const Key('field-nombre')), name);
      await tester.enterText(find.byKey(const Key('field-precio')), '12,5');
      await tapKey('submit');
      expect(find.textContaining('pendiente de sincronizar'), findsOneWidget);

      final pending = (await services.store.allOps()).single;
      expect(pending.kind, OpKind.create);
      expect(
        pending.status,
        OpStatus.pending,
        reason: 'guardada en local, marcada pendiente',
      );
      expect(pending.values['nombre'], name);
      expect(
        await onServer(),
        0,
        reason: 'sin conexión NO llegó nada al servidor',
      );
      expect(find.textContaining('1 pendiente(s)'), findsWidgets);
      print(
        'EVIDENCIA 3 · operación offline guardada en SQLite del teléfono: '
        'op=${pending.opId} kind=${pending.kind.name} status=${pending.status.name} '
        'nombre=${pending.values['nombre']} · en el servidor: ${await onServer()} filas',
      );
      print('MARK:SHOT_OFFLINE');
      await tester.pump(
        const Duration(seconds: 3),
      ); // tiempo para la captura de pantalla

      // ---- 4. Se desactiva el modo avión: NADIE toca nada en la app ----------------------
      print('MARK:AIRPLANE_OFF');
      await waitFor(
        () async {
          final ops = await services.store.allOps();
          return ops.isNotEmpty &&
              ops.every((o) => o.status == OpStatus.synced);
        },
        timeout: const Duration(seconds: 90),
        reason: 'la app no sincronizó sola al recuperar la conexión',
      );
      await tester.pumpAndSettle(
        const Duration(milliseconds: 100),
        EnginePhase.sendSemanticsUpdate,
        const Duration(seconds: 30),
      );

      final synced = (await services.store.allOps()).single;
      expect(await onServer(), 1, reason: 'llegó exactamente una vez');
      expect(find.byKey(const Key('banner-hidden')), findsOneWidget);
      expect(services.monitor.isOnline, isTrue);
      print(
        'EVIDENCIA 4 · sincronizó SOLA: op status=${synced.status.name}, en el servidor: ${await onServer()} fila, '
        'monitor.isOnline=${services.monitor.isOnline}, sin banner',
      );
      print('MARK:SHOT_SYNCED');
      await tester.pump(const Duration(seconds: 3));

      // ---- limpieza: se borra lo creado en el servidor real ---------------------------
      final list = await server.send('GET', 'producto');
      final id = RegExp('"id":(\\d+),"nombre":"$name"')
          .firstMatch(list.body)
          ?.group(1);
      if (id != null) await server.send('DELETE', 'producto/$id');
      print('MARK:DONE');
    },
    timeout: const Timeout(Duration(minutes: 8)),
  );
}
