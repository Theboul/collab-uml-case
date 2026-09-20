import 'entity.dart';

/// Pedido(id: Long, fecha: String).
///
/// `fecha` es `String` en el modelo UML, así que la app la trata como texto libre (sin validar un
/// formato de fecha que el modelo no declara).
class Pedido implements Entity {
  const Pedido({this.id, this.fecha});

  factory Pedido.fromJson(Map<String, dynamic> json) =>
      Pedido(id: parseLong(json['id']), fecha: json['fecha'] as String?);

  @override
  final int? id;
  final String? fecha;

  @override
  Map<String, Object?> toJson() => {'fecha': fecha};
}
