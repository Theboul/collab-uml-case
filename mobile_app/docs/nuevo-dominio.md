# Smoke-test empírico: dominio nuevo generado en el momento (2026-09-21/22)

Objetivo: convertir en certeza empírica la lectura de código que concluyó "agregar una entidad =
escribir `EntityModule`+`FieldSpec`, sin tocar las 5 pantallas ni el parser de voz", y medir cuánto
tiempo real toma — el dato clave para decidir si es viable hacerlo en vivo el día del examen.
Presupuesto: 75 min. Tiempo real usado: **~42 min**.

## Resultado: CONFIRMADO, con 3 matices reales (no maquillados)

La hipótesis se sostiene: **crear una entidad nueva (Proveedor, Insumo) no exigió tocar
`record_form_screen.dart`, `record_list_screen.dart`, `record_detail_screen.dart`,
`entity_menu_screen.dart` ni `voice_command_parser.dart`.** Confirmado end-to-end contra un backend
Spring real, generado por CU10 en el momento, en el teléfono real (CRUD, offline/CU13, voz/texto).

Los 3 matices, cada uno real y medido, no una estimación:

1. **Un campo de tipo nunca visto (`Boolean`) sí exige un cambio — genérico, no de la entidad.**
   `FieldType` no tenía variante `boolean`. Se agregó (`field_spec.dart`), con su validación
   (`validators.dart`) y una corrección de una línea en `record_form_screen.dart` (el teclado
   numérico no tiene sentido para "sí"/"no"). Es una adición **por tipo**, no por entidad: cualquier
   entidad futura con un campo booleano ya funciona sin tocar nada más. Este cambio **se conservó**
   (ver sección "Qué queda en el repo").
2. **El asistente de voz excluye por completo cualquier entidad con un campo `reference`** — no solo
   las relaciones puras como `PedidoProducto`. Insumo (que tiene tres campos normales y una
   referencia a Proveedor) quedó **totalmente fuera de voz** ("listar insumos" → intención ambigua,
   Insumo ni aparece en las opciones), aunque el CRUD manual sí lo maneja sin problema. Es la regla
   estructural ya documentada (`voice_command_parser.dart`, `voiceModules`), confirmada en la
   práctica: no es "PedidoProducto queda afuera", es "cualquier entidad con *algún* campo de
   referencia queda afuera de voz".
3. **Agregar una entidad a `allModules` rompió 23 tests de la suite existente** — no la app en
   producción (ya verificada real en el dispositivo), sino la **suite de tests**, por dos causas
   puntuales:
   - `test/support/fake_backend.dart`: el constructor inicializa una lista fija de tablas
     (`producto`, `pedido`, `pedidoproducto`); cualquier test que use `HomeScreen` (que itera
     `allModules`) explota con un `null check` sobre la tabla de la entidad nueva.
   - `test/domain/voice/voice_command_parser_test.dart` (línea ~527) tenía
     `expect(voiceModules.map((m) => m.path), ['pedido', 'producto'])` — una lista cerrada y exacta.
   
   Mantener entidades de ejemplo en el repo de forma permanente exigiría generalizar esos dos
   fixtures (trabajo real, aparte, no hecho en esta prueba de factibilidad). Por eso se retiraron
   Proveedor/Insumo del código (ver decisión abajo) — al hacerlo, la suite volvió sola a 312/312.

## Paso 1-2: modelar y generar con CU10 (real, sin tocar el generador)

Se construyó el modelo por la **API real de `backend_case`** (los mismos comandos que usa el editor
web — `CREATE_CLASS`, `ADD_ATTRIBUTE`, `ADD_ASSOCIATION`), no a mano ni con un archivo JSON armado
aparte:

- **Proveedor**: `nombre` (String).
- **Insumo**: `nombre` (String), `stock` (Integer), `activo` (Boolean), relación `*..1` hacia
  Proveedor (`Insumo` tiene el `@ManyToOne`, multiplicidad fuente `*`, destino `1`).

`POST /api/v2/canvases/{id}/generation/spring` generó el backend real (200, 10.761 bytes) contra
`back_generator_uml` corriendo local en el puerto 7000 (el `GENERATOR_SPRING_URL` por defecto, un
servidor remoto de producción, no respondió — DNS no resuelve desde esta red; se corrió local sin
tocar una línea del generador).

**Confirmado con `curl` directo (antes de tocar la app móvil), contra H2 en memoria, puerto 9500:**

| Comprobación | Resultado |
|---|---|
| `POST /api/proveedor {"nombre":"Acme SA"}` | `{"id":1,"nombre":"Acme SA","insumo":[]}` |
| `POST /api/insumo {"nombre":"Tornillos","stock":250,"activo":true,"proveedorid":1}` | `{"id":1,...,"activo":true,"proveedor":{"id":1,"nombre":"Acme SA","insumo":[1]}}` |
| `PUT /api/insumo/1 {"stock":300}` | parcial, igual que el dominio anterior |
| `DELETE /api/insumo/1` | 200 |

**Contrato confirmado, no refutado:** la relación se escribe con clave plana **`proveedorid`** (sin
guion bajo) — igual que `pedidoid`/`productoid` — pese a que la columna SQL generada sí lleva guion
bajo (`@JoinColumn(name = "proveedor_id")`, un detalle interno de JPA que no afecta al contrato
REST). `Boolean` mapea correctamente a `Boolean` de Java (`TypeMapper.java`, ya soportaba
`bool`/`boolean` antes de esta prueba). Ningún ajuste al generador fue necesario.

## Paso 3: adaptar la app móvil — **tiempo real medido: 5 min 02 s**

Desde escribir el primer `EntityModule` hasta la APK instalada en el teléfono real (23:32:57 →
23:38:00, teléfono TECNO BG6m por USB):

