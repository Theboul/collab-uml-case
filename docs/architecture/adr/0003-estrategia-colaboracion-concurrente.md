# ADR-0003: Estrategia de Colaboración Concurrente (CU5)

**Estado:** Aprobado, con addendum del 2026-09-20 (parámetros, corrección de una premisa y decisiones de implementación; ver el final del documento)
**Fecha:** 2026-09-08
**Decisores:** Theboul
**Casos de uso relacionados:** CU5 (Colaboración), CU1-CU4 (afectan el recurso que se bloquea)

> **Investigación completada (2026-09-06):** se confirmó con evidencia real que `backend_case/app/collaboration/` es un módulo vacío (solo docstring), `CollaborationGateway` en el frontend es un No-Op explícito y confirmado sin provider real cableado (`git grep` sin resultados), y el único mecanismo de concurrencia existente es el optimistic lock de `version` a nivel de lienzo completo — cero presencia, cero bloqueo granular, cero puntero de colaborador. Terreno limpio: este ADR no necesita reconciliarse con ninguna implementación previa.

---

## Contexto

La ficha de CU5 establece un flujo explícito con pasos que hoy **no están cubiertos** por el único mecanismo de concurrencia confirmado en el proyecto (optimistic locking por `version` a nivel de `CanvasORM`, usado en CU4):

- **Paso 3** — *"El sistema identifica la unidad mínima que debe controlarse concurrentemente."* El `version` actual es a nivel de lienzo completo, no de recurso individual. Dos usuarios editando clases distintas del mismo lienzo generarían un `409 VERSION_CONFLICT` innecesario — un falso conflicto, porque no tocaron lo mismo.
- **Paso 4** — *"Reserva o controla únicamente el recurso afectado cuando sea necesario."* Esto implica un mecanismo de bloqueo (lock) granular por elemento, que hoy no existe.
- **Excepción** — *"Ante pérdida de conexión, libera cualquier reserva temporal."* Requiere que los locks tengan expiración automática, no dependan de un `unlock` explícito que puede no llegar a ejecutarse.

La regla de pragmatismo ya definida para el proyecto anticipó esto: el módulo `collaboration` es el único, junto con `assistant`, donde se justifica un puerto formal (`LockStore`) porque hay variabilidad real de infraestructura esperada (Redis hoy, posible cambio si escala).

## Decisión

**Modelo híbrido: lock pesimista granular por recurso (soft lock, con expiración) + optimistic locking de lienzo como red de seguridad.**

### 1. Unidad mínima de control concurrente (resuelve Paso 3)

El recurso que se bloquea es el **elemento individual** que se está editando activamente — una clase, una relación — identificado por su `id` de dominio. No se bloquea el lienzo completo.

```
recurso_lock_key = f"canvas:{canvas_id}:element:{element_id}"
```

### 2. Adquisición y liberación (resuelve Pasos 4 y 11, y la Excepción)

- Al iniciar una edición interactiva de un elemento (ej. el usuario abre el panel de propiedades de una clase, o empieza a arrastrar un vértice de relación), el cliente solicita el lock vía WebSocket.
- El `LockStore` (Redis) otorga el lock con **TTL corto** (ej. 15-30 segundos; **fijado en 15 s por el Addendum**) y el cliente debe renovarlo con un heartbeat mientras sigue editando.
- Si el cliente se desconecta (cierra pestaña, pierde red), no llega el próximo heartbeat, el TTL expira, y **el lock se libera automáticamente** — sin necesidad de un `unlock` explícito ni de detectar la desconexión activamente. Esto resuelve la excepción de pérdida de conexión de forma simple, sin lógica adicional de limpieza.
- Al terminar la edición (guardar o cancelar), el cliente libera el lock explícitamente antes de que expire el TTL.

### 3. Qué pasa si el recurso ya está bloqueado

