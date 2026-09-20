import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/app.dart';
import 'package:gestion_movil/domain/entity_module.dart';
import 'package:gestion_movil/domain/pending_op.dart';
import 'package:gestion_movil/models/producto.dart';

import '../support/fake_backend.dart';
import '../support/sync_helpers.dart';
import '../support/test_env.dart';

/// CU13 en la UI: banner de conexión, pendientes visibles, sincronización automática y decisiones
/// sobre lo rechazado.
void main() {
  late FakeBackend backend;
  late TestEnv env;

  Future<void> openApp(WidgetTester tester) async {
    backend = seededBackend();
    env = await TestEnv.memory(backend: backend);
    await primeCache(env, ['producto', 'pedido', 'pedidoproducto']);
    await tester.pumpWidget(GestionApp(services: env.services));
    await tester.pumpAndSettle();
  }

  Future<void> goOffline(WidgetTester tester) async {
    env.goOffline();
    await tester.pumpAndSettle();
  }

  Future<void> goOnline(WidgetTester tester) async {
    env.backend.offline = false;
    env.monitor.setOnline(true); // la sincronización arranca sola
    await tester.pumpAndSettle();
  }

  Future<void> openProducto(WidgetTester tester, String op) async {
    await tester.tap(find.byKey(const Key('module-producto')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(Key('op-$op')));
    await tester.pumpAndSettle();
  }

  testWidgets('con conexión y sin pendientes no hay banner', (tester) async {
    await openApp(tester);
    expect(find.byKey(const Key('banner-hidden')), findsOneWidget);
    expect(find.byKey(const Key('banner-offline')), findsNothing);
  });

  testWidgets(
    'sin conexión: aparece el banner y la app sigue mostrando los datos guardados',
    (tester) async {
      await openApp(tester);

      await goOffline(tester);

      expect(find.byKey(const Key('banner-offline')), findsOneWidget);
      expect(find.textContaining('Sin conexión'), findsWidgets);
      await tester.tap(find.byKey(const Key('refresh')));
      await tester.pumpAndSettle();
      expect(find.text('2 registro(s) · datos locales'), findsOneWidget);
    },
  );

  testWidgets(
    'crear sin conexión: se guarda local, se marca PENDIENTE y se ve en el listado',
    (tester) async {
      await openApp(tester);
      await goOffline(tester);
      await openProducto(tester, 'crear');

      await tester.enterText(find.byKey(const Key('field-nombre')), 'Gorra');
      await tester.enterText(find.byKey(const Key('field-precio')), '8.5');
      await tester.tap(find.byKey(const Key('submit')));
      await tester.pumpAndSettle();

      expect(find.textContaining('pendiente de sincronizar'), findsOneWidget);
      expect(backend.count('producto'), 2, reason: 'nada llegó al servidor');
      expect(find.textContaining('1 pendiente(s)'), findsWidgets);

      await tester.tap(find.byKey(const Key('op-consultar')));
      await tester.pumpAndSettle();
      expect(find.text('Gorra'), findsOneWidget);
      expect(
        find.text('Pendiente'),
        findsOneWidget,
        reason: 'chip de pendiente junto al registro',
      );
    },
  );

  testWidgets(
    'al volver la conexión se sincroniza SOLO y desaparecen los pendientes',
    (tester) async {
      await openApp(tester);
      await goOffline(tester);
      await env
          .gateway(const ProductoModule())
          .create(const Producto(nombre: 'Gorra', precio: 8.5));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('banner-offline')), findsOneWidget);

      await goOnline(tester);

      expect(backend.count('producto'), 3);
      expect(find.byKey(const Key('banner-offline')), findsNothing);
      expect(find.byKey(const Key('banner-hidden')), findsOneWidget);
      expect((await env.ops()).single.status, OpStatus.synced);
    },
  );

  testWidgets(
    'una operación rechazada se ve en Sincronización con su motivo, y se puede "Crear como nuevo"',
    (tester) async {
      await openApp(tester);
      await goOffline(tester);
      await env
          .gateway(const ProductoModule())
          .update(1, const Producto(nombre: 'Camisa Pro', precio: 25));
      backend.tables['producto']!.remove(1); // otro cliente lo borró
      await goOnline(tester);

      // El banner avisa que algo necesita atención y lleva a la pantalla de sincronización.
      expect(find.byKey(const Key('banner-pending')), findsOneWidget);
      expect(find.textContaining('requieren tu atención'), findsOneWidget);
      await tester.tap(find.byKey(const Key('banner-pending')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('status-rejected')), findsOneWidget);
      expect(find.textContaining('eliminado por otro usuario'), findsOneWidget);
      expect(find.byKey(const Key('act-create-as-new')), findsOneWidget);
      expect(find.byKey(const Key('act-discard')), findsOneWidget);
      expect(
        backend.tables['producto']!.containsKey(1),
        isFalse,
        reason: 'nunca se recrea sola',
      );

      await tester.tap(find.byKey(const Key('act-create-as-new')));
      await tester.pumpAndSettle();

      expect(
        backend.tables['producto']!.values.any(
          (r) => r['nombre'] == 'Camisa Pro',
        ),
        isTrue,
      );
      expect(find.byKey(const Key('status-synced')), findsOneWidget);
    },
  );

  testWidgets('descartar una operación rechazada la quita de la cola', (
    tester,
  ) async {
    await openApp(tester);
    await goOffline(tester);
    await env
        .gateway(const ProductoModule())
        .update(1, const Producto(nombre: 'X', precio: 1));
    backend.tables['producto']![1]!['precio'] = 30.0;
    await goOnline(tester);
    await tester.tap(find.byKey(const Key('banner-pending')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('act-apply-anyway')), findsOneWidget);
    await tester.tap(find.byKey(const Key('act-discard')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('sync-empty')), findsOneWidget);
    expect(
      backend.tables['producto']![1]!['precio'],
      30.0,
      reason: 'el servidor gana',
    );
  });

  testWidgets(
    'editar sin conexión un registro real muestra el cambio y su chip de pendiente',
    (tester) async {
      await openApp(tester);
      await goOffline(tester);
      await openProducto(tester, 'actualizar');

      await tester.tap(find.byKey(const Key('item-1')));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('field-precio')), '25');
      await tester.tap(find.byKey(const Key('submit')));
      await tester.pumpAndSettle();

      expect(find.textContaining('pendiente de sincronizar'), findsOneWidget);
      expect(find.byKey(const Key('pending-1')), findsOneWidget);
      expect(backend.tables['producto']![1]!['precio'], 19.9);
    },
  );
}
