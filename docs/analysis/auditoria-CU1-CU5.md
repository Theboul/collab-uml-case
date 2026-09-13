# Auditoría de calidad — CU1 a CU5

Sesión de auditoría contra código real (no memoria/documentación), CU por CU, siguiendo los
checklists de calidad de cada iteración. Estados: `[x]` Cumplido, `[~]` Parcial, `[ ]` Pendiente.

Contexto de origen: esta auditoría nació dentro de una sesión de debugging de un bug de
duplicación de nodos en el canvas colaborativo (CU5). El **hallazgo crítico #1** (falta de
autorización real en `GET /{canvas_id}` y en el WebSocket de colaboración) fue corregido en la
misma sesión — ver commits asociados. El resto de los hallazgos quedan documentados como estado
en el momento de la auditoría, no todos corregidos.

---

## CU1 — Crear nuevo lienzo UML

### Hallazgo principal
`UmlGraphService` (frontend) usa el evento genérico de X6 `'node:added'` para detectar altas por
Drag&Drop y dispararles un comando `CREATE_CLASS` — pero ese mismo evento también se dispara en
cada `renderCells()` de un snapshot completo (`applyCanvasSnapshot`, cualquier `canvas_update`
remoto). Hoy no falla porque `state.setSnapshot()` siempre corre *antes* de `renderCells()` en
los dos lugares donde se invoca, y el guard `!currentModel.classes.some(...)` depende
enteramente de ese orden accidental — no hay ningún tipo ni test que lo garantice. Viola el
principio "X6 actúa únicamente como representación visual del modelo" (Sección 2 del checklist).

### Checklist
- **1. Creación del lienzo**: cumplida sólidamente. ID estable, `ModeloUML` vacío válido,
  `DiagramLayout` separado desde `canvas_service.py:crear_lienzo()`, sin datos mock, backend
  confirma antes de responder (`await self.repository.guardar(...)`), abre inmediato en el
  editor (`test_create_canvas_cu1_initial_state` pasa).
- **2. Editor y canvas**: LOADING/READY/ERROR vía signals de `EditorStateService`. **[~]** "X6
  solo representación visual" — ver hallazgo principal arriba.
- **3. Creación de clases**: **[~]** dos pipelines de código separados para el mismo comando
  semántico `CREATE_CLASS` — click (`EditorCommandService.createClass()` →
  `executeCommandWithHistory`, con historial) vs Drag&Drop (`nodeAdded$` → `dispatchCommand()`,
  **sin** historial). IDs también con dos esquemas distintos: `crypto.randomUUID()` (click) vs
  ID interno de X6 (Drag&Drop, `graph.createNode({...})` sin `id:` explícito en
  `uml-graph.service.ts:startDnd()`). Backend sí valida colisión de ID
  (`class_handlers.py:89-95`).
- **4. Selección e interacción**: cumplida — rubberband, shift/ctrl+click, delete grupal.
- **5. Navegación**: pan/zoom no disparan `MOVE_ELEMENT` (doble guarda: `nodeMovable` deshabilitado
  + chequeo explícito en los handlers de `node:move`/`node:moved`).
- **6. Puertos**: ocultos por defecto, visibles solo con selección única, ciclo completo
  verificado.
- **7. Undo/Redo básico**: X6 History desactivado (`new History({ enabled: false })`),
  `EditorHistoryService` como stack propio en memoria. **[~]** consecuencia directa del hallazgo
  de la Sección 3: las clases creadas por Drag&Drop no tienen Undo.
- **8. Persistencia**: aparece en lista real, sobrevive salir/volver, mismos IDs, sin mock
  paralelo.
- **9. Calidad de código**: **[~]** `uml-graph.service.ts` en 804 líneas (cruzó el umbral de
  advertencia de 800 durante esta sesión, por la acumulación de logs `[DIAG]` de diagnóstico —
  candidato a refactor preventivo). Resto de checks (lint/tests/build) OK.

---

## CU2 — Ingresar a un lienzo existente

