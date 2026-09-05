# Estándares y Reglas del Proyecto — Diagramador UML (Examen 2)

**Estado del proyecto:** Migración Django → FastAPI completada. Este documento establece las reglas obligatorias para todo el código que se escriba de aquí en adelante.

---

## 0. Principios rectores

1. `core/uml_domain` es intocable en su aislamiento: no depende de ningún framework, y no se toca su estructura interna salvo que cambie una regla UML real.
2. La arquitectura sirve al equipo, no al revés. Con 1–2 personas, cada capa que se agrega debe pagar su costo en claridad — si no lo paga, no se agrega.
3. Todo lo externo (Gemini, JointJS, Spring, Flutter, Redis, PostgreSQL) es un adaptador. El dominio nunca lo importa directamente.
4. Ningún código nuevo entra sin: tipos, lint limpio, y al menos la prueba del comportamiento crítico que implementa.
5. Toda funcionalidad nueva debe poder trazarse a un CU del documento de Captura de Requisitos.

---

## 1. Arquitectura de software

**Modular Monolith + Ports & Adapters selectivo** (no Clean Architecture extrema, no microservicios).

```
Angular CASE (UI + JointJS adapter)
        │  HTTP / WebSocket
        ▼
FastAPI (backend_case) — capa de entrada
        │
Application Services (por módulo)
        │
core/uml_domain (dominio puro, sin dependencias)
        │
   ┌────┼─────────────┐
   ▼    ▼             ▼
PostgreSQL  Interoperabilidad  Generación (Spring / Flutter)
```

### Regla de dependencia (no negociable):
```
API → Application → Domain
Infrastructure → Application Ports (nunca al revés)
Domain → nada de lo anterior
```

---

## 2. Regla de pragmatismo: cuándo SÍ puertos/adaptadores, cuándo NO

Criterio rector: **¿Tengo hoy, o preveo con certeza razonable, una segunda implementación real de esto?**

| Módulo | ¿Puerto/adaptador? | Justificación |
|---|---|---|
| `modeling` | **No.** Service directo sobre `core/uml_domain` | El dominio ya está aislado en sí mismo; no hay infraestructura variable que proteger aquí |
| `collaboration` | **Sí**, mínimo (`LockStore`) | Redis hoy, candidato real a cambiar si escala |
| `assistant` | **Sí**, mínimo (`AiCommandInterpreter`) | Gemini hoy, modelo local es un cambio previsible |
| `interoperability` | **No, por ahora** | Un solo formato (XMI/EA); no crear la abstracción hasta que exista un segundo formato real (YAGNI) |
| `generation` | **Sí**, uno por generador | Spring Boot (CU10) y Postman (CU11) son dos salidas reales. El CASE NO genera cliente móvil (ADR-0007). |
| `legacy` (compatibilidad Angular) | **No** | Rutas planas, sin capas intermedias — es código de transición, no core |

Regla general para equipo de 1–2 personas: **si una función o una clase de servicio resuelve el problema, no se crean interfaces, mappers ni DTOs intermedios "por si acaso".** Se refactoriza a puerto el día que aparezca la segunda implementación real.

---

## 3. Arquitectura de carpetas — Backend (FastAPI)

```text
Diagramador_UML_Examen2/
│
├── backend_case/                  # FastAPI — único backend activo
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── shared/
│   │   │   ├── config/
│   │   │   ├── errors/            # taxonomía de excepciones de dominio
│   │   │   ├── logging/
│   │   │   └── security/          # auth (definir en ADR-0005)
│   │   │
│   │   ├── modeling/               # PA1 — sin ports, service directo
│   │   │   ├── api/
│   │   │   └── application/
│   │   │
│   │   ├── collaboration/          # PA2 — con LockStore port
│   │   │   ├── api/
│   │   │   ├── application/
│   │   │   │   └── ports/
│   │   │   └── infrastructure/
│   │   │
│   │   ├── assistant/              # PA3 — con AiCommandInterpreter port
│   │   │   ├── api/
│   │   │   ├── application/
│   │   │   │   └── ports/
│   │   │   └── infrastructure/
│   │   │
│   │   ├── interoperability/       # PA2/3 — plano por ahora
│   │   │   ├── api/
│   │   │   └── application/
│   │   │
│   │   ├── generation/             # PA3 — un port por generador
│   │   │   ├── api/
│   │   │   ├── application/
│   │   │   │   └── ports/
│   │   │   └── infrastructure/
│   │   │       ├── spring/
│   │   │       └── postman/
│   │   │
│   │   └── legacy/                 # compatibilidad Angular, plano
│   │       ├── api_router.py
│   │       └── ws_router.py
│   │
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
│
├── core/
│   └── uml_domain/                 # librería interna, sin frameworks
│
├── contracts/                      # fuente de verdad de intercambio de datos
│   ├── uml-model.v2.json
│   ├── collaboration-events.v1.json
│   └── generation-request.v1.json
│
├── back_generator_uml/             # generador Spring + Postman
├── mobile_app_reference/           # Contexto B / PA4 (scaffolding Flutter offline-first para evaluación, ADR-0007)
├── tests/                          # cross-system / caracterización
├── docs/
│   ├── architecture/adr/
│   └── traceability/
└── infra/
```

