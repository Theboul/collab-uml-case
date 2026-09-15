# Auditoría de calidad CU1–CU5 — Diagramador UML (Examen 2)

**Fecha:** 2026-09-08
**Metodología:** Auditoría de cada CU contra un checklist de Definition of Done, verificado línea por línea contra código real (no descripciones de memoria). Realizada por Claude Code sobre el repositorio real, revisada en esta conversación.

---

## Resumen ejecutivo — hallazgos por severidad

### ✅ Resuelto (era crítico)

| # | CU | Hallazgo | Evidencia de resolución |
|---|---|---|---|
| 1 | CU2 + CU5 | Falta de autorización real por rol/pertenencia al lienzo (`GET /{canvas_id}` y WebSocket de colaboración). | `CANVAS_ACCESS_FORBIDDEN` (403) en `routes.py`/`canvas_service.py` + `WS_FORBIDDEN_CLOSE_CODE = 4403` en `ws_router.py`. Tests pasando: `test_get_canvas_forbidden_for_user_without_access`, `test_execute_command_forbidden_for_user_without_access`, `test_add_class_and_add_association_forbidden_for_user_without_access`, `test_validate_canvas_forbidden_for_user_without_access`, `test_ws_rejects_connection_without_valid_role` (verificado 2026-09-14, todos PASSED). |

### 🔴 Crítico

| # | CU | Hallazgo |
|---|---|---|
| 2 | CU4 | **Reconexión de relación se revierte sola, silenciosamente.** X6 captura el evento de reconexión (`EdgeReconnectedEvent` con `sourceId`/`targetId` nuevos), pero el handler lo descarta. No existe `RECONNECT_RELATION` en el backend. El usuario ve la relación "movida" hasta el próximo `renderCells()` completo, momento en que vuelve sola a la posición original. El streaming de CU5 (broadcast de `canvas_update` en cada cambio de otro peer) **aumenta la frecuencia** con la que esto se manifiesta. |

### 🟡 Serio

| # | CU | Hallazgo |
|---|---|---|
| 3 | CU2 | `join_canvas` colapsa a identidad `"anonymous-user"` si no hay usuario autenticado — mitigado hoy solo por el guard de Angular (`authGuard`), no por la API en sí. |
| 4 | CU4 | Las relaciones tipo `DEPENDENCY` se persisten como `UmlAssociation` genérica — pierden su tipo semántico real. |
| 5 | CU5 | Los mensajes WebSocket no se validan ni tipan del lado del servidor — es un relay ciego de cualquier JSON. |
| 6 | CU5 | No existe ninguna lógica de reconexión, ni cliente ni servidor. Si el WS cae, el usuario deja de recibir `canvas_update`/cursores/`node_drag` sin ningún aviso, hasta recargar manualmente. |
| 7 | CU5 | Duplicación visual de nodos en X6 al minimizar/restaurar una pestaña — **repro con logs (`existingCellsWithSameId`, `domCount`, contador de `applyCanvasSnapshot`) pendiente de confirmar por el usuario.** |
| 8 | CU1 | `node:added` (evento genérico de X6) dispara lógica de negocio (creación de clase + comando al backend) — hoy protegido solo por el orden accidental de dos líneas (`setSnapshot` antes de `renderCells`), sin garantía de tipo ni test. |

### 🟢 Menor / UX

| # | CU | Hallazgo |
|---|---|---|
| 9 | CU2, CU3, CU4, CU5 | Mismo error handler agresivo: ante **cualquier** error de `executeCommandWithHistory` (no solo `409`), se limpia el historial de undo/redo y se fuerza un `reloadSnapshot()` completo. Un solo fix resuelve los cuatro hallazgos. |
| 10 | CU4 | Cambiar el tipo de una relación a `Generalization`/`Dependency` es un no-op silencioso — no hay rama de código para esos casos. |
| 11 | CU4 | Multiplicidad inversa (ej. `"5..2"`) genera `500` sin control, en vez de `422`. |
| 12 | CU1 | Dos pipelines distintos para `CREATE_CLASS` (click vs. drag&drop): solo el de click pasa por historial de undo/redo. Una clase creada por drag&drop no se puede deshacer con Ctrl+Z. |
| 13 | CU1 | IDs de origen distinto entre los dos pipelines: click usa `crypto.randomUUID()`, drag&drop deja que X6 genere el id. |
| 14 | CU5 | `collaboration_room_registry` es un dict en memoria de un solo proceso — no escala a múltiples instancias de backend (Redis nunca se usa hoy pese al puerto `LockStore` de papel). |
| 15 | CU5 | Sin presencia real ni selección remota — terreno declarado vacío por el propio ADR-0003, no es una sorpresa. |