### Hallazgos graves (el #1 fue corregido esta sesión — ver sección final)
- **A. Conocer el `canvas_id` alcanzaba para leer el modelo completo — sin 403 en todo el módulo
  de canvases.** `GET /{canvas_id}` devolvía el modelo completo a cualquiera, autenticado o no,
  con o sin acceso real; el rol `INVITADO` era solo informativo, nunca bloqueaba nada.
- **B. `join_canvas` colapsaba a todos los usuarios no autenticados en una identidad
  `"anonymous-user"` compartida** (`routes.py`: `user_id = current_user.id if current_user else
  "anonymous-user"`). Mitigado en la práctica porque `/join/:accessCode` tiene `authGuard` en el
  frontend (fuerza login con `returnUrl` antes de llegar ahí), pero la API en sí no era
  defensiva por su cuenta.
- **C. El error handler genérico de `executeCommandWithHistory` limpia el historial de undo/redo
  ante *cualquier* error** (network transitorio o 409 real), no solo ante conflicto de versión
  real — no corrompe el modelo (siempre resincroniza), pero es más agresivo de lo necesario.

### Checklist
- **1. Acceso**: código/enlace reutilizan el mismo caso de uso
  (`buscar_por_codigo_acceso` normaliza espacios/mayúsculas/prefijo `room-`). **[ ]** "conocer el
  workspaceId no equivale a autorización" — no cumplido (hallazgo A, corregido luego).
  **[ ]** 403 controlado — no existía en absoluto en `modeling/` (confirmado por grep). 404 sí
  (`CanvasNoEncontrado` → 404).
- **2. Autenticación y retorno**: `returnUrl` conservado (`auth.guard.ts`), continúa al lienzo
  tras login (`login.component.ts`), auth/autorización separadas en el backend.
- **3. Participación y rol**: rol conservado, anfitrión nunca degradado (`unirse_a_lienzo` chequea
  `owner_id == user_id` antes que colaborador). **[~]** idempotencia real solo si `user_id`
  identifica a una persona real (hallazgo B).
- **4. Snapshot inicial**: completo — modelo, layout, versión, rol, IDs estables, normalización
  preventiva de parámetros históricos sin ID (test `test_preventive_parameter_normalization_on_get`
  pasa).
- **5. Estado de carga**: LOADING antes que READY, sin autosave (no existe el concepto en el
  frontend — toda persistencia es por comando explícito).
- **6. Hidratación visual**: `UmlDiagramAdapterService.modelToCells()`, IDs/posiciones/tamaños
  correctos. **[~]** viewport (zoom/pan) al cargar — no confirmado si se aplica.
- **7. Recuperación semántica**: IDs preservados en el roundtrip completo.
- **8. Versionado**: `expectedVersion` en toda mutación, CAS real, 409 provoca resync — pero ver
  hallazgo C (resync también en errores no-409).
- **9. UX de error**: **[ ]** 403 como falta de acceso — no existía. 404/409 con mensajes
  específicos. **[~]** 5xx/red sin distinción de status code en el frontend.
- **10. Preparación para CU5**: WS se conecta solo después de tener snapshot válido
  (`collabGateway.connect(dto.id)` corre después de `setSnapshot`), mismo `modelVersion`
  compartido entre snapshot inicial y realtime.
- **11. Calidad de código**: `CanvasCollaboratorORM` es una tabla de unión legítima (no
  especulativa), sin tablas nuevas innecesarias.

---

## CU3 — Gestionar elementos del diagrama de clases

El CU mejor implementado de los cinco. Sin hallazgos graves.

### Checklist
- **1. Clase UML**: create/rename/delete/restore completos, con validación de nombre vacío
  (`Field(..., min_length=1)`, doble capa frontend+backend) y de duplicados (case-insensitive,
  create y rename). Undo restaura con mismo ID.
- **2. Atributos**: CRUD completo, `UPDATE_ATTRIBUTE` siempre por `attributeId` (nunca índice),
  duplicados de nombre validados, IDs generados client-side (`crypto.randomUUID()`) y respetados
  server-side salvo colisión.
