# Arnés de integración del canal de colaboración (Nivel B)

Verifica el canal de colaboración con un **navegador real** (Edge/Chrome headless vía Karma) contra
un **servidor real** (uvicorn), con un proxy TCP que se puede cortar y reponer. Cubre lo que los
tests con dobles no pueden: los códigos de cierre 4401/4403 tal como los ve el navegador, la
negociación del subprotocolo `bearer` y el backoff con temporizadores reales.

```bash
python scripts/collab-e2e/run.py
```

Requisitos: `node_modules` instalado en `front_generador_bd/`, y Edge o Chrome (si no se encuentran
en las rutas habituales, define `CHROME_BIN`).

## Qué hace

1. Levanta el backend con una base SQLite temporal (`:8939`) y siembra usuarios (dueño, ajeno,
   colaborador, un segundo colaborador `peer` que ningún test revoca), un Lienzo y un token
   vencido.
2. Arranca `harness.py`: un proxy TCP (`:8940`) delante del backend y una API de administración
   (`:8941`).
3. Ejecuta solo los specs `*.integration.spec.ts` del frontend
   (`collaboration-channel.integration.spec.ts`: canal, reconexión y códigos de cierre;
   `canvas-delta-sync.integration.spec.ts`: los cambios de otro usuario llegan como `canvas_delta`
   y el estado converge con el del servidor, incluido un hueco y un corte de red real). Las
   utilidades comunes están en `collaboration-integration.harness.spec.ts`.

Sin el arnés, esos specs quedan **pendientes** (no fallan) y `ng test` sigue verde.

## API de administración (GET, con CORS)

| Ruta | Efecto |
|---|---|
| `/config` | La configuración sembrada (tokens, ids) |
| `/cut` | Aborta las conexiones abiertas y rechaza las nuevas (el navegador ve 1006) |
| `/restore` | Repone el paso |
| `/stats` | Conexiones TCP aceptadas, rechazadas y abiertas |
| `/reset` | Pone a cero los contadores |
| `/revoke` | Borra la fila del Colaborador (simula que le retiran el acceso) |

## Qué NO cubre

- Una pestaña realmente en segundo plano (ahorro de temporizadores del navegador, suspensión del
  equipo). Un token vencido sí se reproduce, sin esperar 15 minutos.
- Un corte de red del sistema operativo. El proxy corta la conexión TCP, que para el navegador es
  equivalente en efecto (cierre 1006), pero no es el mismo mecanismo.
- El aspecto visual del indicador de conexión.
- Revocar el acceso a una Sesión ya abierta: no existe (el rol se calcula solo al conectar).
  `/revoke` solo permite verificar que la **siguiente** conexión recibe 4403.

## Reutilizarlo en otros pasos

Para un escenario nuevo basta un `it(...)` en el spec de integración que use `admin('/cut')`,
`admin('/restore')`, `stats()` y `realGateway(...)`. El agotamiento completo de reintentos
(~2 minutos reales) se cubre con reloj falso en `collaboration-gateway.service.spec.ts`, no aquí.
