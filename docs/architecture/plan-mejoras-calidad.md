# Plan de mejoras de calidad

Origen: evaluación contra las 7 características de calidad (2026-09-19). Vocabulario según
`CONTEXT.md`. Este documento registra el orden de trabajo y lo que se difiere a propósito.

## Prioridad 1 — Seguridad e integridad: CERRADA (2026-09-20)

| # | Tarea | Estado |
|---|---|---|
| A | `JWT_SECRET` obligatorio: la app falla al importar `tokens.py` si falta o está en blanco. Compose y `.env.example` actualizados | Hecho |
| B | `agregar_clase` / `agregar_asociacion` guardan con `guardar_atomico` (cierra el lost-update) | Hecho |
| C | Token del WS fuera de la query string: `Sec-WebSocket-Protocol: bearer, <jwt>` (backend y gateway del frontend) | Hecho |
| D | Relé WS: solo `cursor`, `node_drag`, `node_drag_end`; campos validados; máx. 4 KB por mensaje; 60 mensajes/s por Sesión con ráfaga de 60 | Hecho |
| E | Rutas `/api/*` legacy y los dos WS legacy exigen autenticación (solo backend; el front legacy no se toca) | Hecho |

Verificación: suite 281 pasan / 2 se omiten; gate de tamaño y `tsc` del front OK; ruff y mypy sin errores nuevos respecto
a un `git worktree` limpio de `HEAD` (ruff 315 frente a 316; mypy 289 frente a 289); tests de
mutación de D y E; prueba extremo a extremo contra un uvicorn real, 14/14 (handshake con
subprotocolo `bearer`, rechazo de `?token=`, relé y rutas legacy).

Decisiones tomadas al cerrar la Prioridad 1 (2026-09-20):
- **Política del relé WS ante mensajes inválidos.** Un tipo permitido (`cursor`, `node_drag`,
  `node_drag_end`) con campos inválidos (p. ej. una coordenada `null`, que produce
  `JSON.stringify(NaN)`) se **descarta sin cerrar**, igual que el exceso de frecuencia: cursor y
  arrastre son flujos con pérdida. Las violaciones de protocolo (mensaje de más de 4 KB, que no es
  JSON, de tipo no permitido, incluido un `canvas_update` enviado por un cliente) **siguen cerrando
  con 1008**. La reconexión completa del gateway queda para la Prioridad 2, cuando se rediseñe
  `collaboration`.
- **Login con contraseña se mantiene** (ADR-0005); el endurecimiento queda diferido.
- **Legacy: protección con autenticación (opción a)**; retirar el router legacy queda para la
  Prioridad 3. La regla de `.claude/rules/fastapi.md` ya refleja que las rutas y WS legacy
  exigen Bearer / subprotocolo `bearer`.

## Prioridad 2 — Colaboración (CU5)

Decisiones y parámetros: **Addendum del 2026-09-20 del ADR-0003** (y `.claude/rules/redis.md`).
Cada paso: diffs por partes que se muestran antes de aplicar, tests propios, comparación de ruff y
mypy contra un `git worktree` limpio de `HEAD`, y E2E con uvicorn real en los pasos que tocan el WS.
`code-review` (Estándares y Especificación) al final.