- El servidor rechaza la solicitud de lock con un código explícito (`423 Locked` o evento WebSocket equivalente), indicando qué usuario lo tiene.
- El cliente muestra al usuario que ese elemento está siendo editado por otra persona (ej. borde de color distinto, nombre del colaborador) — esto requiere el canal de presencia que ya se estaba pidiendo para el puntero del colaborador, y puede compartir la misma infraestructura de WebSocket.
- El usuario puede optar por esperar o editar otro elemento — no hay cola de espera automática en esta primera versión (evitar sobre-diseño).

### 4. La validación de la operación (Paso 6) y actualización del estado (Pasos 7-9)

Una vez adquirido el lock, la mutación real sigue el flujo que ya existe y está probado: pasa por el método explícito del dominio correspondiente (`editar_asociacion`, `agregar_clase`, etc.), que valida y devuelve el evento. El evento se persiste (incrementa el `version` del lienzo, manteniendo el optimistic lock como red de seguridad adicional) y se propaga por WebSocket a los demás participantes de la sala — mismo mecanismo que ya usan los comandos de CU1-CU4, extendido con el broadcast a otros clientes.

### 5. Puntero del colaborador (presencia en vivo)

Canal separado, **sin lock, sin persistencia**, de menor prioridad de entrega:
- Cada cliente emite su posición de cursor por WebSocket a intervalos cortos (ej. cada 50-100ms, sampleado — no cada movimiento de mouse).
- El servidor hace broadcast a los demás participantes de la misma sala/lienzo.
- No pasa por el dominio, no genera eventos de dominio, no se guarda en `PostgreSQL` — es estado efímero que vive solo mientras dura la conexión.
- Cada participante ve el cursor de los demás con un color/nombre distintivo, desde su propio punto de vista del canvas.

## Alternativas consideradas

| Alternativa | Por qué no |
|---|---|
| **Solo optimistic locking (lo que ya existe hoy)** | No cumple el Paso 3 de la ficha (unidad mínima de control) ni el Paso 4 (reserva del recurso). Generaría falsos conflictos entre usuarios editando cosas distintas del mismo lienzo. |
| **CRDTs (Yjs/Automerge)** | Máxima resiliencia a conflictos, pero complejidad de implementación alta para el tamaño del equipo (1-2 personas) y el tiempo disponible. Se descarta salvo que la experiencia con el lock pesimista muestre problemas serios. |
| **Lock pesimista duro (hasta que el usuario suelte manualmente, sin TTL)** | Un usuario que cierra la pestaña sin guardar dejaría el recurso bloqueado indefinidamente para los demás — viola directamente la excepción de la ficha sobre pérdida de conexión. Se descarta. |
| **Cola de espera automática por recurso bloqueado** | Agrega complejidad de UX y backend no pedida por la ficha ni necesaria para el alcance actual. Puede agregarse después si se necesita. |

## Consecuencias

**Positivas:**
- Cumple los 11 pasos del flujo de la ficha de forma directa, sin inventar comportamiento no especificado.
- Reutiliza el patrón de mutación por eventos de dominio ya construido para CU1-CU4 — no hay que rediseñar cómo se aplican los cambios, solo cuándo se permite iniciarlos.
- El TTL con heartbeat resuelve la recuperación ante desconexión sin lógica de limpieza activa ni jobs en background.
- El puntero de colaborador es aditivo y de bajo riesgo — no toca el dominio ni la persistencia, se puede implementar y probar de forma aislada del resto.
- Reduce la frecuencia del comportamiento agresivo confirmado hoy en `editor-command.service.ts`: ante cualquier `409 VERSION_CONFLICT`, el frontend limpia el historial local no confirmado y fuerza un `reloadSnapshot` completo — incluso cuando los dos usuarios editaron elementos distintos del mismo lienzo. Con lock granular por elemento, ese escenario deja de generar conflicto en primer lugar; el `version` de lienzo completo queda como red de seguridad para el caso real de colisión sobre el mismo recurso, no como el único mecanismo. **(Premisa corregida en el Addendum §6: el lock no evita el `409`; lo reduce que cada cliente aplique rápido los cambios ajenos.)**