- **3. Operaciones**: sobrecarga por firma correctamente implementada —
  `_compute_op_signature()` = `(nombre.lower(), tupla_de_tipos)`, permite mismo nombre con
  distintos parámetros, rechaza firmas idénticas (verificado en add y en update).
- **4. Parámetros**: CRUD completo, sin parámetros como texto plano (entidad de dominio propia
  `UmlParameter`), normalización de históricos sin ID persistida vía CAS, sin IDs generados solo
  en memoria (todo lo que se genera server-side se persiste en la misma transacción).
- **5. Subelementos interactivos**: atributos/operaciones no son nodos X6 independientes
  (renderizados como texto compuesto dentro de un único nodo), `selectedSubElement` es estado
  puramente UI, `elementId` es la identidad real, `rowIndex` solo cálculo visual temporal,
  `rowHighlight` hijo del `<g>` del nodo (hereda transform de pan/zoom automáticamente), puertos
  se mantienen visibles al seleccionar subelemento (fuerza reselección del nodo padre).
- **6. Redimensionamiento y render**: altura/separadores calculados dinámicamente desde
  cantidad de atributos/operaciones, tamaño mínimo determinista, renderizar nunca muta
  `ModeloUML`.
- **7. Eliminación en cascada**: `DELETE_ELEMENTS` captura clases+relaciones+generalizaciones+
  layouts en un `undoPayload` tipado (Pydantic) **antes** de mutar; `RESTORE_ELEMENTS`
  reconstruye con IDs exactos, incluido el layout.
- **8. Undo/Redo semántico**: X6 History desactivado, historial propio, HTTP 200 gate confirmado
  (`pushAction` dentro del callback `next:`), múltiples pasos (arrays, no un solo slot). **[~]**
  mismo matiz de CU2 (error handler agresivo ante cualquier fallo, no solo 409).
- **9. Persistencia y CAS**: CAS real y atómico — un único `UPDATE ... WHERE id=? AND version=?`
  con `.returning(...)`, sin ventana de lectura-luego-escritura; distingue 404 (no existe) de 409
  (versión desactualizada) en la misma sentencia.
- **10. Inputs y edición**: el punto más sólido de todo el audit. `commitInlineEdit()` compartido
  por Enter y blur (idempotente por diseño — el segundo llamado encuentra el estado ya nulo),
  guard exhaustivo contra Delete/Backspace disparando eliminación de elementos mientras se
  escribe en `input`/`textarea`/`select`/`contenteditable` (chequea `event.target` Y
  `document.activeElement`, con `.closest(...)` para casos anidados).
- **11. Calidad de código**: `CommandDispatcher` sin switch gigante (docstring lo dice
  explícitamente), payloads Pydantic tipados en el límite HTTP, `dict[str, Any]` solo como
  contenedor de transporte (nunca contrato de dominio).

---

## CU4 — Gestionar relaciones del diagrama

El CU con más hallazgos graves — varios de pérdida silenciosa de datos. El propio código se
autodeclara parcial: `relation_handlers.py` dice literalmente *"Manejadores de comandos
existentes de relaciones para retrocompatibilidad (CU1). Nota: El ciclo de vida interactivo
completo de relaciones corresponde a CU4"*.

### Hallazgos graves
- **A. Reconectar una relación a otra clase es una ilusión visual que se revierte sola.** X6
  captura `sourceId`/`targetId` nuevos en `edge:connected` (`isNew: false`), pero
  `edgeReconnected$` en el facade los descarta y solo llama `updateRelationLayout()` →
  `UPDATE_RELATION_LAYOUT`, que únicamente toca `sourcePort`/`targetPort` en el layout — nunca
  `sourceClassId`/`targetClassId` en el modelo semántico. No existe ningún comando
  `RECONNECT_RELATION` en el backend (confirmado por grep). Al próximo re-render completo
  (recarga, `canvas_update` de otro peer), la relación vuelve silenciosamente a su clase
  original.
