import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/app.dart';

import '../support/fake_backend.dart';
import '../support/test_env.dart';

/// Flujo de UI de CU12 contra el backend simulado (misma forma de responder que el real).
void main() {
  late FakeBackend backend;

  late TestEnv env;

  /// La UI corre sobre la pila offline-first completa (almacén en memoria + backend simulado).
  Future<void> openApp(WidgetTester tester) async {
    backend = FakeBackend();
    backend.insert('producto', {'nombre': 'Camisa', 'precio': 19.9});
    backend.insert('pedido', {'fecha': '2026-09-01'});
    env = await TestEnv.memory(backend: backend);
    await tester.pumpWidget(GestionApp(services: env.services));
    await tester.pumpAndSettle();
  }

  Future<void> goToProducto(WidgetTester tester, String op) async {
    await tester.tap(find.byKey(const Key('module-producto')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(Key('op-$op')));
    await tester.pumpAndSettle();
  }

  testWidgets('inicio: carga el listado de cada entidad desde el backend', (
    tester,
  ) async {
    await openApp(tester);

    expect(find.text('Productos'), findsOneWidget);
    expect(
      find.text('1 registro(s)'),
      findsNWidgets(2),
    ); // 1 producto y 1 pedido
    expect(find.text('0 registro(s)'), findsOneWidget); // pedido-producto
    expect(
      backend.log,
      containsAll([
        'GET /api/producto',
        'GET /api/pedido',
        'GET /api/pedidoproducto',
      ]),
    );
  });

  testWidgets(
    'inicio sin conexión: no se rompe, usa los datos locales y avisa que no hay conexión',
    (tester) async {
      backend = FakeBackend()..offline = true;
      env = await TestEnv.memory(backend: backend);
      await tester.pumpWidget(GestionApp(services: env.services));
      await tester.pumpAndSettle();

      // El monitor se entera del corte cuando la primera petición falla.
      expect(find.byKey(const Key('banner-offline')), findsOneWidget);
      expect(find.text('0 registro(s) · datos locales'), findsNWidgets(3));
      expect(find.textContaining('No se pudo conectar'), findsNothing);
    },
  );

  testWidgets(
    'crear con precio "abc": se rechaza en la app y NO se envía ninguna petición',
    (tester) async {
      await openApp(tester);
      await goToProducto(tester, 'crear');
      final before = backend.log.length;

      await tester.enterText(find.byKey(const Key('field-nombre')), 'Gorra');
      await tester.enterText(find.byKey(const Key('field-precio')), 'abc');
      await tester.tap(find.byKey(const Key('submit')));
      await tester.pumpAndSettle();

      expect(find.textContaining('debe ser un número'), findsOneWidget);
      expect(
        backend.log.length,
        before,
        reason: 'no debe salir ni una petición',
      );
      expect(backend.count('producto'), 1, reason: 'no se guardó nada');
      // el formulario conserva lo escrito
      expect(find.widgetWithText(TextFormField, 'Gorra'), findsOneWidget);
      expect(find.widgetWithText(TextFormField, 'abc'), findsOneWidget);
    },
  );

  testWidgets('crear con campos vacíos: muestra los errores y no envía nada', (
    tester,
  ) async {
    await openApp(tester);
    await goToProducto(tester, 'crear');
    final before = backend.log.length;

    await tester.tap(find.byKey(const Key('submit')));
    await tester.pumpAndSettle();

    expect(find.textContaining('obligatorio'), findsNWidgets(2));
    expect(backend.log.length, before);
  });

  testWidgets(
    'crear con datos válidos: guarda, confirma al usuario y vuelve al menú',
    (tester) async {
      await openApp(tester);
      await goToProducto(tester, 'crear');

      await tester.enterText(find.byKey(const Key('field-nombre')), 'Gorra');
      await tester.enterText(find.byKey(const Key('field-precio')), '8,5');
      await tester.tap(find.byKey(const Key('submit')));
      await tester.pumpAndSettle();

      expect(find.textContaining('creado correctamente'), findsOneWidget);
      expect(backend.count('producto'), 2);
      expect(backend.tables['producto']![2]!['precio'], 8.5);
    },
  );

  testWidgets(
    'crear cuando el servidor falla: informa, conserva el formulario y no guarda',
    (tester) async {
      await openApp(tester);
      await goToProducto(tester, 'crear');
      await tester.enterText(find.byKey(const Key('field-nombre')), 'Gorra');
      await tester.enterText(find.byKey(const Key('field-precio')), '8.5');

      backend.failNextWith = 500;
      await tester.tap(find.byKey(const Key('submit')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('form-error')), findsOneWidget);
      expect(find.textContaining('error interno'), findsOneWidget);
      expect(find.widgetWithText(TextFormField, 'Gorra'), findsOneWidget);
      expect(backend.count('producto'), 1);

      // reintenta sin volver a escribir nada y ahora sí guarda
      await tester.tap(find.byKey(const Key('submit')));
      await tester.pumpAndSettle();
      expect(backend.count('producto'), 2);
    },
  );

  testWidgets(
    'consultar por ID inexistente: mensaje claro (no un error crudo del 500)',
    (tester) async {
      await openApp(tester);
      await goToProducto(tester, 'consultar');

      await tester.enterText(find.byKey(const Key('search-id')), '999');
      await tester.tap(find.byKey(const Key('search-by-id')));
      await tester.pumpAndSettle();

      expect(
        find.textContaining('No existe Producto con ID 999'),
        findsOneWidget,
      );
      expect(find.textContaining('500'), findsNothing);
    },
  );

  testWidgets(
    'buscar con un ID que no es número: se rechaza sin llamar al backend',
    (tester) async {
      await openApp(tester);
      await goToProducto(tester, 'consultar');
      final before = backend.log.length;

      await tester.enterText(find.byKey(const Key('search-id')), 'abc');
      await tester.tap(find.byKey(const Key('search-by-id')));
      await tester.pumpAndSettle();

      expect(find.textContaining('número entero'), findsOneWidget);
      expect(backend.log.length, before);
    },
  );

  testWidgets(
    'eliminar: pide confirmación, elimina y confirma; cancelar no borra',
    (tester) async {
      await openApp(tester);
      await goToProducto(tester, 'eliminar');

      await tester.tap(find.byKey(const Key('item-1')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('cancel-delete')));
      await tester.pumpAndSettle();
      expect(backend.count('producto'), 1, reason: 'cancelar no borra');

      await tester.tap(find.byKey(const Key('item-1')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-delete')));
      await tester.pumpAndSettle();

      expect(find.textContaining('eliminado correctamente'), findsOneWidget);
      expect(backend.count('producto'), 0);
    },
  );

  testWidgets(
    'eliminar algo que otro usuario ya borró: informa que no existe (no "éxito")',
    (tester) async {
      await openApp(tester);
      await goToProducto(tester, 'eliminar');

      backend.tables['producto']!
          .clear(); // otro usuario lo eliminó mientras tanto
      await tester.tap(find.byKey(const Key('item-1')));
      await tester.pumpAndSettle();

      expect(
        find.textContaining('No existe Producto con ID 1'),
        findsOneWidget,
      );
      expect(find.textContaining('eliminado correctamente'), findsNothing);
    },
  );

  testWidgets(
    'actualizar: el formulario viene prellenado con los datos reales y guarda el cambio',
    (tester) async {
      await openApp(tester);
      await goToProducto(tester, 'actualizar');

      await tester.tap(find.byKey(const Key('item-1')));
      await tester.pumpAndSettle();
      expect(find.widgetWithText(TextFormField, 'Camisa'), findsOneWidget);
      expect(find.widgetWithText(TextFormField, '19.9'), findsOneWidget);

      await tester.enterText(find.byKey(const Key('field-precio')), '25');
      await tester.tap(find.byKey(const Key('submit')));
      await tester.pumpAndSettle();

      expect(find.textContaining('actualizado correctamente'), findsOneWidget);
      expect(backend.tables['producto']![1]!['precio'], 25.0);
      expect(backend.log, contains('PUT /api/producto/1'));
    },
  );

  Future<void> chooseRelation(WidgetTester tester) async {
    await tester.tap(find.byKey(const Key('module-pedidoproducto')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('op-crear')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('field-pedido')));
    await tester.pumpAndSettle();
    await tester.tap(find.textContaining('Pedido #1').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('field-producto')));
    await tester.pumpAndSettle();
    await tester.tap(find.textContaining('Camisa').last);
    await tester.pumpAndSettle();
  }

  testWidgets(
    'crear una relación: se elige pedido y producto y queda guardada',
    (tester) async {
      await openApp(tester);
      await chooseRelation(tester);

      await tester.tap(find.byKey(const Key('submit')));
      await tester.pumpAndSettle();

      expect(find.textContaining('creado correctamente'), findsOneWidget);
      expect(backend.count('pedidoproducto'), 1);
      final saved = backend.tables['pedidoproducto']![1]!;
      expect((saved['pedido'] as Map)['id'], 1);
      expect((saved['producto'] as Map)['id'], 1);
    },
  );

  testWidgets(
    'crear una relación con un pedido que otro usuario borró: no queda una fila nula',
    (tester) async {
      await openApp(tester);
      await chooseRelation(tester);

      backend.tables['pedido']!
          .clear(); // el pedido elegido desaparece antes de guardar
      await tester.tap(find.byKey(const Key('submit')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('form-error')), findsOneWidget);
      // El motor lo detecta ANTES de enviar (no llega a crear ninguna fila).
      expect(find.textContaining('Pedido 1 ya no existe'), findsOneWidget);
      expect(
        backend.count('pedidoproducto'),
        0,
        reason: 'no se llegó a crear ninguna fila',
      );
    },
  );
}