| Paso | Qué | Estado |
|---|---|---|
| 0 | Addendum del ADR-0003 y actualización de `redis.md` | Hecho |
| 1 | Puerto `CollaborationRoom` (`join`, `leave`, `publish`) con adaptador en memoria; sustituye a `CollaborationRoomRegistry` sin cambiar el comportamiento | Hecho |
| 2 | Publicar `canvas_update` tras el commit, desde la capa de aplicación (puerto `ChangePublisher`), fuera de las rutas HTTP y del asistente | Hecho |
| 3 | Reconexión del gateway: aceptar y cerrar con 4401/4403, backoff 1 s a 30 s con jitter, máximo de 8 reintentos, resync al reabrir, indicador y botón "Reintentar". Verificado en Karma (Nivel A), en un navegador real contra un servidor real con proxy cortable (Nivel B, `scripts/collab-e2e/`) y en la app real (Nivel C, manual asistido) | Hecho |
| 4 | Deltas por elemento (clase o relación completa, no por campo) calculados como diferencia antes/después en la capa de aplicación, con `fromVersion`/`toVersion`; el cliente los aplica solo si está exactamente en `fromVersion` y, si hay hueco, descarga el lienzo entero (`resync`). Cambio directo: el servidor ya no envía `canvas_update`. Contrato compartido en `contracts/canvas-delta.v1.json` con ejemplos generados por el backend (`contracts/canvas-delta.examples.json`) que consume el spec del frontend. `POST /classes` y `POST /associations` ahora publican. La importación XMI queda fuera: siempre crea un Lienzo nuevo, sin Sala a la que avisar. Nombre y descripción del Lienzo quedan fuera del delta (un cambio ahí solo produce un hueco de versión y un resync). Verificado en unitarios (propiedad `aplicar(delta, antes) == después` sobre 18 comandos reales, servicio, adaptador, WS), en el Nivel B (3 casos nuevos: convergencia, hueco por mensaje perdido, corte de red real) y en la app real (Nivel C) | Hecho |
| 5 | `LockStore` (puerto y adaptador en memoria), mensajes de lock, presencia y UX del frontend (adquisición, heartbeat 5s, inactividad 60s, Ajuste B, chips de presencia en header; límite conocido en Nivel B: carrera de arrastre simultáneo; verificado en Nivel B y Nivel C) | Hecho |
| 6 | Adaptadores Redis (fan-out, presencia, `LockStore`); `fakeredis` como dependencia de desarrollo; 2 workers y `--ws-max-size 8192` en compose | Pendiente |
| 7 | `code-review`, docs (ADR, `requirements-matrix`, `redis.md`, este plan) y E2E con 2 workers | Pendiente |

Puntos de partida verificados: hoy se publica antes del commit (`routes.py`, dentro del handler;
el commit está en `get_db_session`); los comandos de layout no emiten evento de dominio;
`ElementoAgregado` no lleva los datos del elemento; el front ya reconcilia el grafo por id de
forma incremental (`UmlGraphReconciliationService`); `WebSocketCollaborationGateway` no tiene
`onclose` ni reconexión; `fakeredis` no está instalado y no hay Redis local.

## Prioridad 3 — Retirar el legado y unificar vocabulario

Retirar el router legacy (`app/legacy/*`), la ruta `legacy-diagram/:roomId`, y
`front_generador_bd/src/services/diagram` (hoy excluida del gate de tamaño). Actualizar
`docs/traceability/requirements-matrix.md` (CU5 y CU12/CU13 están desactualizados). Aplicar el
glosario de `CONTEXT.md` en código, API y eventos.

---

# Tareas diferidas

## Colaboración — diferido de la Prioridad 2

- **Aplicar el lock en el servidor, detrás de una bandera.** Hoy el lock es advisory: el servidor
  lleva y difunde el estado pero no rechaza mutaciones HTTP sobre un elemento bloqueado por otra
  Sesión; la integridad la da la versión optimista. Aplicarlo exige mapear cada comando a los
  elementos que toca (los payloads son heterogéneos: `classId`, `elementId`, `relationId`, ...).
  Nombre de la bandera por definir (Addendum del ADR-0003, §5 y §8).
- **Revocación de acceso en caliente.** El rol solo se calcula en el handshake: una Sesión abierta
  no se revoca aunque se retire al Colaborador (ni existe hoy un flujo para retirarlo). Verificado en
  la app real: tras retirarle el acceso, la Sesión de Beto siguió viva y solo la siguiente conexión
  recibió 4403. Es una funcionalidad que no existe, no un defecto de lo construido; queda fuera de la
  Prioridad 2.
- **Reintento automático tras un `409`.** Hoy, ante `409 VERSION_CONFLICT`, el frontend descarta el
  historial local y recarga el snapshot. Mejor: traer los cambios desde su versión y reaplicar los
  comandos que no se solapan con lo que cambió. Fuera de la Prioridad 2 (Addendum, §6).

## Seguridad — pendientes de la Prioridad 1

- **Límite de tamaño de mensaje en uvicorn.** El límite de 4 KB se aplica en la aplicación
  (`collaboration/schemas.py`), después de que uvicorn ya recibió el mensaje completo; su límite por
  defecto es 16 MiB. Un cliente malicioso puede seguir enviando frames grandes antes de que el
  chequeo actúe. Bajar el límite a nivel de servidor (`--ws-max-size` en el comando de uvicorn y en
  el `CMD` del Dockerfile del backend), no solo a nivel de aplicación.
