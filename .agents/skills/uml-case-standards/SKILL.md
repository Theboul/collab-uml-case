---
name: uml-case-standards
description: >-
  Standards, architecture guidelines, folder conventions, and Definition of Done
  for developing the Diagramador UML (Examen 2) CASE tool.
  Use whenever implementing, modifying, refactoring, or reviewing code in backend_case,
  front_generador_bd, or core/uml_domain.
---

# Diagramador UML CASE — Estándares y Flujo de Desarrollo

Esta skill guía el desarrollo de nuevas funcionalidades en el proyecto siguiendo la arquitectura acordada de **Modular Monolith con Ports & Adapters selectivo** y el principio de pragmatismo para equipos de 1–2 personas.

---

## 1. Verificación Inicial Obligatoria

Antes de escribir cualquier línea de código o crear nuevos archivos:
1. **Identificar el Caso de Uso (CU)**: La funcionalidad debe estar asociada a un CU del documento de Captura de Requisitos.
2. **Consultar ADRs existentes**: Revisar `docs/architecture/adr/`. Si la tarea toca colaboración concurrente (CU5), sync offline (CU13) o auth (CU2), comprobar si su ADR está aprobado. Si no lo está, **no implementar la funcionalidad hasta resolver el ADR**.
3. **Regla de oro sobre `core/uml_domain`**:
   > `core/uml_domain` es intocable en su aislamiento. No importa FastAPI, SQLAlchemy, Pydantic ni ningún framework externo. Si una tarea parece requerir modificarlo, detenerse y solicitar confirmación explícita al usuario.

---

## 2. Aplicar la Regla de Pragmatismo (Cuándo Ports y Cuándo NO)

> **Criterio rector:** ¿Existe hoy, o se prevé con certeza razonable, una **segunda implementación real** de este componente?

- **`modeling` (CU1–CU4)**: **Sin ports.** Service directo consumiendo `core/uml_domain`.
- **`collaboration` (CU5)**: **Sí, puerto mínimo (`LockStore`)**. Hoy Redis, mañana escalable.
- **`assistant` (CU6–CU8)**: **Sí, puerto mínimo (`AiCommandInterpreter`)**. Hoy Gemini, mañana LLM local.
- **`interoperability` (CU9–CU10)**: **Sin ports por ahora.** Solo un formato inicial (XMI/Enterprise Architect).
- **`generation` (CU10–CU11)**: **Sí, un port por generador.** Spring Boot 3 (CU10) y Postman v2.1 (CU11) son dos implementaciones reales. El CASE NO genera cliente móvil (ADR-0007).
- **`legacy` (compatibilidad Angular)**: **Sin ports.** Controladores y WebSockets planos para soportar la transición.

*Regla:* Si una función o una clase de servicio resuelve el problema, **no crear interfaces, mappers ni DTOs intermedios innecesarios**.

---

## 3. Reglas de Implementación en Backend (`backend_case`)

### A. Ubicación por módulo funcional
- `app/modeling/`: `api/` (routers FastAPI) y `application/` (servicios de canvas y diagramas).
- `app/collaboration/`: `api/`, `application/ports/`, `infrastructure/`.
- `app/assistant/`: `api/`, `application/ports/`, `infrastructure/`.
- `app/generation/`: `api/`, `application/ports/`, `infrastructure/spring/`, `infrastructure/postman/`.
- `app/legacy/`: compatibilidad transitoria con frontend Angular (`/api/chatbot/`, `/api/set_backup_uml/`, etc.).

### B. Prohibiciones estrictas de código
- ❌ Prohibido `from x import *`.
- ❌ Prohibido `raise Exception(...)` genérico; usar la taxonomía en `app/shared/errors/` (`UmlValidationError`, `CanvasNotFound`, etc.).
- ❌ Prohibida lógica de negocio en routers (`api/`). El router solo valida DTOs de entrada, llama al application service y devuelve la respuesta.
- ❌ Prohibido ejecutar consultas SQL o acceder al ORM dentro de los routers.
- ❌ Prohibido llamar a APIs externas (Gemini, Redis, servicios remotos) fuera de `infrastructure/`.
- ❌ Prohibidas variables globales mutables.
- ❌ Prohibido que funciones superen ~40 líneas sin justificación documentada.

### C. Convención de API REST
- Endpoints nuevos: siempre bajo `/api/v2/...` con nombres de recursos en plural (ej. `/api/v2/canvases`).
- Endpoints legacy: preservados bajo `/api/...` y `/ws/...` sin alterar sus contratos.
- Formato de error estructurado:
  ```json
  {
    "code": "UML_INVALID_MODEL",
    "message": "The UML model contains validation errors.",
    "details": []
  }
  ```