**Negativas / mitigaciones:**
- Agrega Redis como dependencia de infraestructura activa (ya estaba anticipado en la regla de pragmatismo del proyecto, pero hay que levantarlo en `docker-compose` si no está corriendo aún).
- El heartbeat de renovación de lock agrega tráfico WebSocket adicional — mitigado con throttling razonable, no es un volumen alto para el tamaño de equipo esperado en la evaluación.
- Requiere manejar en el frontend el caso de "lock rechazado" con una UX clara (de quién es el lock) — trabajo de frontend no trivial, pero acotado.
- El `LockStore` es un puerto nuevo real (primera vez que `collaboration/` deja de estar vacío) — debe seguir el patrón de pragmatismo ya acordado: puerto mínimo, sin sobre-abstracción.

## Pendiente de decidir en este ADR (resuelto en el Addendum del 2026-09-20, salvo el lock por inactividad, que sigue abierto)

- TTL exacto del lock y frecuencia del heartbeat — valores de ejemplo arriba, no definitivos.
- Si el rechazo de lock se comunica por HTTP (`423`) o exclusivamente por WebSocket — depende de si la adquisición de lock viaja por REST o ya está integrada al canal de comandos existente.
- Si hace falta un timeout distinto para "lock por inactividad" (usuario tiene el panel abierto pero no interactúa) vs. "lock por desconexión real".


---

## Addendum (2026-09-20): decisiones de implementación de la Prioridad 2

**Estado:** Aprobado · **Decisor:** Theboul
**Alcance:** fija los parámetros que este ADR dejó abiertos, corrige una premisa y registra las
decisiones de transporte tomadas al implementar CU5. No cambia el modelo híbrido (lock pesimista
suave por elemento + versión optimista de Lienzo).

Vocabulario según `CONTEXT.md`: una **Sala** agrupa las **Sesiones** (conexiones) de un Lienzo.

### 1. Módulo y nombres

- El puerto del módulo se llama `CollaborationRoom` (una Sala por Lienzo) y entrega un handle
  `Session` por conexión. Se descarta el nombre `CollaborationSession`: por glosario, una Sesión es
  una conexión individual, no el grupo.
- El puerto `LockStore` de este ADR se mantiene (`.claude/rules/fastapi.md`).

### 2. Parámetros del lock

- **TTL: 15 s. Heartbeat: cada 5 s** (un tercio del TTL: tolera perder dos heartbeats seguidos).
  Renovar es repetir `acquire` desde la misma Sesión (idempotente).
- Sustituye los "15-30 s" de este ADR y los "10-15 s" de `.claude/rules/redis.md`, que quedan
  unificados en 15 s. Sigue vigente: nunca un lock sin TTL.

### 3. Rechazo de un lock

- Por WebSocket, no por HTTP 423: la adquisición ya viaja por WS. El servidor responde con un
  evento `lock_denied` que indica quién tiene el lock (usuario y nombre a mostrar). Sin cola de
  espera (sin cambios).

### 4. Claves de Redis

```text
lock:canvas:{canvasId}:element:{elementId}   # TTL 15 s, renovado con el heartbeat; valor: quién lo tiene
presence:canvas:{canvasId}:{sessionId}       # una clave por Sesión (no por usuario); TTL corto
```

- Se elimina la clave separada de heartbeat: renovar el TTL de la clave del lock ya cumple esa
  función.
- La presencia es por Sesión: un mismo Colaborador con dos pestañas abiertas tiene dos Sesiones.

### 5. Lock advisory por ahora

- El servidor lleva y difunde el estado de los locks y rechaza `acquire` sobre un elemento ya
  tomado, pero **no rechaza mutaciones HTTP** sobre un elemento bloqueado por otra Sesión. La
  integridad la garantiza la versión optimista (`expectedVersion`), como en CU3/CU4.
