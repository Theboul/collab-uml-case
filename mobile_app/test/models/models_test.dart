import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:gestion_movil/models/entity.dart';
import 'package:gestion_movil/models/pedido.dart';
import 'package:gestion_movil/models/pedido_producto.dart';
import 'package:gestion_movil/models/producto.dart';

/// Los fixtures son respuestas REALES capturadas del backend generado por CU10 (con datos semilla).
Object? fixture(String name) =>
    jsonDecode(File('test/fixtures/$name').readAsStringSync());

void main() {
  group('id explícito y tipado como el backend (Long → int)', () {
    test('Producto expone id como int y precio como double', () {
      final p = Producto.fromJson({
        'id': 1,
        'nombre': 'Camisa',
        'precio': 19.9,
      });
      expect(p.id, isA<int>());
      expect(p.id, 1);
      expect(p.precio, isA<double>());
    });

    test('precio entero en el JSON (40) se lee como double', () {
      expect(
        Producto.fromJson({'id': 2, 'nombre': 'Zapato', 'precio': 40}).precio,
        40.0,
      );
    });

    test('toJson nunca incluye el id: viaja en la ruta', () {
      expect(
        const Producto(
          id: 9,
          nombre: 'X',
          precio: 1,
        ).toJson().containsKey('id'),
        isFalse,
      );
      expect(
        const Pedido(id: 9, fecha: 'f').toJson().containsKey('id'),
        isFalse,
      );
      expect(
        const PedidoProducto(
          id: 9,
          pedidoId: 1,
          productoId: 2,
        ).toJson().containsKey('id'),
        isFalse,
      );
    });

    test(
      'parseLong acepta int, num entero y String numérico; rechaza el resto',
      () {
        expect(parseLong(5), 5);
        expect(parseLong(5.0), 5);
        expect(parseLong('7'), 7);
        expect(parseLong(5.5), isNull);
        expect(parseLong('x'), isNull);
        expect(parseLong(null), isNull);
      },
    );
  });

  group(
    'Producto y Pedido con datos nulos (el backend los acepta en silencio)',
    () {
      test('un Producto con nulos se lee sin fallar y conserva los nulos', () {
        final p = Producto.fromJson({'id': 4, 'nombre': null, 'precio': null});
        expect(p.nombre, isNull);
        expect(p.precio, isNull);
      });
    },
  );

  group(
    'PedidoProducto: relaciones con identidad de Jackson (respuesta real)',
    () {
      test('lista real: la primera aparición es un objeto y las repetidas son solo el id', () {
        final list = (fixture('pedidoproducto_list.json') as List)
            .cast<Map<String, dynamic>>();
        // El fixture contiene "pedido": {..} en el 1.º, "pedido": 1 (id suelto) en el 2.º.
        expect(list[0]['pedido'], isA<Map>());
        expect(list[1]['pedido'], isA<int>());

        final parsed = list.map(PedidoProducto.fromJson).toList();
        expect(parsed.map((e) => e.pedidoId), [1, 1, 2]);
        expect(parsed.map((e) => e.productoId), [1, 2, 3]);
        expect(parsed.map((e) => e.id), [1, 2, 3]);
      });

      test('registro suelto por id', () {
        final pp = PedidoProducto.fromJson(
          fixture('pedidoproducto_1.json') as Map<String, dynamic>,
        );
        expect((pp.id, pp.pedidoId, pp.productoId), (1, 1, 1));
      });

      test(
        'relaciones nulas (lo que el backend guarda al ignorar la relación)',
        () {
          final pp = PedidoProducto.fromJson({
            'id': 5,
            'pedido': null,
            'producto': null,
          });
          expect(pp.pedidoId, isNull);
          expect(pp.productoId, isNull);
        },
      );

      test('parseRefId acepta objeto, id suelto y null', () {
        expect(parseRefId({'id': 3, 'fecha': 'x'}), 3);
        expect(parseRefId(3), 3);
        expect(parseRefId(null), isNull);
      });

      test('toJson escribe la relación con las claves del contrato real: pedidoid / productoid', () {
        expect(const PedidoProducto(pedidoId: 1, productoId: 2).toJson(), {
          'pedidoid': 1,
          'productoid': 2,
        });
        expect(const PedidoProducto(pedidoId: 1).toJson(), {'pedidoid': 1});
      });
    },
  );

  group('listados reales de Pedido y Producto', () {
    test(
      'pedido_list se lee (los pedidoproducto anidados no rompen el parseo)',
      () {
        final list = (fixture('pedido_list.json') as List)
            .cast<Map<String, dynamic>>();
        final pedidos = list.map(Pedido.fromJson).toList();
        expect(pedidos.map((p) => p.fecha), ['2026-09-01', '2026-09-15']);
        expect(pedidos.every((p) => p.id is int), isTrue);
      },
    );

    test('producto_list se lee con precios double', () {
      final list = (fixture('producto_list.json') as List)
          .cast<Map<String, dynamic>>();
      final productos = list.map(Producto.fromJson).toList();
      expect(productos.map((p) => p.nombre), ['Camisa', 'Zapato', 'Gorra']);
      expect(productos.map((p) => p.precio), [19.9, 40.0, 8.5]);
    });
  });
}
