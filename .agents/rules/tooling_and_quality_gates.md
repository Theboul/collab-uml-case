# Tooling de calidad y convenciones de nombres — por stack

> Este documento complementa `standards.md` (arquitectura/prohibiciones), `code_quality.md`
> (tamaño de archivo/SRP) y `frontend_design_architecture.md` (design tokens/shell). No repite
> esas reglas: aquí solo se documenta **qué herramienta corre, dónde está configurada, y las
> convenciones de nombres** que esa herramienta hace cumplir automáticamente.

---

## 1. Angular / TypeScript — ESLint + Prettier

**Config:** `front_generador_bd/eslint.config.js` (flat config, `@angular-eslint` + `typescript-eslint`)
y `front_generador_bd/.prettierrc.json`.

```bash
cd front_generador_bd
pnpm install                 # primera vez / tras clonar
pnpm run lint                # eslint sobre src/**/*.{ts,html}
pnpm run lint:fix
pnpm run format:check        # prettier --check
pnpm run format               # prettier --write
```

### Convenciones de nombres (Angular Style Guide oficial + lo ya establecido en este repo)

| Tipo | Archivo | Clase | Selector |
|---|---|---|---|
| Componente | `nombre-feature.component.ts` | `NombreFeatureComponent` | `sc-nombre-feature` (kebab-case, prefijo `sc`) |
| Servicio | `nombre.service.ts` | `NombreService` | — |
| Facade (application) | `nombre.facade.ts` | `NombreFacade` | — |
| Gateway/Adapter (infra HTTP) | `nombre.gateway.ts` | `NombreGateway` | — |
| Guard | `nombre.guard.ts` | funcional (`CanActivateFn`), preferido sobre clase | — |
| Interceptor | `nombre.interceptor.ts` | funcional (`HttpInterceptorFn`), preferido sobre clase | — |
| Directiva | `nombre.directive.ts` | `NombreDirective` | `[scNombre]` (camelCase, prefijo `sc`) |
| Pipe | `nombre.pipe.ts` | `NombrePipe` | `scNombre` |
| Modelo/tipo de dominio | `nombre.model.ts` / `nombre.types.ts` | `interface`/`type` PascalCase | — |

**Prefijo `sc`:** obligatorio para todo componente/directiva **nuevo**. El prefijo `app-` que
todavía existe en `features/modeling` (canvas JointJS legado, ver CLAUDE.md) queda aceptado por
el linter solo ahí mientras dura la migración a X6 — no se usa en código nuevo, y no se debe
"corregir" masivamente sin que el usuario lo pida (no es un descuido, es transición documentada).

### Regla de aislamiento del motor de canvas (X6/JointJS)

`eslint.config.js` bloquea con `no-restricted-imports` cualquier `import` de `@antv/x6`,
`@antv/x6-plugin-*` o `jointjs` fuera de:
- `features/modeling/infrastructure/x6/` (nodos custom en `x6/nodes/`, servicios de
  sincronización del canvas como `*.service.ts` en esa misma carpeta)
- `features/modeling/infrastructure/jointjs/` (legado)

Si el linter marca un import de X6/JointJS fuera de esas carpetas, la corrección correcta es
mover la lógica a un adapter/servicio dentro de `infrastructure/x6/`, nunca deshabilitar la regla
inline.

### Otras reglas duras del linter
- `@typescript-eslint/no-explicit-any`: error (usar `unknown` + guard, o el comentario
  `// any justificado: ...` ya definido en `standards.md`).
- `no-restricted-imports` bloquea `HttpClient` importado en cualquier archivo — el flujo
  `Component → Facade → Gateway → HttpClient` ya definido en `standards.md` se hace cumplir
  automáticamente.

---

## 2. FastAPI / Python — Ruff + Mypy

**Config:** `pyproject.toml` (raíz del repo) — secciones `[tool.ruff]` y `[tool.mypy]`. Cubre
`backend_case/`, `core/` y `tests/`.

```bash
python -m ruff check backend_case/app backend_case/tests core
python -m ruff format backend_case/app backend_case/tests core     # aplica formato
python -m ruff format --check backend_case/app backend_case/tests core  # solo verifica
python -m mypy backend_case/app core/uml_domain
```

- Reglas activas: `E/F/W` (pycodestyle+pyflakes), `I` (orden de imports), `UP` (pyupgrade),
  `B` (bugbear), `C4` (comprehensions), `SIM` (simplify), `N` (pep8-naming), `RUF`, y `TRY002`
  (bloquea `raise Exception("...")` genérico — ya prohibido en `standards.md`).
- Mypy corre en **modo estricto** (`strict = true`) sobre `core/uml_domain/*` y sobre
  `app/*/application/*` (la capa de casos de uso), tal como exige `standards.md` sección 5.
  El resto del backend exige tipos (`disallow_untyped_defs`) pero sin el resto de flags
  estrictos; `app/legacy/*` queda eximido por ser código de compatibilidad congelado.
