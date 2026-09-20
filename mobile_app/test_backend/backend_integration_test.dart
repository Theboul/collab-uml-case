import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/data/api_client.dart';
import 'package:gestion_movil/data/entity_repository.dart';
import 'package:gestion_movil/data/failures.dart';
import 'package:gestion_movil/domain/entity_module.dart';
import 'package:gestion_movil/domain/field_spec.dart';
import 'package:gestion_movil/domain/validators.dart';
import 'package:gestion_movil/models/pedido.dart';
import 'package:gestion_movil/models/pedido_producto.dart';
import 'package:gestion_movil/models/producto.dart';

/// Pruebas de integración REALES: sin mocks, contra el backend Spring generado por CU10.
///
/// Requieren el backend levantado en `API_BASE_URL` (por defecto http://127.0.0.1:9000/api):
///
///     mobile_app\backend_cu10\run-h2.cmd          (H2 en memoria, con datos semilla)
///     flutter test test_backend
///
/// Cada test limpia lo que crea. Los tests marcados "caracterización" fijan cómo responde HOY el
/// backend (es la razón de que la app valide por su cuenta); si el backend se corrige, fallarán y
/// habrá que revisar las suposiciones de la app.
void main() {
  late ApiClient api;
  late EntityRepository productos;
  late EntityRepository pedidos;
  late EntityRepository relaciones;
  final created = <(String, int)>[]; // (ruta, id) a limpiar

  setUpAll(() async {
    // flutter_test bloquea el HTTP real por defecto; estas pruebas necesitan la red de verdad.
    HttpOverrides.global = null;
    api = ApiClient();
    productos = EntityRepository(const ProductoModule(), api);
    pedidos = EntityRepository(const PedidoModule(), api);
    relaciones = EntityRepository(const PedidoProductoModule(), api);
    try {
      await productos.list();
    } on NetworkFailure catch (e) {
      fail(
        'El backend no responde en ${api.baseUrl} (${e.detail}). '
        'Levántalo con mobile_app\\backend_cu10\\run-h2.cmd y repite.',
      );
    }
  });

  tearDown(() async {
    for (final (path, id) in created) {
      await api.send('DELETE', '$path/$id');
    }
    created.clear();
  });

  String unique(String base) =>
      '$base-${DateTime.now().microsecondsSinceEpoch}';

  group('consultar (datos reales del backend)', () {
    test('lista de cada entidad: se lee sin errores', () async {
      expect(await pedidos.list(), isA<List<Object>>());
      expect(await productos.list(), isA<List<Object>>());
      expect(await relaciones.list(), isA<List<Object>>());
    });

    test('las relaciones sembradas se leen con ids Long, incluso las serializadas solo como id', () async {
      final items = (await relaciones.list()).cast<PedidoProducto>();
      final linked = items
          .where((r) => r.pedidoId != null && r.productoId != null)
          .toList();
      if (linked.isEmpty) {
        markTestSkipped('el backend no tiene datos semilla (usa run-h2.cmd)');
        return;
      }
      for (final r in linked) {
        expect(r.id, isA<int>());
        expect(r.pedidoId, isA<int>());
        expect(r.productoId, isA<int>());
      }
    });

    test('getById devuelve el mismo registro que el listado', () async {
      final producto = (await productos.list()).cast<Producto>().first;
      final again = await productos.getById(producto.id!) as Producto;
      expect(
        (again.id, again.nombre, again.precio),
        (producto.id, producto.nombre, producto.precio),
      );
    });
  });

  group('ciclo completo de gestión de un Producto', () {
    test('crear → consultar → actualizar → eliminar → ya no existe', () async {
      final nombre = unique('Integracion');

      final creado = await productos.create(
        Producto(nombre: nombre, precio: 12.5),
      ) as Producto;
      created.add(('producto', creado.id!));
      expect(creado.id, isA<int>());
      expect((creado.nombre, creado.precio), (nombre, 12.5));

      final leido = await productos.getById(creado.id!) as Producto;
      expect(leido.nombre, nombre);

      final actualizado = await productos.update(
        creado.id!,
        Producto(id: creado.id, nombre: '$nombre-v2', precio: 99.99),
      ) as Producto;
      expect((actualizado.nombre, actualizado.precio), ('$nombre-v2', 99.99));
      expect(((await productos.getById(creado.id!)) as Producto).precio, 99.99);

      await productos.delete(creado.id!);
      await expectLater(
        productos.getById(creado.id!),
        throwsA(isA<NotFoundFailure>()),
      );
      expect((await productos.list()).any((p) => p.id == creado.id), isFalse);
    });

    test('ciclo de un Pedido (String) con acentos y símbolos', () async {
      final fecha = unique('2026-09-19 ñandú €');
      final creado = await pedidos.create(Pedido(fecha: fecha)) as Pedido;
      created.add(('pedido', creado.id!));
      expect((await pedidos.getById(creado.id!) as Pedido).fecha, fecha);
      await pedidos.delete(creado.id!);
    });
  });

  group('operación no disponible / datos inexistentes', () {
    const ghost = 987654321;

    test(
      'consultar un id inexistente: NotFoundFailure (el backend responde 500)',
      () async {
        // caracterización: el backend responde 500 y no 404
        expect((await api.send('GET', 'producto/$ghost')).status, 500);
        await expectLater(
          productos.getById(ghost),
          throwsA(isA<NotFoundFailure>()),
        );
      },
    );

    test(
      'actualizar un id inexistente: NotFoundFailure y no se crea nada',
      () async {
        final antes = (await productos.list()).length;
        await expectLater(
          productos.update(ghost, const Producto(nombre: 'x', precio: 1)),
          throwsA(isA<NotFoundFailure>()),
        );
        expect((await productos.list()).length, antes);
      },
    );

    test('eliminar un id inexistente: NotFoundFailure (el backend respondería 200)', () async {
      // caracterización: el backend "elimina con éxito" algo que no existe
      expect((await api.send('DELETE', 'producto/$ghost')).status, 200);
      await expectLater(
        productos.delete(ghost),
        throwsA(isA<NotFoundFailure>()),
      );
    });

    test('sin conexión: NetworkFailure rápido, sin colgarse', () async {
      final sinBackend = ApiClient(
        baseUrl: 'http://127.0.0.1:9/api',
        timeout: const Duration(seconds: 3),
      );
      await expectLater(
        EntityRepository(const ProductoModule(), sinBackend).list(),
        throwsA(isA<NetworkFailure>()),
      );
    });
  });

  group('validación: la app rechaza lo que el backend acepta', () {
    test('caracterización: el backend acepta {"precio":"abc"} con 200 y guarda null', () async {
      final r = await api.send(
        'POST',
        'producto',
        jsonBody: {'nombre': unique('Basura'), 'precio': 'abc'},
      );
      final id = RegExp(r'"id":(\d+)').firstMatch(r.body)!.group(1)!;
      created.add(('producto', int.parse(id)));

      expect(r.status, 200);
      expect(r.body, contains('"precio":null'));
    });

    test('caracterización: el backend acepta un cuerpo vacío {} y crea una fila nula', () async {
      final r = await api.send(
        'POST',
        'producto',
        jsonBody: <String, Object?>{},
      );
      created.add((
        'producto',
        int.parse(RegExp(r'"id":(\d+)').firstMatch(r.body)!.group(1)!),
      ));
      expect(r.status, 200);
      expect(r.body, contains('"nombre":null'));
    });

    test('la validación de la app corta esos casos ANTES de enviarlos', () {
      final precio = const ProductoModule().fields.firstWhere(
        (f) => f.name == 'precio',
      );
      expect(FieldValidator.validate(precio, 'abc'), isNotNull);
      expect(FieldValidator.validate(precio, ''), isNotNull);
      expect(precio.type, FieldType.decimal);
    });
  });

  group('relaciones (contrato pedidoid / productoid del backend generado)', () {
    test(
      'crear → leer → cambiar el producto → eliminar una relación',
      () async {
        final pedido = (await pedidos.list()).firstOrNull;
        final productosSembrados = await productos.list();
        if (pedido == null || productosSembrados.length < 2) {
          markTestSkipped('faltan pedido/productos sembrados (usa run-h2.cmd)');
          return;
        }
        final p1 = productosSembrados[0].id!;
        final p2 = productosSembrados[1].id!;

        final creada = await relaciones.create(
          PedidoProducto(pedidoId: pedido.id, productoId: p1),
        ) as PedidoProducto;
        created.add(('pedidoproducto', creada.id!));
        expect((creada.pedidoId, creada.productoId), (pedido.id, p1));

        final leida = await relaciones.getById(creada.id!) as PedidoProducto;
        expect((leida.pedidoId, leida.productoId), (pedido.id, p1));

        final cambiada = await relaciones.update(
          creada.id!,
          PedidoProducto(pedidoId: pedido.id, productoId: p2),
        ) as PedidoProducto;
        expect(cambiada.productoId, p2);

        await relaciones.delete(creada.id!);
        await expectLater(
          relaciones.getById(creada.id!),
          throwsA(isA<NotFoundFailure>()),
        );
      },
    );

    test('caracterización: las claves que NO son pedidoid/productoid se ignoran con 200 y null', () async {
      final r = await api.send(
        'POST',
        'pedidoproducto',
        jsonBody: {'pedido': 1, 'producto': 1},
      );
      created.add((
        'pedidoproducto',
        int.parse(RegExp(r'"id":(\d+)').firstMatch(r.body)!.group(1)!),
      ));
      expect(r.status, 200);
      expect(r.body, contains('"pedido":null'));
    });

    test('un id de relación inexistente: el backend lo ignora (200) → la app lo detecta y no deja basura', () async {
      final producto = (await productos.list()).firstOrNull;
      if (producto == null) {
        markTestSkipped('falta un producto sembrado');
        return;
      }
      final antes = (await relaciones.list()).length;

      final failure = await _failureOf(
        () => relaciones.create(
          PedidoProducto(pedidoId: 987654321, productoId: producto.id),
        ),
      );

      expect(failure, isA<InconsistentResultFailure>());
      expect(failure.userMessage, contains('no guardó: Pedido'));
      expect(failure.userMessage, contains('Se descartó'));
      expect(
        (await relaciones.list()).length,
        antes,
        reason: 'no queda ninguna fila a medias',
      );
    });
  });
}

Future<AppFailure> _failureOf(Future<Object?> Function() action) async {
  try {
    await action();
  } on AppFailure catch (failure) {
    return failure;
  }
  fail('se esperaba un AppFailure y la operación terminó bien');
}
