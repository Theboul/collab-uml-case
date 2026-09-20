# Decisiones y hallazgos — mobile_app (CU12 + CU13)

Fecha de inicio: 2026-09-19. Este proyecto es **independiente de SchemaCraft** (ver `CLAUDE.md`): las
decisiones de CU13 (offline/sincronizacion) se registran aqui, no en un ADR del CASE web.

## 1. Base: proyecto Flutter nuevo (no el scaffold legacy)

Diagnostico del boton "Exportar Flutter" (`/api/generar_flutter/`, `mobile_app_reference/`), medido con el
generador real y el backend real de CU10 (dominio Pedido / Producto / PedidoProducto):

| Hallazgo | Evidencia |
|---|---|
| El endpoint responde **500** en Windows | `print("✅ ...")` en `flutter_scaffolding.py:165` revienta con la consola cp1252 (`'charmap' codec can't encode '✅'`); con `PYTHONUTF8=1` devuelve el zip |
| update/delete rotos si el modelo no declara `id` | usa el primer atributo como id: `PUT/DELETE /api/producto/Camisa` -> **400**; el modelo Dart no tiene `id` |
| Con `id` declarado lo tipa `String` (en Spring es `Long`) | `lib/models/producto.dart` generado |
| Validacion solo "campo requerido" | `precio` acepta cualquier texto y lo vuelve `0.0` |
| Nada de CU13 | sin storage local, sin conectividad, sin timeouts, sin tests, sin `android/` |

Decision: proyecto nuevo; el scaffold queda solo como referencia de convenciones.

## 2. Contrato real del backend generado por CU10

Todo verificado con peticiones reales (`backend_cu10/`, H2) y fijado en `test_backend/`:

| Comportamiento | Resultado real | Como lo trata la app |
|---|---|---|
| `POST {"precio":"abc"}` | 200, guarda `precio: null` | la app valida el tipo **antes** de enviar |
| `POST {}` | 200, crea fila con todo `null` | todos los campos son obligatorios en el formulario |
| `GET`/`PUT` de id inexistente | **500** (no 404) | se comprueba en el listado: si el id falta -> `NotFoundFailure`; si existe -> `ServerFailure` |
| `DELETE` de id inexistente | **200** | se consulta antes; si no existe -> `NotFoundFailure` y no se envia el DELETE |
| `DELETE` que responde 200 pero no borra | posible | se verifica despues; si sigue -> `InconsistentResultFailure` |
| JSON malformado | 400 | `RejectedFailure` |
| Relaciones: escritura | claves `pedidoid` / `productoid` | `PedidoProducto.toJson` |
| Relaciones: lectura | `pedido`/`producto` como objeto **o** id suelto (identidad de Jackson) o `null` | `parseRefId` |
| Relacion con clave distinta (`pedido:1`, `pedido:{id:1}`, `pedidoId`) o id inexistente | 200 y relacion `null` (se ignora en silencio) | tras crear/actualizar se compara lo guardado con lo enviado; si difiere -> `InconsistentResultFailure` y se descarta la fila a medias |

Correccion de un diagnostico previo: se afirmo que el backend "no permite crear relaciones". Era falso: se
probaron claves equivocadas. La coleccion Postman de CU11 (`Create PedidoProducto` con
`{"pedidoid":1,"productoid":1}`) persiste la relacion; no hay bug en `back_generator_uml`. La confusion vino del
contrato asimetrico escritura (`pedidoid`) / lectura (`pedido`).

## 3. Decisiones de CU12

- **Id explicito y tipado como el backend**: `int? id` (`Long`), nunca el primer atributo; viaja solo en la ruta.
- **Validacion por tipo real del atributo** (`FieldValidator`): texto (obligatorio, <= 255), entero `Long`
  (sin decimales, rango int64), decimal `Double` (punto o coma, finito, sin notacion cientifica), referencia (id > 0).
  `fecha` es `String` en el modelo UML y se trata como texto libre (el modelo no declara un formato).
- **Todos los campos obligatorios** al escribir: el modelo UML no declara nulabilidad y el backend acepta `null` en silencio.
- **El repositorio no se fia del codigo HTTP**: verifica el resultado (ver tabla del punto 2).
- **Un error nunca altera datos validos**: la validacion falla antes de enviar; un fallo del servidor deja el
  formulario intacto y no se reescribe el estado local; la fila a medias se descarta.
- **Metadatos del modelo a mano** (`EntityModule`): refleja el modelo UML de CU10; anadir una entidad es anadir un modulo.

## 4. CU13: offline y sincronizacion

### 4.1 Politica de conflictos (aprobada 2026-09-19): "el servidor gana"