---

## CU1 — Crear nuevo lienzo UML

**Estado general:** sólido en persistencia/backend; el hallazgo de `node:added` es una fragilidad de diseño real, aunque hoy no manifiesta bug.

- Creación, persistencia y separación ModeloUML/DiagramLayout: **cumplidos**.
- Selección, navegación (pan/zoom), puertos de conexión: **cumplidos**.
- Undo/Redo: la infraestructura (`EditorHistoryService`, stack propio sin depender de X6 History) está bien diseñada, pero **no cubre el pipeline de creación por drag&drop** (hallazgo #12).
- Calidad de código: sin archivos ≥1000 líneas; `uml-graph.service.ts` en 804 líneas, cerca del umbral de revisión.

## CU2 — Ingresar a lienzo existente

**Estado general:** snapshot/hidratación/versionado sólidos; el hallazgo de autorización es grave.

- `GET /{canvas_id}` sin verificación de rol — **resuelto** (hallazgo #1, ver tabla resumen).
- `join_canvas` con fallback a `"anonymous-user"` (hallazgo #3).
- Error handler agresivo ante cualquier fallo, no solo `409` (hallazgo #9).
- Snapshot inicial, hidratación, `resolver_rol` como dato informativo (no como gate) todos confirmados con evidencia de código.

## CU3 — Gestionar elementos (clases, atributos, operaciones, parámetros)

**Estado general:** el módulo más sólido de los cinco. CAS atómico real en una sola sentencia SQL, captura del `undo_payload` antes de mutar, guard exhaustivo de Delete/Backspace en inputs.

- Sin hallazgos críticos ni serios propios — hereda el error handler agresivo (hallazgo #9).
- Algunos ítems de UI puntual (disparador exacto de doble clic, binding del panel lateral) quedaron sin verificación exhaustiva por no ser evaluables por lectura estática.

## CU4 — Gestionar relaciones del diagrama de clases

**Estado general:** el más débil de los cinco. El propio código se autodeclara parcial (`relation_handlers.py`: *"retrocompatibilidad... el ciclo de vida interactivo completo corresponde a CU4"*).

- Reconexión de relación no persiste, se revierte sola (hallazgo #2).
- `DEPENDENCY` se guarda como `ASSOCIATION` (hallazgo #4).
- Cambiar tipo a Generalization/Dependency es no-op silencioso (hallazgo #10).
- Multiplicidad inversa da `500` en vez de `422` (hallazgo #11).
- Creación, eliminación en cascada, undo/redo del resto de tipos: sólidos, mismo patrón que CU3.

## CU5 — Colaborar en la edición del diagrama

**Estado general:** exactamente lo que el ADR-0003 describe con honestidad — "paso 1" (transporte) y "paso 2" (cursores + sync de resultado) completos y bien construidos tras el trabajo de esta sesión (exclusión de eco por `peerId`, guard `isDraggingLocally`, TTL de snap-back). "Paso 3" en adelante (locks, presencia, Redis) es terreno confirmado vacío, ya declarado en el propio ADR.

- WebSocket sin autenticación ni autorización — **resuelto** (hallazgo #1, ver tabla resumen).
- Mensajes WS sin validación de schema en servidor (hallazgo #5).
- Sin lógica de reconexión (hallazgo #6).
- Duplicación de nodos al minimizar/restaurar — repro pendiente (hallazgo #7).
- Optimistic lock a nivel de lienzo completo, no granular por recurso — es exactamente lo que el ADR-0003 ya identificó como "Paso 3" pendiente.

---

## Orden recomendado de resolución

1. ~~Autorización real (CU2 + CU5)~~ — **resuelto**, ver hallazgo #1.
2. **Reconexión de relación (CU4)** — pérdida de datos real, agravada por el streaming de CU5.
3. **Error handler agresivo (CU2/CU3/CU4/CU5)** — un fix, cuatro hallazgos resueltos.
4. **DEPENDENCY mal persistida (CU4)** y **validación de mensajes WS (CU5)**.
5. **Cerrar la reproducción pendiente de duplicados (CU5)** — confirmar antes de dar el streaming por terminado.
6. Resto de hallazgos menores — quedan documentados para el roadmap, no bloquean nada urgente.