---

## 4. Arquitectura de carpetas — Frontend (Angular)

```text
front_generador_bd/src/app/
│
├── core/
│   ├── config/
│   ├── http/                       # cliente HTTP común, apunta a FastAPI :8000
│   ├── errors/
│   └── websocket/
│
├── shared/                         # solo piezas que NO conocen el negocio
│   ├── components/                 # ConfirmDialog, LoadingIndicator, Modal...
│   ├── directives/
│   └── pipes/
│
└── features/
    ├── modeling/
    │   ├── application/            # facades / application services
    │   ├── infrastructure/
    │   │   └── jointjs/            # JointJS vive aquí, no en domain
    │   └── ui/
    ├── collaboration/
    ├── assistant/
    ├── interoperability/
    └── generation/
```

- **Regla de shared:** Un componente entra a `shared/` solo si no conoce el negocio y lo reutilizan al menos dos features. `UmlClassEditor`, `RelationshipPanel`, `CollaborationPresence` NO van ahí.
- **Regla de flujo de datos:**
  `Component → Facade/Application Service → Gateway/Adapter → HttpClient`
  Nunca `Component → HttpClient` directo. Nunca lógica de negocio dentro de un componente JointJS.

---

## 5. Estándares de codificación — Python / FastAPI

- **Versión:** Python 3.12+
- **Formato y lint:** Ruff (reemplaza black + isort + flake8)
- **Tipos:** Mypy en modo estricto para `core/uml_domain` y `app/*/application`; type hints obligatorios en toda API pública.
- **Tests:** pytest

### Reglas de código:
- Prohibido `from x import *`.
- Prohibido `raise Exception("...")` genérico — usar excepciones de dominio explícitas.
- Prohibida lógica de negocio en routers (`api/routes.py` solo orquesta: recibe request → llama application service → devuelve response).
- Prohibido SQL directo en routers.
- Prohibido acceso directo a Gemini/APIs externas fuera de `infrastructure/`.
- Prohibidas variables globales mutables.
- Funciones largas (>~40 líneas) se dividen salvo justificación explícita en comentario.

### Taxonomía de errores de dominio:
```python
class UmlDomainError(Exception): ...
class UmlValidationError(UmlDomainError): ...
class UnsupportedGenerationFeature(UmlDomainError): ...
class CanvasNotFound(UmlDomainError): ...
class ConcurrentEditConflict(UmlDomainError): ...
```

---

### Regla del módulo `assistant` (CU6, CU7) — no negociable

El flujo de cualquier entrada procesada por IA (Gemini u otro modelo, texto, voz o imagen) es SIEMPRE:

```text
    Entrada del usuario
        ↓
    InterpretadorComandosModelado / AnalizadorDiagramaImagen
        ↓
    Salida cruda de la IA (ComandoModelado / PropuestaModelo)
        ↓
    ValidadorComandoModelado / ValidadorModelo   ← OBLIGATORIO, sin excepción
        ↓
    GestorElementosUML / GestorRelacionesUML     ← únicos que tocan ModeloUML
```

Reglas duras:
1. Ninguna función dentro de `app/assistant/` puede importar o llamar directamente a `GestorElementosUML`, `GestorRelacionesUML` ni a `core/uml_domain` sin pasar antes por el validador correspondiente. No existe bypass "temporal", "solo para debug" ni "solo en dev".
2. La salida de la IA se trata SIEMPRE como no confiable, igual que un input HTTP del usuario. Se valida:
   - Esquema/estructura (¿es un ComandoModelado bien formado?)
   - Referencias (¿los IDs de elementos/relaciones que menciona existen en el modelo actual?)
   - Reglas de negocio UML (multiplicidades, tipos válidos, ciclos no permitidos, etc. — las mismas que ya aplica `ValidadorModelo` para CU9)
