---
paths:
  - "backend_case/app/collaboration/**/*.py"
  - "**/*redis*.py"
---

# Redis — convenciones de SchemaCraft

> **Estado actual:** `redis>=5.0.0` está en `backend_case/requirements.txt` y `REDIS_URL` es
> variable opcional en `.env.example`, pero el módulo `collaboration` usa hoy un
> `room_registry.py` **en memoria** — el puerto `LockStore` (ver `.claude/rules/fastapi.md`,
> tabla de pragmatismo) todavía no tiene implementación real de Redis. Estas convenciones aplican
> **desde el primer PR** que toque Redis de verdad, no son retroactivas a lo que existe hoy.

## Naming de keys

Formato obligatorio: `{contexto}:{entidad}:{id}:{campo}`, siempre minúsculas, sin espacios.

```text
lock:element:{elementId}:owner          # sesión con el lock pesimista de un elemento (CU5)
lock:element:{elementId}:heartbeat      # timestamp del último heartbeat del lock
presence:canvas:{canvasId}:{userId}     # cursor/presencia de un colaborador en un canvas
session:ws:{connectionId}               # metadata de una conexión WebSocket, si se cachea
```

El `{contexto}` inicial (`lock`, `presence`, `session`, ...) identifica el subsistema y permite
`SCAN`/`KEYS` acotado por prefijo sin tocar otras keys.

## TTL

- Todo lock pesimista (`lock:element:*`) lleva TTL corto (10-15s) + heartbeat que lo renueva.
  **Nunca** un lock sin TTL (ver ADR-0003, estrategia de colaboración CU5). Si el heartbeat deja
  de llegar, el lock expira solo.
- Toda key de `presence:*` lleva TTL igualmente corto y se re-escribe en cada evento de presencia;
  no se persiste presencia indefinidamente.
- Nada en Redis es fuente de verdad durable — es cache/estado efímero de colaboración en tiempo
  real. El estado durable del modelo UML vive en PostgreSQL/SQLite vía `core/uml_domain`.

## Capa que puede tocar el cliente Redis

Solo `infrastructure/` (igual que cualquier otro adaptador). El cliente Redis se inyecta detrás
del puerto `LockStore` (`app/collaboration/application/ports/`); ningún router (`api/`) ni
`application/` importa `redis`/`redis.asyncio` directamente. Esto es lo que permite cumplir la
regla de pragmatismo: Redis hoy, otro almacén distribuido mañana, sin tocar el resto del módulo.
