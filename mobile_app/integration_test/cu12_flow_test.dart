import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/app.dart';
import 'package:gestion_movil/app_scope.dart';
import 'package:integration_test/integration_test.dart';

/// CU12 de punta a punta en un dispositivo real, contra el backend real generado por CU10.
///
///     adb reverse tcp:9000 tcp:9000
///     flutter test integration_test/cu12_flow_test.dart -d <id-del-telefono>
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  Future<void> settle(WidgetTester tester) => tester.pumpAndSettle(
    const Duration(milliseconds: 100),
    EnginePhase.sendSemanticsUpdate,
    const Duration(seconds: 30),
  );

  Future<void> tapKey(WidgetTester tester, String key) async {
    await tester.tap(find.byKey(Key(key)));
    await settle(tester);
  }

  Future<void> searchById(WidgetTester tester, int id) async {
    await tester.enterText(find.byKey(const Key('search-id')), '$id');
    await tapKey(tester, 'search-by-id');
  }

  testWidgets(
    'crear → consultar → actualizar → eliminar, con validación y errores',
    (tester) async {
      final nombre = 'Telefono-${DateTime.now().millisecondsSinceEpoch}';

      final services = await AppServices.bootstrap();
      await tester.pumpWidget(GestionApp(services: services));
      await settle(tester);

      // Inicio: cada entidad cargó su listado desde el backend real.
      expect(find.textContaining('registro(s)'), findsNWidgets(3));

      // Producto → Crear, con un precio inválido: la app lo rechaza antes de enviar.
      await tapKey(tester, 'module-producto');
      await tapKey(tester, 'op-crear');
      await tester.enterText(find.byKey(const Key('field-nombre')), nombre);
      await tester.enterText(find.byKey(const Key('field-precio')), 'abc');
      await tapKey(tester, 'submit');
      expect(find.textContaining('debe ser un número'), findsOneWidget);

      // Corrige y crea de verdad.
      await tester.enterText(find.byKey(const Key('field-precio')), '12,5');
      await tapKey(tester, 'submit');
      final snack = find.textContaining('creado correctamente');
      expect(snack, findsOneWidget);
      final id = int.parse(
        RegExp(r'Producto (\d+)')
            .firstMatch((tester.widget<Text>(snack)).data!)!
            .group(1)!,
      );

      // Consultar por ID: dato fresco del backend.
      await tapKey(tester, 'op-consultar');
      await searchById(tester, id);
      expect(find.text(nombre), findsOneWidget);
      expect(find.text('12.5'), findsOneWidget);
      await tester.pageBack();
      await settle(tester);
      await tester.pageBack(); // vuelve al menú de operaciones
      await settle(tester);

      // Actualizar: cambia el precio.
      await tapKey(tester, 'op-actualizar');
      await searchById(tester, id);
      await tester.enterText(find.byKey(const Key('field-precio')), '99.99');
      await tapKey(tester, 'submit');
      expect(find.textContaining('actualizado correctamente'), findsOneWidget);
      await tester.pageBack();
      await settle(tester);

      // Eliminar (con confirmación).
      await tapKey(tester, 'op-eliminar');
      await searchById(tester, id);
      await tapKey(tester, 'confirm-delete');
      expect(find.textContaining('eliminado correctamente'), findsOneWidget);

      // Eliminarlo otra vez: el backend respondería 200, la app informa que no existe.
      await searchById(tester, id);
      expect(
        find.textContaining('No existe Producto con ID $id'),
        findsOneWidget,
      );
    },
  );
}
