# Decisiones y hallazgos — mobile_app (CU12 + CU13 + CU14)

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
| `test/` | dominio, modelos, repositorios, almacenamiento (SQLite real), sincronizacion, dedup, UI (widgets), CU14 (parser, ejecutor, asistente) | `flutter test` |
| `test_backend/` | CU12 + CU13 contra el Spring REAL (incl. respuesta perdida real) | `tool\run-integration.cmd` |
| `integration_test/cu13_offline_test.dart` | telefono real, modo avion real, backend real | `tool\device-offline-test.ps1` |
| `integration_test/cu14_voice_test.dart` | telefono real, modo avion real, asistente por TEXTO (crear, consultar, 4 excepciones sin red, sincroniza sola al volver la red) | `tool\device-voice-test.ps1 -Mode offline` |
| `integration_test/cu14_voice_online_test.dart` | telefono real, CON red, boton de voz real de punta a punta contra el backend real | `tool\device-voice-test.ps1 -Mode voice` |
| `integration_test/cu14_asr_probe_test.dart` | diagnostico de Fase 0 (no es parte de la app) | `tool\device-asr-probe.ps1` |

## 6. CU14: asistente por voz/texto (parser por reglas, sin LLM)

### 6.1 Fase 0: medicion real de ASR offline (2026-09-21)

Se evaluo un LLM on-device (llama.cpp/GGUF) como "componente inteligente local" y se descarto por
restricciones de hardware confirmadas en el dispositivo de pruebas (TECNO BG6m, Android 14, SDK 34):
ABI de 32 bits (`armeabi-v7a`/`armeabi`, sin `arm64-v8a`) y RAM insuficiente (1,8 GB totales, ~660 MB
libres con la app del sistema cargada). El spike y la dependencia `llm_llamacpp` se retiraron del
repo (commit `chore(mobile): retirar el spike de LLM on-device`); no se reescribe ese spike, queda
trazable en el historial.

Con el LLM descartado, se midio si al menos el **reconocimiento de voz** (ASR, sin modelo de
lenguaje) podia correr offline en espanol. Resultado medido, sin el plugin `speech_to_text` de por
medio (listener nativo directo contra `SpeechRecognizer`, para descartar que el plugin ocultara el
error):

| Comprobacion | Resultado |
|---|---|
| `SpeechRecognizer.isOnDeviceRecognitionAvailable` | **false** |
| Unico `RecognitionService` instalado | `com.google.android.tts` (Servicios de voz de Google) |
| En modo avion REAL (red verificada caida por DNS) con `EXTRA_PREFER_OFFLINE`, 7 variantes: `es-ES`, `es-US`, `es-MX`, `es-419`, `es-BO`, `es-AR`, `es` | **`ERROR_LANGUAGE_NOT_SUPPORTED`** en ~160 ms cada una |
| Misma prueba, `en-US` (control: espanol no es el problema, es "offline") | `ERROR_LANGUAGE_UNAVAILABLE` (tambien falla, distinto codigo) |
| CONTROL con red, sin `EXTRA_PREFER_OFFLINE` | el espanol funciona: transcribe frases reales del dominio ("crear producto camisa con precio 20") |
| Plugin `speech_to_text` con `onDevice: true` | la sesion muere en 0,4-1,4 s **sin error hacia Dart**, incluso con red (bug/limitacion del plugin: cae en silencio al reconocedor por defecto) |
| `SpeechToText.locales()` del plugin | nunca responde en este dispositivo (hay que envolverlo en un timeout) |

Conclusion: **no hay ASR offline en espanol disponible en este dispositivo.** Herramienta de
medicion: `AsrProbe.kt` + `integration_test/cu14_asr_probe_test.dart` +
`tool\device-asr-probe.ps1` (diagnostico, no es parte de la app; se conserva para repetir la
medicion en otro telefono).

### 6.2 Decision de diseno (aprobada): Opcion A

