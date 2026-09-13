---
paths:
  - "backend_case/**/*.py"
  - "core/uml_domain/**/*.py"
---

# FastAPI / core.uml_domain — reglas de SchemaCraft (backend_case)

## Tooling

Config: `pyproject.toml` (raíz del repo) — `[tool.ruff]` y `[tool.mypy]`.

```bash
python -m ruff check backend_case/app backend_case/tests core
python -m ruff format backend_case/app backend_case/tests core          # aplica
python -m ruff format --check backend_case/app backend_case/tests core  # solo verifica
python -m mypy backend_case/app core/uml_domain
python -m pytest backend_case/tests/ -v
```

- Reglas Ruff activas: `E/F/W`, `I` (orden imports), `UP` (pyupgrade), `B` (bugbear), `C4`
  (comprehensions), `SIM`, `N` (pep8-naming, con `N815` ignorado a propósito — los DTOs Pydantic
  usan camelCase intencional para reflejar `contracts/uml-model.v2.json` y el JSON legado), `RUF`,
  y `TRY002` (bloquea `raise Exception("...")` genérico).
- Mypy en **modo estricto** (`strict = true`) sobre `core/uml_domain/*` y `app/*/application/*`
  (casos de uso). El resto exige tipos (`disallow_untyped_defs`) sin el resto de flags estrictos;
  `app/legacy/*` queda eximido por ser código de compatibilidad congelado.

## Principios rectores

1. `core/uml_domain` es **intocable en su aislamiento**: nunca importa FastAPI, SQLAlchemy,
   Pydantic ni ningún framework. **Si una tarea parece requerir modificarlo, detente y pide
   confirmación explícita del usuario antes de tocarlo** — es la pieza más protegida del sistema.
2. Todo lo externo (Gemini, Redis, PostgreSQL, Spring, Flutter) es un adaptador; el dominio nunca
   lo importa directamente.
3. Ningún código nuevo entra sin tipos, lint limpio, y al menos una prueba del comportamiento
   crítico que implementa.
4. Toda funcionalidad debe trazarse a un CU del documento de Captura de Requisitos
   (`docs/traceability/requirements-matrix.md`).

## Regla de dependencia (no negociable)

```text
API (routers) → Application (services/use cases) → Domain (core/uml_domain)
Infrastructure → implementa Application Ports (nunca al revés)
Domain → no depende de nada de lo anterior
```

## Regla de pragmatismo: ¿puertos/adaptadores sí o no?

Criterio rector: **¿tengo hoy, o preveo con certeza razonable, una segunda implementación real?**

| Módulo | ¿Puerto/adaptador? | Por qué |
|---|---|---|
| `modeling` | No — service directo sobre `core/uml_domain` | Dominio ya aislado; sin infra variable que proteger |
| `collaboration` | Sí, `LockStore` (Redis) — ver `.claude/rules/redis.md` | Redis hoy, candidato real a cambiar si escala |
| `assistant` | Sí, `AiCommandInterpreter` (Gemini) | Gemini hoy, modelo local es swap previsible |
| `interoperability` | No, por ahora | Un solo formato (XMI); YAGNI hasta que exista un segundo real |
| `generation` | Sí, un port por generador (Spring/Postman) | Dos salidas reales y distintas |
| `legacy` | No — rutas/WS planos | Código de transición para el Angular actual, no core |

Si una función o clase de servicio resuelve el problema, **no se crean interfaces/mappers/DTOs
intermedios "por si acaso"**. Se refactoriza a puerto el día que aparezca la segunda implementación real.

## Estructura de capas por módulo (`backend_case/app/<modulo>/`)

```text
api/              # routers — solo orquestan request → application service → response
application/      # casos de uso / servicios; aquí vive la lógica de negocio
application/ports/  # solo en collaboration/assistant/generation (ver tabla)
infrastructure/     # adaptadores: DB, Redis, Gemini, generadores externos
schemas/            # contratos Pydantic de entrada/salida
```

Handlers de comandos se desacoplan por entidad, nunca acumulados en un solo archivo:
```text
backend_case/app/modeling/application/commands/
├── dispatcher.py
├── class_handlers.py
├── attribute_handlers.py
├── operation_handlers.py
├── parameter_handlers.py
├── relation_handlers.py
└── layout_handlers.py
```

## Prohibiciones estrictas

- ❌ `from x import *`
- ❌ `raise Exception(...)` genérico — usar la taxonomía de `app/shared/errors/`
  (`UmlDomainError`, `UmlValidationError`, `CanvasNotFound`, `ConcurrentEditConflict`, ...)
- ❌ Lógica de negocio o SQL directo en routers (`api/`)
- ❌ Llamar APIs externas (Gemini, Redis) fuera de `infrastructure/`
- ❌ Variables globales mutables
- ❌ Inyectar una sesión de DB vía `Depends()` a nivel de un handler `@websocket` — queda abierta
  durante toda la vida de la conexión, no solo el instante de uso, y agota el pool con pocas
  conexiones WS concurrentes de larga duración (bug real encontrado en `collaboration/ws_router.py`).
  Usar una sesión manual de vida corta (`async with async_session_factory()`) acotada al momento
  exacto que la necesita.
- Funciones > ~40 líneas se dividen salvo justificación explícita en comentario

## Convención de API REST

- Endpoints nuevos siempre bajo `/api/v2/...`, recursos en plural (`/api/v2/canvases`).
- `app/legacy/` preserva los contratos Django-era intactos (`/api/chatbot/`, `/api/set_backup_uml/`,
  `/ws/canvas/`, ...) para que el Angular actual siga funcionando — no "limpiar" su forma de contrato.
- Formato de error único para todo lo nuevo:
  ```json
  { "code": "UML_INVALID_MODEL", "message": "...", "details": [] }
  ```

## Pipeline obligatorio de validación de IA — módulo `assistant` (CU6/CU7)

Toda entrada procesada por IA (Gemini u otro modelo; texto, voz o imagen) sigue SIEMPRE:

```text
Entrada del usuario
  → InterpretadorComandosModelado / AnalizadorDiagramaImagen
  → salida cruda de la IA (ComandoModelado / PropuestaModelo)
  → ValidadorComandoModelado / ValidadorModelo   ← OBLIGATORIO, sin excepción
  → GestorElementosUML / GestorRelacionesUML     ← únicos autorizados a tocar el modelo
```

1. Ninguna función en `app/assistant/` llama directo a `GestorElementosUML`,
   `GestorRelacionesUML` ni `core/uml_domain` sin pasar antes por el validador. Sin bypass
   "temporal", "solo debug" ni "solo dev".
2. La salida de la IA se trata SIEMPRE como no confiable (igual que un input HTTP): se valida
   esquema/estructura, que los IDs referenciados existan en el modelo actual, y reglas de negocio
   UML (multiplicidades, tipos válidos, ciclos no permitidos).
3. Si la validación falla, error explícito al usuario — nunca aplicar parcialmente ni "corregir"
   silenciosamente lo que la IA propuso.
4. Toda invocación a un modelo de IA pasa por el puerto `AiCommandInterpreter` — nunca se llama al
   SDK de Gemini directo desde un router o desde `application/`.
5. Test obligatorio: un caso donde la IA devuelve un comando/propuesta inválido (referencia rota,
   relación no soportada) y se verifica que el modelo **no cambia**.

## Contratos

`contracts/uml-model.v2.json` es la fuente de verdad del modelo UML compartida con el frontend y
`back_generator_uml`. Cambios ahí impactan los tres sistemas — revisar `docs/domain-model/` y el
ADR relevante antes de alterarlo.