3. Si la validación falla, el sistema responde con un error explícito al usuario (nunca aplica el cambio parcialmente ni "corrige" silenciosamente lo que la IA propuso).
4. Toda invocación a un modelo de IA pasa por el puerto `AiCommandInterpreter` (nunca se llama al SDK de Gemini directo desde un router o desde `application/`). Esto además es lo que permite cumplir la regla de pragmatismo ya definida (Gemini hoy, modelo local mañana, sin tocar el resto del módulo).
5. Test obligatorio antes de dar por cumplido el DoD de CU6/CU7: un caso donde la IA devuelve un comando/propuesta inválido (referencia a un elemento inexistente, tipo de relación no soportado, texto ambiguo) y se verifica que el modelo NO cambia y el error se propaga correctamente.

---


## 6. Estándares de codificación — TypeScript / Angular

- TypeScript en modo `strict`.
- ESLint + Prettier.
- Angular Style Guide oficial como base.
- Prohibido `any` salvo caso documentado con comentario `// any justificado: ...`; usar `unknown` cuando el tipo es real pero desconocido.
- Prohibido `HttpClient` inyectado directo en componentes — pasa siempre por facade/gateway.

---

## 7. Convenciones de API

- Todo endpoint nuevo bajo `/api/v2/...`. Los endpoints legacy (`/api/chatbot/`, `/api/set_backup_uml/`, `/ws/canvas/`, etc.) se mantienen intactos en `legacy/` sin tocar su contrato.
- Nombres de recursos en plural: `/api/v2/canvases`, `/api/v2/models`, `/api/v2/generation`, `/api/v2/interoperability`.
- Formato de error único para todo lo nuevo:
```json
{
  "code": "UML_INVALID_MODEL",
  "message": "The UML model contains validation errors.",
  "details": []
}
```

---

## 8. Estrategia de testing por capa

| Capa | Tipo de prueba |
|---|---|
| `core/uml_domain` | Unit tests (máxima cobertura de reglas UML puras) |
| Application services | Unit / service tests |
| Adaptadores (DB, Redis, Gemini) | Integration tests |
| HTTP / WebSocket | Contract / API tests |
| Angular + FastAPI integrados | E2E smoke tests |
| Generadores Spring / Flutter | Compilación + análisis estático del output generado |

**Meta real:** toda regla crítica tiene prueba — especialmente validación UML, conflicto de colaboración, mapeo XMI, generación, sync offline (cuando se resuelva el ADR-0004).

---

## 9. Proceso de ADR

Ubicación: `docs/architecture/adr/`. Formato: Context / Decision / Alternatives considered / Consequences.

| # | Título | Estado |
|---|---|---|
| 0001 | Modular monolith + FastAPI | Por transcribir |
| 0002 | `core/uml_domain` como librería aislada | Por transcribir |
| 0003 | Estrategia de colaboración concurrente (CU5) | **Pendiente — bloquea implementación de CU5** |
| 0004 | Estrategia de sync offline (CU13) | **Pendiente — CU13 congelado hasta resolverlo** |
| 0005 | Autenticación/autorización (Anfitrión vs. Colaborador) | **Pendiente — atraviesa CU2 y CU5** |
| 0006 | Formato de contratos versionados (JSON Schema) | Por transcribir |

---

## 10. Definition of Done (DoD)

- [ ] Trazable a un CU del documento de Captura de Requisitos
- [ ] Implementación respeta la regla de dependencias (sección 1)
- [ ] Tipos completos (Python/TS)
- [ ] Lint limpio (Ruff / ESLint)
- [ ] Type check limpio (Mypy / tsc strict)
- [ ] Unit tests de la regla crítica
- [ ] Integration tests si toca un adaptador nuevo
- [ ] Documentado (docstring / comentario de decisión no obvia)
- [ ] Entrada agregada en la matriz de trazabilidad

---

## 11. Reglas para asistentes de IA en el IDE

1. Antes de generar código para un módulo, leer este documento y el ADR relevante si existe.
2. Ningún código generado se acepta si crea una carpeta o capa no contemplada en la sección 3/4 sin justificación explícita.
3. Ninguna lógica de negocio se genera dentro de un router, componente Angular o adaptador JointJS.
4. **Si una tarea requiere tocar `core/uml_domain`, se detiene y se pide confirmación explícita antes de modificar** — es la pieza más protegida del sistema.
5. Todo código generado debe pasar lint + type check antes de considerarse entregado.
6. **Toda salida generada por IA (Gemini/LLM) debe ser validada antes de tocar el dominio**: bajo ningún concepto se debe omitir la validación de esquema, referencias e integridad UML de lo propuesto por la IA.