1. `lib/models/proveedor.dart`, `lib/models/insumo.dart` (siguiendo el patrón de `pedido.dart`).
2. `ProveedorModule`/`InsumoModule` en `entity_module.dart`, agregadas a `allModules`.
3. (Incluido en el tiempo) agregar `FieldType.boolean` — ver matiz 1 arriba.
4. `adb reverse tcp:9500 tcp:9500` + `flutter build apk --debug
   --dart-define=API_BASE_URL=http://127.0.0.1:9500/api` (28,5 s) + `adb install -r` — sin tocar
   ninguna pantalla ni el parser.

**Conclusión sobre viabilidad:** 5 minutos es holgadamente viable para hacerlo en vivo el día del
examen, incluso sumando el tiempo de modelar en el editor web y generar con CU10 (Paso 1-2, que acá
se hizo vía API directa en ~3 minutos; a mano en el editor web tomaría más, pero sigue siendo del
orden de minutos, no de una preparación previa obligatoria).

## Paso 4: verificación real en el dispositivo (sin mocks)

Todo en el teléfono real, contra el backend Spring real en el puerto 9500 (capturas en
`mobile_app/build/smoke-*.png`):

- **CRUD manual completo**: crear Proveedor "Acme SA" (por `curl`, como dato base) → crear Insumo
  "Tornillos" (nombre, stock, `activo` como texto "sí"/"no", Proveedor por dropdown) →
  `Insumo 2 creado correctamente.` → editar (stock 250→300, confirmado por `curl`) → eliminar
  (confirmado `[]` en el servidor). Las 4 pantallas, sin cambios, funcionaron con los 4 tipos de
  campo (texto, entero, booleano, referencia).
- **Offline real (modo avión de verdad, no `adb reverse` simulando)**: banner "Sin conexión ·
  trabajando con los datos guardados" apareció solo para Proveedor/Insumo igual que para
  Pedido/Producto; se creó un Insumo sin red → "guardado en este dispositivo, pendiente de
  sincronizar" + badge "1"; al desactivar el modo avión, sincronizó sola (confirmado por `curl`:
  `{"id":3,"nombre":"OffTest","stock":5,"activo":false,"proveedor":{"id":1,...}}`).
- **Voz/texto**: `"crear proveedor Beta"` → `Crear Proveedor · Nombre: Beta` → confirmado →
  `{"id":2,"nombre":"Beta",...}` en el servidor real. `"listar proveedores"` →
  `Proveedores: 2 registro(s). Acme SA ID 1. Beta ID 2.` Ambos sin tocar
  `voice_command_parser.dart`. `"listar insumos"` confirmó el matiz 2 (Insumo excluido de voz por
  tener un campo `reference`).
- **Suite completa**: ver matiz 3. Con Proveedor/Insumo en el árbol: 289 de 312 pasan (23 fallas,
  ninguna en la app real, todas en dos fixtures de test con supuestos cerrados). Tras retirarlos:
  **312 de 312**, `flutter analyze` limpio.

## Qué queda en el repo (decisión)

**Proveedor e Insumo se retiraron** (`lib/models/proveedor.dart`, `lib/models/insumo.dart`
eliminados; `ProveedorModule`/`InsumoModule` y sus entradas en `allModules` removidas de
`entity_module.dart`) — mantenerlos como ejemplo permanente exige generalizar
`test/support/fake_backend.dart` (tablas dinámicas) y la aserción cerrada de
`voice_command_parser_test.dart`, trabajo real aparte que no entra en el alcance de esta prueba de
factibilidad.

**Se conserva** el soporte genérico de `FieldType.boolean` (`field_spec.dart`, `validators.dart`,
`record_form_screen.dart`): es una capacidad de tipo, no de entidad, ya probada end-to-end, y deja
la app lista para la próxima entidad que use un campo booleano sin repetir este hallazgo.

## Receta para el día del examen

1. Modelar la entidad en el editor UML web (o, si hace falta velocidad, por la API de
   `backend_case` como se hizo acá).
2. Generar el backend con el botón/endpoint de CU10; correrlo con H2 en memoria en un puerto propio
   (no 9000, que puede estar en uso) — mismo patrón que `mobile_app/backend_cu10/run-h2.cmd`, pero
   apuntando al `pom.xml` nuevo.
3. `lib/models/<entidad>.dart` (copiar el patrón de `pedido.dart`/`producto.dart`) +
   `<Entidad>Module extends EntityModule` en `entity_module.dart` + agregarla a `allModules`.
   Si el modelo tiene un tipo de campo nunca usado antes (fuera de texto/entero/decimal/referencia/
   booleano), **eso sí puede exigir tocar `field_spec.dart`/`validators.dart`** — es la única
   categoría de cambio real que rompe la hipótesis "cero pantallas tocadas", y es genérica por tipo,
   nunca por entidad.
4. `adb reverse tcp:<puerto> tcp:<puerto>` + `flutter build apk --debug
   --dart-define=API_BASE_URL=http://127.0.0.1:<puerto>/api` + `adb install -r`. ~5 minutos.
5. Si la entidad tiene un campo `reference`, avisar que **no** será controlable por voz (limitación
   de diseño conocida, no un bug) — el camino de texto/CRUD manual sigue intacto.
6. Antes de dar la demo por cerrada, correr `flutter test`: si agregaste la entidad como ejemplo
   permanente (no solo para la demo), vas a necesitar generalizar `fake_backend.dart` y la aserción
   de `voice_command_parser_test.dart` — si es solo para la demo, alcanza con no commitear el
   cambio a `allModules` en la suite de tests, o revertirlo después como se hizo acá.
