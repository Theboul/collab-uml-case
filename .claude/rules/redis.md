---
paths:
  - "backend_case/app/collaboration/**/*.py"
  - "**/*redis*.py"
---

# Redis — convenciones de SchemaCraft

> **Estado actual:** `redis>=5.0.0` está en `backend_case/requirements.txt` y `REDIS_URL` es
> variable opcional en `.env.example`, pero el módulo `collaboration` usa hoy un registro de salas
> **en memoria** — el puerto `LockStore` (ver `.claude/rules/fastapi.md`, tabla de pragmatismo)
> todavía no tiene implementación real de Redis. Los parámetros y decisiones de la Prioridad 2
> (TTL, claves, arranque) están en el **Addendum del 2026-09-20 del ADR-0003**; este archivo los
> refleja. Estas convenciones aplican **desde el primer PR** que toque Redis de verdad, no son
> retroactivas a lo que existe hoy.

## Naming de keys

Formato obligatorio: `{contexto}:{entidad}:{id}[:{subentidad}:{id}][:{campo}]`, siempre
minúsculas, sin espacios.

```text
lock:canvas:{canvasId}:element:{elementId}   # lock pesimista de una Clase o Relación (CU5); valor: quién lo tiene
presence:canvas:{canvasId}:{sessionId}       # presencia de una Sesión (conexión) en un Lienzo
session:ws:{connectionId}                    # metadata de una conexión WebSocket, si se cachea
```

- No hay clave de heartbeat aparte: renovar el TTL de la clave del lock ya cumple esa función.
- La presencia es por **Sesión**, no por usuario: un Colaborador con dos pestañas abiertas tiene
  dos claves (vocabulario en `CONTEXT.md`).

El `{contexto}` inicial (`lock`, `presence`, `session`, ...) identifica el subsistema y permite
`SCAN`/`KEYS` acotado por prefijo sin tocar otras keys.

## TTL

- Todo lock pesimista (`lock:*`) lleva TTL de **15 s** + heartbeat cada **5 s** que lo renueva
  (repetir `acquire` desde la misma Sesión). **Nunca** un lock sin TTL (ver ADR-0003 y su
  Addendum). Si el heartbeat deja de llegar, el lock expira solo.
- Toda key de `presence:*` lleva TTL igualmente corto y se renueva mientras la Sesión siga viva;
  no se persiste presencia indefinidamente. (El valor exacto del TTL de presencia se fija en el
  Paso 6 de la Prioridad 2.)
- Nada en Redis es fuente de verdad durable — es cache/estado efímero de colaboración en tiempo
  real. El estado durable del modelo UML vive en PostgreSQL/SQLite vía `core/uml_domain`.

## Capa que puede tocar el cliente Redis

Solo `infrastructure/` (igual que cualquier otro adaptador). El cliente Redis se inyecta detrás
de los puertos `LockStore` y `CollaborationRoom` (`app/collaboration/application/ports/`): el
fan-out por pub/sub y la presencia viven en el adaptador Redis de `CollaborationRoom`. Ningún
router (`api/`) ni `application/` importa `redis`/`redis.asyncio` directamente. Esto es lo que
permite cumplir la regla de pragmatismo: Redis hoy, otro almacén distribuido mañana, sin tocar el
resto del módulo.

## Arranque

- Sin `REDIS_URL`: adaptadores en memoria (desarrollo y tests).
- Con `REDIS_URL` definido pero sin respuesta: la app **falla al arrancar**, igual que con un
  `JWT_SECRET` ausente. Nunca degradar en silencio a memoria si `REDIS_URL` está definido: con
  varios workers eso dividiría las Salas sin que nadie lo note.
