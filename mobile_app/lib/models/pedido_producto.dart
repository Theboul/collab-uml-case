import 'entity.dart';

/// PedidoProducto: entidad intermedia de la relación `Pedido *..* Producto`.
///
/// Contrato asimétrico del backend generado (verificado contra el backend real):
/// - **Lectura** (GET): `pedido` y `producto` llegan como objeto, como id suelto (identidad de
///   Jackson) o `null`; aquí se reducen siempre a su id `Long`.
/// - **Escritura** (POST/PUT): la relación se envía con claves dedicadas en minúscula,
///   `pedidoid` y `productoid` (el controlador generado las resuelve con `findPedidoById`…).
///   Cualquier otra forma (`pedido: 1`, `pedido: {id: 1}`, `pedidoId`) se ignora en silencio.
///   Un id que no existe también se ignora en silencio: queda `null`.
class PedidoProducto implements Entity {
  const PedidoProducto({this.id, this.pedidoId, this.productoId});

  factory PedidoProducto.fromJson(Map<String, dynamic> json) => PedidoProducto(
    id: parseLong(json['id']),
    pedidoId: parseRefId(json['pedido']),
    productoId: parseRefId(json['producto']),
  );

  @override
  final int? id;
  final int? pedidoId;
  final int? productoId;

  /// Cuerpo de escritura: `{"pedidoid": n, "productoid": m}` (solo las relaciones con valor).
  @override
  Map<String, Object?> toJson() => {
    if (pedidoId != null) 'pedidoid': pedidoId,
    if (productoId != null) 'productoid': productoId,
  };
}