- **B. Las relaciones tipo DEPENDENCY se guardan como ASSOCIATION**, perdiendo el tipo — es
  seleccionable en la UI (`uml-toolbar.component.html`, `relation-context-menu.component.ts`)
  pero `relation_handlers.py` no tiene ninguna rama `elif rel_type == "DEPENDENCY"`, siempre
  construye una `UmlAssociation`.
- **C. Cambiar el tipo de una relación existente a GENERALIZATION es un no-op silencioso** —
  `UPDATE_RELATION` busca únicamente en `lienzo.modelo.associations`; si la relación ya es una
  generalización (vive en `lienzo.modelo.generalizations`), no la encuentra y no hace nada, sin
  avisar al usuario.
- **D. Multiplicidad inversa ("5..2") no da 422 controlado — crashea con 500.** La validación
  existe (`MultiplicityRange.__post_init__` en `core/uml_domain/model.py`), pero lanza
  `ValueError` plano; ni el dispatcher ni ningún exception handler registrado capturan
  `ValueError` genérico (`UmlDomainError` no hereda de `ValueError`).
- **E. Sin chequeo de reflexividad/duplicados en la creación** — `agregar_asociacion`/
  `agregar_generalizacion` solo validan existencia de IDs, no `origen_id == destino_id` ni
  generalizaciones duplicadas. La detección de ciclos de herencia sí existe
  (`validation.py`, DFS sobre el DAG) pero vive en el validador de `/validate` (invocación
  explícita separada), no se ejecuta automáticamente al crear una relación desde el editor.

### Checklist (resumen — detalle completo en el hilo de la sesión)
- **1-4**: tipos/creación/identidad/semántica — cumplidos salvo DEPENDENCY (hallazgo B).
- **5-7**: selección/propiedades/multiplicidades — cumplidos salvo el rango inverso (hallazgo D).
- **8-9**: cambio de tipo/reconexión — los más débiles (hallazgos A y C).
- **10**: validaciones estructurales — solo existencia de IDs, sin reflexividad/duplicados
  (hallazgo E).
- **11-14**: delete/undo-redo/modelo-vs-layout/persistencia — sólidos para lo que SÍ se persiste
  correctamente.
- **15**: calidad de código — sin switch gigante, Pydantic tipado, sin tablas nuevas; el propio
  archivo admite ser la versión "básica/legacy", no el rediseño completo de CU4.

---

## CU5 — Colaboración en tiempo real

Toda la investigación de esta sesión fue, en esencia, un bug hunt dentro de CU5. El propio
`ADR-0003` (aprobado, 2026-09-08) documenta el estado real: "paso 1" (transporte) y "paso 2"
(cursores) completos; "paso 3" en adelante (locks granulares, presencia real, resiliencia de
reconexión, autenticación del canal) es terreno confirmado vacío — no bugs ocultos, gaps ya
declarados en el propio ADR antes de esta auditoría. El ADR también cita, de forma independiente,
el mismo hallazgo del error handler agresivo señalado en CU2/CU3.

### Hallazgos graves (el de autenticación fue corregido esta sesión — ver sección final)
- **A. El WebSocket de colaboración no tenía autenticación ni autorización — cero.**
  `canvas_collaboration_websocket` no dependía de `get_current_user`/JWT; cualquiera que supiera
  un `canvas_id` se conectaba y participaba activamente (cursor, `node_drag`) sin verificación.
- **B. Los mensajes WebSocket no se validaban ni tipaban del lado del servidor** — relay ciego,
  cualquier JSON (o texto no-JSON) se reenviaba tal cual a toda la sala.
- **C. Sin ninguna lógica de reconexión**, ni cliente ni servidor — sin `onclose`, sin reintento,
  sin backoff, sin aviso de estado en la UI.

### Checklist
- **1. Conexión realtime**: WS se abre solo tras snapshot CU2, asociado al lienzo correcto,
  desconexión limpia recursos. **[ ]** autenticación/autorización (hallazgo A, corregido luego).
  **[ ]** reconexión (hallazgo C).
- **2. Presencia**: no existe roster explícito de participantes (`presence$` es un no-op
  documentado en el propio código: *"quedan como no-ops deliberados todavía"*); presence efímera
  y no persistida donde sí existe (cursores).
