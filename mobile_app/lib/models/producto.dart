import 'entity.dart';

/// Producto(id: Long, nombre: String, precio: Double).
///
/// Los atributos son nulables porque así los puede devolver el backend (acepta `null` en silencio);
/// el formulario los exige siempre al escribir.
class Producto implements Entity {
  const Producto({this.id, this.nombre, this.precio});

  factory Producto.fromJson(Map<String, dynamic> json) => Producto(
    id: parseLong(json['id']),
    nombre: json['nombre'] as String?,
    precio: (json['precio'] as num?)?.toDouble(),
  );

  @override
  final int? id;
  final String? nombre;
  final double? precio;

  @override
  Map<String, Object?> toJson() => {'nombre': nombre, 'precio': precio};
}