- **Autorización por sala en los WS legacy.** La autenticación identifica al usuario pero no
  autoriza: cualquier usuario autenticado puede entrar a cualquier `room_id` / `room_name`
  (`/ws/canvas/{room_name}`) y a los backups por `room_id`. Es una tarea de autorización separada
  de la autenticación ya resuelta. Los backups viven en `legacy_uml.db` sin dueño; se resuelve al
  retirar el legado (Prioridad 3).
- **Rotar la clave JWT e invalidar sesiones.** El valor por defecto anterior estuvo en git y en
  `.env.example`; toda instancia que corrió sin `JWT_SECRET` firmó con una clave pública. Rotar
  invalida los access tokens (15 min). Los refresh tokens son opacos y no dependen de esa clave:
  para forzar un nuevo login hay que borrar las filas de sesión. **Hecho (2026-09-20):** el
  `backend_case/.env` local ya usa un secreto nuevo (el valor público anterior no aparece en ningún
  archivo del árbol de trabajo). **Pendiente:** rotar el de cualquier otro entorno (compose,
  despliegues), decidir si se borran las sesiones existentes y, opcional, rechazar en el arranque el
  valor público conocido (sigue en el historial de git).
- **`display_name` del WS** lo envía el cliente y no se valida contra el usuario autenticado
  (permite suplantar el nombre mostrado junto al cursor). Debe derivarse del usuario autenticado.
- **Lienzos sin dueño:** `resolver_rol` devuelve ANFITRION a cualquiera cuando `owner_id` es nulo, y
  `POST /api/v2/canvases` los crea de forma anónima. Los chequeos de rol no protegen esos Lienzos.
  Varios tests dependen de este comportamiento.

## Límites conocidos de los deltas (Paso 4)

- **El cliente aplica el delta sobre su estado local, que se edita de forma optimista.** Un elemento
  que el servidor normaliza distinto de como lo dejó la edición local (por ejemplo, un id generado
  en el servidor) solo se corrige cuando un delta posterior lo vuelve a enviar completo o en el
  siguiente `resync`; el `snapshot` de antes lo sobrescribía todo en cada cambio ajeno.
- **Aplicar un delta sigue re-renderizando el grafo completo** (`applyCanvasContent` →
  `renderCells`, que reconcilia por id): el ahorro es de tráfico, no de trabajo del cliente.
- **La cola durante un arrastre local guarda todos los deltas en orden** (no se pueden colapsar como
  los snapshots) y se limita a 200 (`MAX_QUEUED_DELTAS`): si se desborda, se descarta y se resincroniza.
- **`tests/fixtures/legacy/` está en `.gitignore` (línea 86, `legacy/`):** en un clon limpio la suite
  completa falla en 33 tests de caracterización que necesitan esos ficheros. No depende de este
  trabajo (idéntico en todos los commits de la rama); hay que versionarlos con `git add -f` o mover
  la regla de `.gitignore`.

## Hallazgo de renderizado: Desmontaje de lienzo por conflicto X6 Scroller y Angular Ivy (Paso 5)

- **Causa:** El plugin `@antv/x6-plugin-scroller` reubica el contenedor del lienzo con `appendChild` fuera del árbol DOM que Angular Ivy espera (dentro de `.x6-graph-scroller-content`), disparando `removeViewFromDOM` / `detachViewFromDOM` durante reconciliaciones de vista.
- **Cuándo se manifestaba:** HMR en desarrollo (`ng serve`) y navegación directa con hidratación SSR.
- **Solución aplicada:** Montaje del grafo X6 en un `div` hijo imperativo no gestionado por el template Angular (`this.graphMountEl`), combinado con `ngSkipHydration: 'true'` en la metadata de host de `UmlCanvasComponent`.


## Autenticación (después de la Prioridad 1)

- **Endurecer el login con contraseña** (ADR-0005 mantiene ambos métodos):
  - Mínimo de contraseña: hoy 6 caracteres (`schemas.py`).
  - Límite de intentos y bloqueo de cuenta: hoy no existe.
  - Hasher a Argon2id: el ADR lo indica, pero el código usa PBKDF2-SHA256.

## Riesgos abiertos detectados en la revisión de código

- **El gateway no reconecta.** Mitigado parcialmente: los campos inválidos ya no cierran la Sesión
  (ver "Decisiones tomadas"), pero una violación de protocolo o una caída de red sigue dejando la
  colaboración muerta hasta recargar. La reconexión completa es Prioridad 2.