- **3. Cursores remotos**: implementados sólidamente — coordenadas de canvas (no pantalla),
  throttle de 80ms (dentro del rango sugerido por el ADR), limpieza por TTL de 5s (no por evento
  explícito de desconexión, que el backend no manda), color por participante.
- **4. Selección remota**: no implementada — ningún mecanismo transmite qué clase/relación
  selecciona otro usuario.
- **5-6. Cambios semánticos / no pixel-a-pixel**: bien resueltos — snapshot completo vía
  `canvas_update` (simple y consistente aunque no es "incremental" en sentido estricto),
  streaming de `node_drag` nunca persiste hasta el fin del gesto.
- **7. Versionado y orden**: guard de versión descarta obsoletos/duplicados; **[ ]** sin
  estrategia de detección de eventos perdidos (ningún ACK ni número de secuencia).
- **8. Conflictos**: CAS real como autoridad, pero **[ ]** el `version` es de lienzo completo, no
  por elemento — el propio ADR-0003 ya identifica esto como el "Paso 3" no resuelto (falsos
  conflictos entre usuarios editando cosas distintas). Sin locks granulares (`LockStore` es un
  puerto de papel, sin adaptador Redis real).
- **9. Redis/distribución**: **[ ]** no se usa Redis en absoluto — `collaboration_room_registry`
  es un `dict` en memoria de un solo proceso; con más de una instancia de backend, peers en
  instancias distintas nunca se verían entre sí.
- **10. Reconexión y resync**: no implementado (hallazgo C) — el modelo persistente en sí no se
  destruye (vive en Postgres/SQLite, ajeno al WS), pero no hay ninguna UX de
  reconnecting/offline.
- **11-12. UX colaborativa / rendimiento**: probado con 2 clientes esta sesión (no 3+), sin
  tormenta de pointermove, canvas usable durante actividad remota tras los fixes de esta sesión
  (`peerId`, `isDraggingLocally`).
- **13. Seguridad**: **[ ]** sin autenticación del canal (hallazgo A), **[ ]** mensajes sin
  validar/tipar (hallazgo B). El `peer_id` en sí SÍ es server-generado y no falsificable.
- **14. Calidad de código**: transporte bien separado del dominio, `CollaborationGateway` no
  concentra lógica de negocio (repartida en `RemoteCanvasSyncService`/`RemoteNodeDragService`/
  `RemoteCursorsService`), archivos pequeños y focalizados. **[ ]** sin tests de conflicto en
  contexto realtime ni de reconexión/resync (consistente con que la funcionalidad tampoco
  existe).

---

## Hallazgo adicional (fuera de alcance del fix de autorización — solo documentado)

**`GET /canvases` lista TODOS los lienzos del sistema sin filtro por usuario.**
`list_canvases()` (`routes.py`) no tiene ningún parámetro `current_user` ni filtro por
`owner_id`/colaborador — devuelve `name`/`description`/`roomName`/`ownerId` de cada lienzo en la
base de datos a cualquiera que llame el endpoint, autenticado o no. No es tan grave como el
hallazgo #1 (no expone el modelo UML completo, solo metadata), pero es una superficie de
information disclosure real que debería filtrarse por participación del usuario (dueño o
colaborador) en una iteración futura. **No corregido en esta sesión** — queda documentado a
pedido explícito del usuario.

---

## Fix aplicado en esta sesión: hallazgo crítico #1 (autorización real)

**Alcance:** `GET /canvases/{canvas_id}`, `POST /canvases/{canvas_id}/commands`,
`POST /canvases/{canvas_id}/classes`, `POST /canvases/{canvas_id}/associations`, y el WebSocket
`/ws/canvas/{canvas_id}/collaboration`.

**Decisiones de diseño confirmadas:**
1. `GET /canvases/by-room/{room_name}` se dejó **sin cambios** — conocer el `room_name` (link
   compartido) sigue siendo la autorización válida para ver el lienzo, coherente con el flujo
   real del frontend (`loadCanvas()` llama `getCanvasByRoom()` directo, sin pasar por `/join`
   antes).