- La aplicación del lock en el servidor queda **diferida detrás de una bandera** (nombre por
  definir). Requiere mapear cada comando a los elementos que toca, y los payloads son
  heterogéneos.
- Unidad de lock: **Clase o Relación**. Editar un Atributo u Operación cuenta como tocar su Clase.
  Se solicita al abrir el panel de propiedades o al iniciar un arrastre.

### 6. Corrección de una premisa

- Este ADR decía que el lock granular elimina los `409 VERSION_CONFLICT` falsos. **No es así**: el
  `409` compara la versión del Lienzo completo y un lock no cambia esa comparación. Lo que reduce
  esos `409` es que cada cliente aplique con rapidez los cambios ajenos (para que su
  `expectedVersion` esté al día), y eso lo aporta el envío de deltas.
- Lo que el lock sí aporta: evitar que dos personas editen a la vez el mismo elemento y mostrar
  quién lo está editando.
- El **reintento automático tras un `409`** (traer los cambios y reaplicar los comandos que no se
  solapan, en vez de descartar el historial local y recargar) queda como **tarea diferida, fuera
  de la Prioridad 2**.

### 7. Decisiones de transporte

- **Publicar después del commit**, desde la capa de aplicación (no con un hook `after_commit`).
  Hasta ahora se publicaba dentro de la ruta HTTP, antes del commit. Si publicar falla tras el
  commit no hay rollback: se registra y el cliente repara por resync.
- **Handshake:** el servidor acepta el WebSocket y lo cierra con 4403 si el rol no basta, en vez de
  rechazar antes de `accept()`; así el cliente puede leer el código. Un socket sin permiso nunca
  entra a una Sala. Un token presentado pero inválido o vencido cierra con **4401** (decidido en el
  Paso 3): el access token dura 15 minutos y una reconexión tras una caída larga lleva uno
  caducado, así que el cliente lo renueva una vez y reintenta; el 4403 no se reintenta.
- **Reconexión** del cliente: backoff de 1 s a 30 s con jitter (1, 2, 4, 8, 16, 30, 30, 30 s), máximo
  de **8 reintentos** (≈ 1 a 2 minutos) y **10 s** de conexión establecida para considerarla estable
  y reiniciar el contador; sin reintentar tras un 4403; resync al reabrir. Tras agotar los
  reintentos hay un botón "Reintentar".
- **Deltas:** por diferencia entre el modelo antes y después del comando, en la capa de aplicación,
  sin tocar `core/uml_domain`. Llevan `fromVersion` y `toVersion`; si el cliente detecta un hueco
  pide un snapshot. Cambio directo, sin enviar snapshot y delta en paralelo. Los eventos de dominio
  actuales no bastan: `ElementoAgregado` no lleva los datos del elemento, `RelacionModificada` no
  lleva los cambios y los comandos de layout no emiten evento.
- **Redis:** fan-out entre workers por pub/sub y presencia con TTL; los sockets siguen viviendo en
  cada worker. Sin `REDIS_URL` se usa memoria (desarrollo). Con `REDIS_URL` definido y sin
  respuesta, la app **falla al arrancar** (mismo patrón que `JWT_SECRET`). Compose con 2 workers y
  `--ws-max-size 8192`.

### 8. Sigue abierto (se decide en el paso indicado)

- Lock por inactividad frente a lock por desconexión (tercer pendiente de este ADR): qué hace el
  cliente para dejar de enviar heartbeat cuando el usuario no interactúa (Paso 5).
- Formato del valor guardado en la clave del lock y nombres de los mensajes del protocolo de
  locks (Paso 5).
- TTL y renovación de la clave de presencia, y nombre del canal de pub/sub (Paso 6).
- Nombre de la bandera que activaría la aplicación del lock en el servidor (tarea diferida).