El backend no tiene version ni timestamp (verificado): la deteccion es del cliente, con una **instantanea
base** (lo que la app sabia del servidor al crear la operacion) comparada con el estado real al sincronizar.
No es atomica (entre la comprobacion y el PUT/DELETE otro cliente puede escribir): sin `If-Match`/version en el
generador no se puede cerrar; queda documentado como limitacion.

| Caso | Resolucion | Estado / acciones |
|---|---|---|
| Update de un registro que otro cliente borro | no se envia el PUT; se quita de la cache; **nunca se recrea solo** | Rechazada (`deletedRemotely`). *Crear como nuevo* (opcional) o *Descartar* |
| Create de una relacion con un id que ya no existe | se comprueba la existencia **antes** del POST (el backend lo ignoraria con 200 y `null`) | Rechazada (`parentMissing`), sin fila basura |
| Delete de algo que otro modifico | **bloqueado**; se muestran los valores actuales | Rechazada (`modifiedRemotely`). *Eliminar igualmente* o *Descartar* |
| Delete de algo ya borrado | la intencion se cumplio | Sincronizada (`alreadyApplied`), no rechazada |
| Update de algo que otro modifico | servidor gana | Rechazada (`modifiedRemotely`). *Aplicar igualmente* o *Descartar* |
| Update cuyo resultado el servidor ya tiene | no es conflicto | Sincronizada (`alreadyApplied`) |
| Padre creado offline rechazado | sus dependientes se rechazan en cascada | Rechazada (`parentRejected`) |
| 400 del servidor | dato rechazado (definitivo) | Rechazada (`serverRejected`) |
| 5xx del servidor en update/delete | transitorio: 3 reintentos automaticos, luego manual | Fallida (`transient`). *Reintentar* |

Nada se pierde en silencio: lo rechazado conserva sus datos, el motivo y las acciones; solo *Descartar* los borra.
Las operaciones sobre registros creados offline se **fusionan** en su `create` (o lo descartan) y usan ids
temporales negativos que se remapean al id real.

### 4.2 Deduplicacion de creates (respuesta perdida)

`POST` no es idempotente (dos iguales = dos filas) y el backend no acepta clave de idempotencia. Se eligio la
**busqueda antes de reintentar**, endurecida con dos piezas de la idempotencia propia del cliente:

1. Cada operacion tiene un **UUID propio** y un estado persistido en SQLite: `sending` se guarda **antes** del POST.
2. Justo antes del envio se guarda la **foto de ids** que el servidor ya tenia (`preSendIds`).
3. Una operacion `uncertain` (timeout, corte, 5xx, o la app murio a mitad) **nunca se reenvia a ciegas**: se busca en
   el servidor un registro con los mismos datos exactos, cuyo id no estuviera en la foto previa ni reclamado por otra
   operacion. 0 candidatos -> reenviar; 1 -> adoptarlo (`alreadyCreated`); varios -> `needsReview` (lo decide el usuario).

Por que no solo UUID: un UUID que el backend nunca ve no puede resolver el caso ambiguo (la app no sabe si el POST
llego). Limitacion honesta: sigue siendo una heuristica por valores; solo es exacta con candidato unico.
`PUT` y `DELETE` son idempotentes y se reintentan directo (un update ya aplicado no se toma por conflicto).

### 4.3 Conectividad

"En linea" = interfaz de red (`connectivity_plus`) **y** el backend responde (sonda `GET /api/producto`). Una peticion
real que falla por red pasa la app a "sin conexion" de inmediato. Al volver, `SyncController` envia la cola **solo**.
Con `adb reverse` el tunel USB sigue vivo en modo avion, pero `connectivity_plus` informa `none` y la app se comporta
como sin conexion (es lo que se prueba).

### 4.4 Hallazgos durante la implementacion

- **Carrera en `SyncController.syncNow()`** (encontrada con el backend real): devolvia la pasada en curso aunque esta
  hubiera leido la cola antes de que llegara la operacion nueva, y esa operacion quedaba sin enviar. Ahora una peticion
  durante una pasada provoca otra al terminar (salvo que la pasada se haya cortado por falta de red). Test de regresion.
- `flutter test` corre los archivos en paralelo: los tests de integracion reales van con `--concurrency=1` (comparten backend).

## 5. Pruebas

| Suite | Que cubre | Comando |
|---|---|---|
| `test/` | dominio, modelos, repositorios, almacenamiento (SQLite real), sincronizacion, dedup, UI (widgets) | `flutter test` |
| `test_backend/` | CU12 + CU13 contra el Spring REAL (incl. respuesta perdida real) | `tool\run-integration.cmd` |
| `integration_test/cu13_offline_test.dart` | telefono real, modo avion real, backend real | `tool\device-offline-test.ps1` |