- **El indicador de conexión no se veía sin desplazar la barra (RESUELTO en el Paso 3).** Estaba al final de la barra de herramientas, fuera de pantalla a 1038 y a 1600 px. Se movió junto a las insignias del encabezado (sala, versión, rol), que siempre son visibles. Verificado en la app real a ambos anchos y en las tres variantes: "Reconectando…" (x 363–463), "Sin conexión" + "Reintentar" (hasta x 529) y "Sin permiso en este lienzo" (x 363–516).
- **El rechazo del handshake no llega como código 4401/4403 (RESUELTO en el Paso 3).** Con un servidor real, cerrar antes
  de `accept()` se traduce en HTTP 403 y el navegador ve un fallo de conexión, no el código. El
  cliente no distingue "sin permiso" de "sin red"; la reconexión no debe entrar en bucle con 403.
- **`CanvasRepository.guardar()` conserva una rama de actualización sin control de versión.** Ya no
  tiene llamadores que la usen para actualizar (solo creación e importación), pero puede reintroducir
  el lost-update. Restringirla a inserción.
- **Prueba en navegador real pendiente.** El cambio del gateway (`new WebSocket(url, ['bearer',
  token])`) se verificó con `tsc` y con un cliente WebSocket real, pero no en un navegador, y el
  gateway no tiene tests unitarios.
- **Deuda menor en lo tocado:** bloque `authenticate_ws_user` + cierre 4401 duplicado en los dos WS
  legacy; los códigos de cierre (4401, 4403, 1008) están definidos en tres módulos; el helper de
  registro de usuarios se repite en cuatro archivos de test (extraer a `conftest.py`);
  `contextlib.suppress(Exception)` en el relé no registra nada (conserva el comportamiento
  anterior, pero oculta fallos); errores de lint previos en archivos tocados (B904, UP017, E501,
  I001 inline).

## Integridad y API

- `expectedVersion` opcional en `POST /classes` y `POST /associations`, para detectar estado
  obsoleto entre peticiones distintas (hoy solo se detecta la carrera dentro de una petición).

## Dominio (requieren confirmación explícita: tocan `core/uml_domain`)

- **Interfaz:** retirar `UmlClass.is_interface` o documentar cuál de las dos representaciones usa
  `UmlRealization.supplier_interface_id`.
- **Operación:** el campo legacy `methods` del repositorio queda marcado para migrar.

## Menores

- **[RESUELTO - Paso 6 / Parte E]** Desajuste de puerto corregido: tanto `docker-compose.app.yml`, `backend_case/Dockerfile`, `front_generador_bd/proxy.conf.json` como la documentación se unificaron al puerto canónico `8000` con Uvicorn multi-worker (`--workers 2 --ws-max-size 8192`).
- Contraseña de PostgreSQL en `docker-compose.app.yml` pendiente de parametrización en `.env`.

---

## Verificación Manual Multi-Worker (Paso 6 - Prueba de Humo en Vivo)

Dado que la suite automatizada de pytest corre en un único proceso con bucle de eventos local, la validación final del fan-out entre procesos independientes debe verificarse con Uvicorn multi-worker (`--workers 2`):

1. **Levantar infraestructura y aplicación:**
   ```bash
   docker compose -f docker-compose.db.yml up -d
   docker compose -f docker-compose.app.yml up --build
   ```
2. **Verificar inicialización de workers en logs:**
   Ejecutar `docker logs -f fastapi_backend_UML` y verificar:
   - `Started parent process [PID_PADRE]`
   - `Started worker process [PID_1]`
   - `Started worker process [PID_2]`
   - Mensajes de conexión exitosa a Redis Pub/Sub (`REDIS_URL=redis://redis:6379/0`).
3. **Verificar fan-out cross-worker en vivo:**
   - Abrir **Navegador 1** (p. ej. Chrome normal) y **Navegador 2** (p. ej. Chrome Incógnito / Firefox) en el mismo canvas: `http://localhost:4200/canvas/<id>`.
   - Comprobar en los logs de Docker que las dos conexiones WebSocket entrantes fueron distribuidas entre los dos workers (`PID_1` y `PID_2`).
   - En Navegador 1, mover el cursor o arrastrar un nodo: verificar que en Navegador 2 el cursor y el movimiento se reflejan inmediatamente en tiempo real sin duplicación (validación anti-eco y entrega Pub/Sub).
   - En Navegador 1, hacer clic sobre una clase para adquirir su lock: verificar que en Navegador 2 la clase se marca como bloqueada por el primer usuario en tiempo real vía Redis.
