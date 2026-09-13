---
paths:
  - "**/*.java"
---

# Spring Boot (`back_generator_uml/`) — convenciones de SchemaCraft

`back_generator_uml/` es el generador Spring Boot 3 (Java/Maven) que produce backend + colección
Postman a partir de un modelo UML (CU10/CU11). Es código real y activo, pero **todavía no tiene
linter instalado** — se deja lista la convención para el día que el volumen de código Java lo
justifique; no se instala Checkstyle/SpotBugs de forma especulativa (YAGNI, mismo principio de
pragmatismo del resto del repo).

## Estructura por capas (a respetar en código nuevo aunque aún no haya lint que lo fuerce)

```text
back_generator_uml/src/main/java/.../
├── controller/     # REST endpoints — solo orquestan request/response
├── service/        # lógica de generación (Spring/Postman)
├── repository/     # solo si aplica persistencia propia del generador
├── model/          # entidades/dominio del generador
├── dto/             # contratos de entrada/salida
└── config/          # configuración de Spring (beans, CORS, etc.)
```

Misma regla que el resto del repo: **nada de lógica de negocio en `controller/`**.

## Herramienta de lint elegida (a instalar cuando haya código Java real que lintear)

**Checkstyle**, no SpotBugs, porque el objetivo principal aquí es consistencia de
estilo/convención — el mismo rol que Ruff/ESLint cumplen en los otros dos stacks — no análisis de
bugs a nivel bytecode. Si en el futuro aparecen bugs de concurrencia/nulidad recurrentes en el
generador, se puede sumar SpotBugs como complemento, no como reemplazo.

Al instalarlo:
1. `checkstyle.xml` en `back_generator_uml/`.
2. Plugin `maven-checkstyle-plugin` en `pom.xml`.
3. Target `mvn checkstyle:check` agregado a la cadena de validación del repo (junto a
   `python scripts/check-file-size.py`, Ruff/Mypy y ESLint/Prettier — ver `CLAUDE.md`).

El generador produce backend Spring Boot **y** colecciones Postman v2.1 (dos salidas reales), por
eso en `backend_case` el módulo `generation` tiene un puerto por generador — ver
`.claude/rules/fastapi.md`. El CASE **no** genera cliente móvil (`mobile_app_reference/` es solo
scaffolding de referencia para evaluación, ver ADR-0007).