2. Código de cierre WebSocket al rechazar: `4403` (custom, en el rango reservado 4000-4999 de
   RFC 6455, espeja semánticamente el 403 HTTP).
3. Un lienzo con `owner_id=None` (creado sin autenticación) resuelve rol `ANFITRION` para
   cualquiera — no hay dueño real a quien proteger, y esto evita romper los ~20 tests/flujos
   históricos que operan sin token.

**Verificación de la decisión 3 — ¿`owner_id=None` es alcanzable en producción real?**
Confirmado que **no, no vía la SPA**: el único call-site de `POST /canvases` es
`dashboard.service.ts` (`crearLienzo`), invocado exclusivamente desde `DashboardComponent`, que
tiene `canActivate: [authGuard]` (`app.routes.ts:12`). `authGuard` solo deja pasar si
`isAuthenticated()` es verdadero o si el refresh silencioso por cookie tiene éxito — si ambos
fallan, redirige a `/login` y bloquea la navegación. Y una vez autenticado, `auth.interceptor.ts`
adjunta `Authorization: Bearer <token>` a toda request `/api/*` no relacionada con
login/register/refresh, automáticamente. Es decir: **Dashboard → `authGuard` → `auth.interceptor.ts`
garantiza que toda creación de lienzo disparada desde la app real siempre lleva JWT.**
`owner_id=None` es, por lo tanto, exclusivamente un artefacto de los tests que le pegan a la API
directo (bypaseando Angular y su guard) — no un camino real de producción vía la SPA.

**Matiz que queda abierto, no introducido ni empeorado por este fix:** `POST /canvases` en el
backend sigue usando `CurrentUserOptionalDep` — alguien que le pegue directo al endpoint HTTP
(curl/Postman, sin pasar por la SPA) todavía puede crear un lienzo anónimo hoy en producción,
exactamente igual que podía antes de esta sesión. Es una decisión de diseño preexistente de la
API pública, no algo que el hallazgo #1 haya tocado. Si en algún momento se quiere cerrar esa
puerta (exigir JWT real también en la creación, no solo en lectura/mutación de un lienzo
existente), es una decisión de producto aparte — queda documentada acá como pendiente, no
resuelta.

**Cambios:**
- `canvas_repository.py`: `resolver_rol()` gana el caso `owner_id is None → "ANFITRION"`.
- `shared/security/dependencies.py`: nueva `get_current_user_optional_ws()` (JWT vía query param
  `?token=...`, sin precedente previo en el proyecto ni en el stack legacy).
- `canvas_service.py`: helper `_verificar_acceso_edicion()` + los 3 métodos de mutación
  (`ejecutar_comando`, `agregar_clase`, `agregar_asociacion`) ahora reciben `user_id` y lo
  invocan.
- `routes.py`: `get_canvas` rechaza `INVITADO` con 403; los 3 endpoints de mutación ganan
  `current_user: CurrentUserOptionalDep`.
- `ws_router.py`: resuelve rol **antes** de aceptar el handshake, con una sesión de DB de vida
  corta abierta manualmente (`async with async_session_factory()`) — un `Depends()` de sesión a
  nivel del handler WS quedaría abierto durante toda la conexión, no solo el chequeo, y agota el
  pool con pocos WS concurrentes (bug real encontrado y corregido durante la implementación de
  este mismo fix).
- `collaboration-gateway.service.ts`: `connect()` ahora manda `?token=...` además de
  `display_name`.
- Tests nuevos: 6 en `test_canvases_commands.py` (403 HTTP + regresión de lienzo anónimo) y 2 en
  `test_collaboration_ws.py` (4403 WS + flujo legítimo), usando usuarios reales vía
  `POST /api/v2/auth/register`.

**Verificación:** suite completa de `backend_case/tests/` — 63 passed, 0 failed (incluye los
~20 tests anónimos históricos sin modificar). `ruff`/`tsc`/`ng build`/file-size check limpios de
issues nuevos.