---

## 4. Reglas de Implementación en Frontend (`front_generador_bd`)

- **Modo estricto**: TypeScript en `strict: true`. Prohibido `any` no documentado.
- **Flujo de datos unidireccional**:
  `Component → Facade/Application Service → Gateway/Adapter → HttpClient`
  Nunca inyectar `HttpClient` directamente en un componente de UI.
- **Aislamiento de JointJS**: Todo el código gráfico de JointJS debe vivir encapsulado en adaptadores de infraestructura (`features/modeling/infrastructure/jointjs/`), nunca contaminando la lógica de negocio ni componentes compartidos.
- **Criterio para `shared/`**: Solo entran componentes agnósticos al negocio reutilizados por al menos 2 features (ej. `ConfirmDialog`, `LoadingIndicator`).

---

## 5. Regla No Negociable del Módulo `assistant` (CU6, CU7)

> **Toda salida de IA es tratada como NO CONFIABLE y DEBE pasar por validación antes de tocar el dominio.**

Flujo estricto obligatorio:
```text
Entrada del usuario
    ↓
InterpretadorComandosModelado / AnalizadorDiagramaImagen
    ↓
Salida cruda de la IA (ComandoModelado / PropuestaModelo)
    ↓
ValidadorComandoModelado / ValidadorModelo   ← OBLIGATORIO, sin excepción
    ↓
GestorElementosUML / GestorRelacionesUML     ← únicos autorizados a modificar el modelo
```

**Checklist previo a tocar `app/assistant/`:**
- [ ] No existen llamadas directas desde `app/assistant/` hacia `GestorElementosUML`, `GestorRelacionesUML` ni `core/uml_domain` sin pasar por el validador.
- [ ] Se valida esquema, referencias a IDs existentes y reglas UML (ciclos, multiplicidades).
- [ ] Toda invocación a Gemini o modelo externo pasa a través del puerto `AiCommandInterpreter`.
- [ ] Ante falla de validación, se responde con error explícito sin aplicar cambios parciales ni correcciones silenciosas.
- [ ] Existe prueba automatizada donde la IA retorna un comando inválido (referencia rota, relación no soportada) y se verifica que el modelo **no cambia**.

---

## 6. Checklist de Definition of Done (DoD)

Para dar por terminada cualquier tarea:

1. [ ] **Trazabilidad**: Asociada a un Caso de Uso oficial.
2. [ ] **Dependencias**: Respeta `API → Application → Domain`.
3. [ ] **Tipado**: Type hints completos en Python y types estrictos en TypeScript.
4. [ ] **Linting**: Código formateado y limpio con Ruff (Python) / ESLint (TS).
5. [ ] **Pruebas**:
   - Prueba unitaria del comportamiento crítico (ej. reglas de validación UML).
   - Prueba de integración si interactúa con adaptadores (PostgreSQL, Redis, Gemini).
   - Si toca `assistant` (CU6/CU7): prueba donde la salida de la IA es inválida y se confirma que no muta el modelo.
   - Prueba de API/contrato HTTP si expone un endpoint nuevo.
6. [ ] **Validación de Tamaño y Modularidad (RULE-CODE-QUALITY)**:
   - Ningún archivo fuente supera 1000 líneas.
   - Archivos >= 800 líneas revisados o refactorizados preventivamente.
   - Ejecutar: `python scripts/check-file-size.py`.
7. [ ] **Ejecución de regresión**: Ejecutar suite completa de pruebas:
   ```bash
   python -m pytest
   node --test tests/frontend/test_legacy_frontend_export.mjs
   ```
8. [ ] **Documentación**: Docstring explicativo en código y actualización de la matriz de trazabilidad en `docs/traceability/matriz.md`.

---

## 7. RULE-CODE-QUALITY — Modularidad y Límites de Tamaño

* **Límite Absoluto**: 1000 líneas por archivo fuente. Fallo bloqueante.
* **Límite Preventivo**: 800 líneas por archivo fuente. Refactor obligatorio antes de agregar nueva funcionalidad.
* **Funciones**: <= 30 líneas ideal, > 60 líneas revisar, > 100 líneas refactor obligatorio.
* **Prohibición de God Objects**: Descomponer fachadas y servicios masivos en servicios especializados cohesivos.
* **Cero Duplicación**: Reutilizar mappers, constantes, validadores y contratos existentes.
* **Pipeline de Validación Obligatorio**:
  1. `python scripts/check-file-size.py`
  2. Linter (`ruff` / `eslint`)
  3. Tests (`pytest`)
  4. Build (`npm run build`)