- No se han añadido reglas de complejidad ciclomática (`C90`) ni `ANN` por ahora — el límite de
  ~40 líneas por función y la prohibición de God Objects ya están cubiertos por `code_quality.md`
  y se revisan en code review, no por lint automático (para no generar ruido en 1-2 personas).

---

## 3. Redis — convenciones (para cuando `collaboration.LockStore` se implemente)

> **Estado actual:** `redis>=5.0.0` está en `backend_case/requirements.txt` y `REDIS_URL` es
> variable opcional en `.env.example`, pero el `collaboration` module usa hoy un
> `room_registry.py` en memoria — el puerto `LockStore` (Redis) descrito en `standards.md` §2
> todavía no tiene implementación. Estas convenciones aplican **desde el primer PR** que toque
> Redis de verdad.

### Naming de keys
Formato obligatorio: `{contexto}:{entidad}:{id}:{campo}`

```text
lock:element:{elementId}:owner          # sesión que tiene el lock pesimista de un elemento (CU5)
lock:element:{elementId}:heartbeat      # timestamp del último heartbeat del lock
presence:canvas:{canvasId}:{userId}     # cursor/presencia de un colaborador en un canvas
session:ws:{connectionId}               # metadata de una conexión WebSocket, si se cachea
```

- Namespacing siempre en minúsculas, separado por `:`, sin espacios.
- El `{contexto}` inicial (`lock`, `presence`, `session`, ...) identifica el subsistema — permite
  hacer `SCAN`/`KEYS` acotado por prefijo sin tocar otras keys.

### TTL
- Todo lock pesimista (`lock:element:*`) lleva TTL corto (segundos, ej. 10-15s) + heartbeat que
  lo renueva — nunca un lock sin TTL (ver ADR-0003, estrategia de colaboración CU5). Si el
  heartbeat deja de llegar, el lock expira solo.
- Toda key de `presence:*` lleva TTL igualmente corto (se re-escribe en cada evento de
  presencia); no se persiste presencia indefinidamente.
- Nada en Redis se trata como fuente de verdad durable — es cache/estado efímero de
  colaboración en tiempo real. El estado durable del modelo UML vive en PostgreSQL/SQLite vía
  `core/uml_domain`.

### Capa que puede tocar el cliente Redis
Igual que cualquier otro adaptador (`standards.md` §0.3): **solo `infrastructure/`**. El cliente
Redis se inyecta detrás del puerto `LockStore` (`app/collaboration/application/ports/`); ningún
router (`api/`) ni `application/` importa `redis`/`redis.asyncio` directamente. Esto es lo que
permite cumplir la regla de pragmatismo ya definida (Redis hoy, otro almacén distribuido mañana,
sin tocar el resto del módulo).

---

## 4. Spring Boot (`back_generator_uml/`) — preparado para cuando escale

El generador ya existe (Maven/Java, `back_generator_uml/`), pero **no se instala linter todavía**
— se deja la convención lista para el día que el volumen de código Java lo justifique.

### Estructura por capas (a respetar en código nuevo, aunque no haya lint que lo fuerce aún)
```text
back_generator_uml/src/main/java/.../
├── controller/     # REST endpoints — solo orquestan request/response
├── service/        # lógica de generación (Spring/Postman)
├── repository/     # si aplica persistencia propia del generador
├── model/          # entidades/dominio del generador
├── dto/            # contratos de entrada/salida
└── config/         # configuración de Spring (beans, CORS, etc.)
```
Misma regla que el resto del repo: **nada de lógica de negocio en `controller/`**.

### Herramienta de lint elegida (a instalar cuando haya código Java real que lintear)
- **Checkstyle** (no SpotBugs) — se elige Checkstyle porque el objetivo principal en este
  proyecto es consistencia de estilo/convención (equivalente a lo que Ruff/ESLint hacen en los
  otros dos stacks), no análisis de bugs a nivel bytecode. Si en el futuro aparecen bugs de
  concurrencia/nulidad recurrentes en el generador, se puede sumar SpotBugs como complemento,
  no como reemplazo.
- Al instalarlo: `checkstyle.xml` en `back_generator_uml/`, plugin `maven-checkstyle-plugin` en
  `pom.xml`, y un target `mvn checkstyle:check` que se agrega a este mismo documento y al
  Pipeline de Verificación de `code_quality.md` §13.

---

## 5. Pipeline de verificación completo (antes de cualquier commit)

Además de lo ya definido en `code_quality.md` §13, con las herramientas de este documento el
pipeline completo es:

```bash
# Tamaño de archivo (obligatorio, todo el repo)
python scripts/check-file-size.py

# Backend
python -m ruff check backend_case/app backend_case/tests core
python -m ruff format --check backend_case/app backend_case/tests core
python -m mypy backend_case/app core/uml_domain
python -m pytest

# Frontend
cd front_generador_bd
pnpm run lint
pnpm run format:check
ng build
```

`pre-commit install` (usando `.pre-commit-config.yaml` en la raíz) ejecuta automáticamente la
versión "solo lo que cambió" de este mismo pipeline en cada commit.
