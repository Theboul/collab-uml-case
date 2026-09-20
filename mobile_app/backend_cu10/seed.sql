-- Datos semilla SOLO para el fixture H2 (los carga run-h2.cmd). Permiten ver/consultar relaciones
-- ya pobladas, porque el backend generado NO permite crear relaciones por su API (ver README).
INSERT INTO pedido (fecha) VALUES ('2026-09-01'), ('2026-09-15');
INSERT INTO producto (nombre, precio) VALUES ('Camisa', 19.9), ('Zapato', 40.0), ('Gorra', 8.5);
INSERT INTO pedido_producto (pedido_id, producto_id) VALUES (1, 1), (1, 2), (2, 3);
