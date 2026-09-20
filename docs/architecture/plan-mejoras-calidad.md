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

Implementar el `LockStore` del ADR-0003 detrás de una sola interfaz; sacar el broadcast de
`canvas_update` de las rutas HTTP; enviar deltas en vez del Lienzo completo; reconexión en el
gateway del frontend (hoy `WebSocketCollaborationGateway` no tiene `onclose` ni reconexión; un
cierre por violación de protocolo, o una caída de red, deja la colaboración muerta hasta recargar).
La reconexión no debe entrar en bucle ante un rechazo de handshake (403).

## Prioridad 3 — Retirar el legado y unificar vocabulario

Retirar el router legacy (`app/legacy/*`), la ruta `legacy-diagram/:roomId`, y
`front_generador_bd/src/services/diagram` (hoy excluida del gate de tamaño). Actualizar
`docs/traceability/requirements-matrix.md` (CU5 y CU12/CU13 están desactualizados). Aplicar el
glosario de `CONTEXT.md` en código, API y eventos.

---

# Tareas diferidas

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

## Autenticación (después de la Prioridad 1)

- **Endurecer el login con contraseña** (ADR-0005 mantiene ambos métodos):
  - Mínimo de contraseña: hoy 6 caracteres (`schemas.py`).
  - Límite de intentos y bloqueo de cuenta: hoy no existe.
  - Hasher a Argon2id: el ADR lo indica, pero el código usa PBKDF2-SHA256.

## Riesgos abiertos detectados en la revisión de código

- **El gateway no reconecta.** Mitigado parcialmente: los campos inválidos ya no cierran la Sesión
  (ver "Decisiones tomadas"), pero una violación de protocolo o una caída de red sigue dejando la
  colaboración muerta hasta recargar. La reconexión completa es Prioridad 2.
- **El rechazo del handshake no llega como código 4401/4403.** Con un servidor real, cerrar antes
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

- `docker-compose.app.yml` publica el puerto 8000 pero el Dockerfile del backend expone 8001, y la
  contraseña de PostgreSQL está escrita en el archivo.