- **Voz** (`speech_to_text`, `onDevice: false`): **requiere red**. Antes de escuchar se comprueba la
  conectividad con el mismo `ConnectivityMonitor` de CU13 (sin duplicar la deteccion); sin red no se
  intenta escuchar, se muestra directamente la excepcion `recursosInsuficientes` ("el reconocimiento
  de voz necesita conexion en este dispositivo — usa el campo de texto").
- **Texto**: campo siempre disponible, alimenta el **mismo** `VoiceCommandParser` que la voz. Es el
  camino que garantiza la postcondicion de la ficha ("sin requerir obligatoriamente conexion a
  Internet") y el unico que se prueba en modo avion real.
- Principio de diseno mantenido: la voz/texto son una entrada mas al pipeline de CU12/13
  (`OfflineFirstRepository` via `VoiceCommandExecutor`); no hay validacion, ejecucion ni logica de
  negocio duplicada.

### 6.3 Alcance del vocabulario cerrado del parser

`VoiceCommandParser` (`lib/domain/voice/`) cubre, para **Producto** y **Pedido** (los `EntityModule`
sin campos de referencia — derivado de los modulos existentes, no de una lista aparte):

| Intent | Cubre | No cubre |
|---|---|---|
| `crear` | todos los campos de la entidad, en cualquier orden, por palabra clave o posicion | — |
| `consultar` | listar todos, o uno por id | — |
| `actualizar` | **un** campo de un registro existente por id | mas de un campo a la vez (es `intencionAmbigua`) |
| `eliminar` | por id | — |

Fuera de alcance en esta fase: `PedidoProducto` (relacion) por voz directa — exige elegir dos ids de
otras entidades, y el `EntityModule` tiene campos de referencia; una frase que la mencione cae en
`accionInexistente` con un mensaje explicito. Numeros: digitos (`20`, `19,90`) y palabras en espanol
de 0 a 999 (`veinte`, `ciento veinte`, `doscientos cincuenta y uno`).

### 6.4 Variabilidad real del reconocedor externo con audio sintetizado

Medido con `integration_test/cu14_voice_online_test.dart` (con red, boton de voz real) y una frase
reproducida por una voz TTS del PC hacia el microfono del telefono (`tool\device-voice-test.ps1
-Mode voice`) — **dato real medido, no una estimacion**, en 3 tandas de 3 corridas cada una:

| Tanda | Resultado (OK/FALLO) | Nota |
|---|---|---|
| Voz TTS lenta (`Rate -2`) | FALLO, FALLO, OK | la voz lenta introduce pausas; el reconocedor corta la frase antes de tiempo |
| Voz TTS a velocidad normal (`Rate 0`) | OK, OK, OK (2-3 intentos cada una) | |
| Igual, tras agregar deteccion de "microfono abierto" (evita hablar antes de tiempo) | FALLO, FALLO, OK (hasta 4 intentos) | la variabilidad no desaparecio |

En total: **5 de 9 corridas** terminaron en exito. Cuando fallo, la causa medida siempre fue el
reconocedor cortando o mal-oyendo la frase (`"crear producto"`, `"crear producto Cami"`, sin
resultado) — **nunca** un error del parser: cada vez que el reconocedor devolvio la frase completa,
el parser y el ejecutor produjeron el comando correcto. Es una limitacion conocida del reconocedor
externo (`com.google.android.tts`) con audio de altavoz-a-microfono, documentada como tal — no se
"arregla" en el parser porque no es ahi donde esta el problema. El test de integracion offline
(campo de texto, sin este reconocedor de por medio) no tiene esta variabilidad.

**Pendiente de confirmar con voz humana real** (no sintetizada): durante las pruebas manuales el
reconocedor no entendio la voz del usuario aunque si entendia la voz sintetizada del PC. Se
investigaron dos causas y se corrigieron las dos: (1) el idioma quedaba fijo en `es_ES` (espanol de
Espana) mientras el telefono esta en `es-BO` — ahora el idioma por defecto se deriva del `Locale`
del dispositivo (`spanishLocaleFor`), y ademas se agrego un selector de idioma en la pantalla
(`voice-locale`: automatico, Bolivia, Latinoamerica, Espana, Mexico, EE. UU.); (2) el usuario podia
empezar a hablar antes de que el microfono estuviera realmente abierto — ahora la fase
`VoicePhase.listening` distingue "Abriendo microfono…" de "Escuchando…" (`SpeechInput.listen(onReady:
...)`). No se alcanzo a re-confirmar con la voz real del usuario antes de este commit; queda como
seguimiento (ver README/seccion de pendientes).

### 6.5 Las 5 excepciones de la ficha

| Excepcion | Quien la dispara |
|---|---|
| `vozNoReconocida` | capa de ASR: no se capto ninguna frase (`error_no_match`, `error_speech_timeout`) |
| `intencionAmbigua` | parser: dos acciones, dos entidades, o mas de un campo a actualizar a la vez |
| `datosFaltantes` | parser (falta un campo) o ejecutor (un slot no pasa `FieldValidator`, p. ej. `precio: abc`) |
| `accionInexistente` | parser: ninguna accion reconocida, incluida una transcripcion vacia (no se agrego un sexto caso aparte: "nada que ejecutar" es el mismo caso) |
| `recursosInsuficientes` | capa de ASR: sin red, sin permiso de microfono, o el reconocedor/idioma no esta disponible en el dispositivo |

Cada una tiene un mensaje distinto y especifico (`voice_failure_messages.dart`); `intencionAmbigua`
y `datosFaltantes` muestran que se entendio y que falta o entre que opciones se duda, no un generico
"no entendi".
