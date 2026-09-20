import '../models/entity.dart';
import '../models/pedido.dart';
import '../models/pedido_producto.dart';
import '../models/producto.dart';
import 'field_spec.dart';

/// Descripción de una entidad del dominio para la UI y el repositorio genéricos.
///
/// Refleja el modelo UML que CU10 convirtió en backend. Añadir una entidad del dominio = añadir
/// aquí un módulo (modelo + campos); las pantallas y el repositorio no cambian.
///
/// Es una clase **no genérica** a propósito: los módulos se manejan en una lista heterogénea y los
/// genéricos con funciones en posición contravariante fallan en tiempo de ejecución en Dart.
abstract class EntityModule {
  const EntityModule();

  /// Segmento de ruta REST: el backend expone `/api/{path}` (nombre de la clase en minúsculas).
  String get path;

  /// Nombre singular para mensajes ("Producto").
  String get label;

  String get labelPlural;

  /// Atributos editables (sin `id`), en el orden del formulario.
  List<FieldSpec> get fields;

  Entity fromJson(Map<String, dynamic> json);

  /// Construye la entidad a partir de valores **ya validados y tipados** (`String`/`int`/`double`).
  Entity fromValues(int? id, Map<String, Object?> values);

  /// Valores tipados por nombre de campo (para prellenar el formulario y comparar lo persistido).
  Map<String, Object?> valuesOf(Entity entity);

  String title(Entity entity);

  String subtitle(Entity entity);
}

class ProductoModule extends EntityModule {
  const ProductoModule();

  @override
  String get path => 'producto';
  @override
  String get label => 'Producto';
  @override
  String get labelPlural => 'Productos';

  @override
  List<FieldSpec> get fields => const [
    FieldSpec(name: 'nombre', label: 'Nombre', type: FieldType.text),
    FieldSpec(name: 'precio', label: 'Precio', type: FieldType.decimal),
  ];

  @override
  Entity fromJson(Map<String, dynamic> json) => Producto.fromJson(json);

  @override
  Entity fromValues(int? id, Map<String, Object?> values) => Producto(
    id: id,
    nombre: values['nombre'] as String?,
    precio: values['precio'] as double?,
  );

  @override
  Map<String, Object?> valuesOf(Entity entity) {
    final p = entity as Producto;
    return {'nombre': p.nombre, 'precio': p.precio};
  }

  @override
  String title(Entity entity) => (entity as Producto).nombre ?? '(sin nombre)';

  @override
  String subtitle(Entity entity) {
    final p = entity as Producto;
    return 'ID ${p.id} · precio ${p.precio ?? '—'}';
  }
}

class PedidoModule extends EntityModule {
  const PedidoModule();

  @override
  String get path => 'pedido';
  @override
  String get label => 'Pedido';
  @override
  String get labelPlural => 'Pedidos';

  @override
  List<FieldSpec> get fields => const [
    FieldSpec(name: 'fecha', label: 'Fecha', type: FieldType.text),
  ];

  @override
  Entity fromJson(Map<String, dynamic> json) => Pedido.fromJson(json);

  @override
  Entity fromValues(int? id, Map<String, Object?> values) =>
      Pedido(id: id, fecha: values['fecha'] as String?);

  @override
  Map<String, Object?> valuesOf(Entity entity) => {
    'fecha': (entity as Pedido).fecha,
  };

  @override
  String title(Entity entity) => 'Pedido #${entity.id}';

  @override
  String subtitle(Entity entity) => 'Fecha ${(entity as Pedido).fecha ?? '—'}';
}

class PedidoProductoModule extends EntityModule {
  const PedidoProductoModule();

  @override
  String get path => 'pedidoproducto';
  @override
  String get label => 'Pedido-Producto';
  @override
  String get labelPlural => 'Pedidos-Productos';

  @override
  List<FieldSpec> get fields => const [
    FieldSpec(
      name: 'pedido',
      label: 'Pedido',
      type: FieldType.reference,
      referenceTo: 'pedido',
    ),
    FieldSpec(
      name: 'producto',
      label: 'Producto',
      type: FieldType.reference,
      referenceTo: 'producto',
    ),
  ];

  @override
  Entity fromJson(Map<String, dynamic> json) => PedidoProducto.fromJson(json);

  @override
  Entity fromValues(int? id, Map<String, Object?> values) => PedidoProducto(
    id: id,
    pedidoId: values['pedido'] as int?,
    productoId: values['producto'] as int?,
  );

  @override
  Map<String, Object?> valuesOf(Entity entity) {
    final pp = entity as PedidoProducto;
    return {'pedido': pp.pedidoId, 'producto': pp.productoId};
  }

  @override
  String title(Entity entity) => 'Relación #${entity.id}';

  @override
  String subtitle(Entity entity) {
    final pp = entity as PedidoProducto;
    return 'Pedido ${pp.pedidoId ?? '—'} · Producto ${pp.productoId ?? '—'}';
  }
}

/// Módulos del dominio, en el orden en que se muestran en la pantalla de inicio.
const List<EntityModule> allModules = [
  PedidoModule(),
  ProductoModule(),
  PedidoProductoModule(),
];

/// Busca un módulo por su ruta REST (para resolver `FieldSpec.referenceTo`).
EntityModule moduleByPath(String path) =>
    allModules.firstWhere((m) => m.path == path);
