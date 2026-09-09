# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**SchemaCraft / "Diagramador UML" (Examen 2)** — a collaborative UML CASE tool. Monorepo containing:

- `front_generador_bd/` — Angular 20 frontend (the active client). Standalone components, X6 (`@antv/x6`) as the canvas engine (JointJS is legacy/being phased out), Tailwind v4.
- `backend_case/` — FastAPI backend, the **only active backend** (a prior Django backend has been fully retired; do not recreate it).
- `core/uml_domain/` — framework-free Python domain library (pure UML metamodel + validation). Shared by `backend_case` and the legacy adapters.
- `back_generator_uml/` — Spring Boot 3 generator (Java/Maven) that produces backend code + Postman collections from a UML model.
- `contracts/` — canonical JSON Schema contracts (`uml-model.v2.json`) shared across frontend/backend/generator.
- `mobile_app_reference/` — Flutter scaffolding reference for evaluation only (the CASE tool itself does **not** generate a mobile client — see ADR-0007).
- `docs/architecture/adr/` — Architecture Decision Records; check these before touching collaboration (CU5), offline sync (CU13), or auth.
- `tests/` — cross-system / characterization tests (domain model, legacy Spring/Flutter/Postman generator output, legacy frontend export).

The project standards live in `AGENTS.md` (root) and `.agents/rules/*.md` / `.agents/skills/uml-case-standards/SKILL.md` — **read those before making architectural changes**; this file only summarizes what's needed to navigate and run things.

## Commands

### Backend (FastAPI, Python 3.12+, run from repo root)

```bash
# Run the dev server
python -m uvicorn backend_case.app.main:app --host 0.0.0.0 --port 8001 --reload

# Run backend tests only
python -m pytest backend_case/tests/ -v

# Run a single test file / test
python -m pytest backend_case/tests/test_canvases_commands.py -v
python -m pytest backend_case/tests/test_canvases_commands.py::test_name -v

# Run the entire repo suite (domain + legacy generator characterization + FastAPI)
python -m pytest

# Lint
python -m ruff check backend_case/app backend_case/tests
```

Notes:
- `pytest.ini` (root) sets `testpaths = tests backend_case/tests` and puts both the repo root and `backend_case/` on `pythonpath`, so pytest is normally invoked from the repo root, not from inside `backend_case/`.
- Default DB is local SQLite via `aiosqlite` (`shared_case.db` for the new backend, `legacy_uml.db` for the legacy tables); set `DATABASE_URL` (see `backend_case/.env.example`) to point at PostgreSQL instead. `POSTGRES_HOST`/`REDIS_URL` are only relevant when running via `docker-compose.app.yml`/`docker-compose.db.yml`.
- Auth requires `GOOGLE_CLIENT_ID` and `JWT_SECRET` (see `backend_case/.env.example`); Google OAuth is the only login method.

### Frontend (Angular 20, package manager: pnpm)

```bash
cd front_generador_bd
ng serve            # dev server on :4200
ng build             # production build
ng test              # Karma unit tests
```

### Repo-wide code-quality gate (required before considering any task done)

```bash
python scripts/check-file-size.py     # fails (exit 1) if any .py/.ts/.html/.css/.scss file >= 1000 lines; warns at >= 800
```

This is enforced project policy (`.agents/rules/code_quality.md`), not optional tooling — run it after any nontrivial change alongside the linters/tests above.

## Architecture

### Layering (non-negotiable dependency rule)

```
API (routers) → Application (services/use cases) → Domain (core/uml_domain)
Infrastructure → implements Application Ports (never the reverse)
Domain → depends on nothing above it
```

`core/uml_domain` is pure Python: **never** import FastAPI, SQLAlchemy, Pydantic, or any framework into it. It is the most protected part of the system — if a task seems to require modifying it, stop and get explicit user confirmation first rather than proceeding.

### Backend module layout (`backend_case/app/`)

Each functional module (`modeling`, `collaboration`, `assistant`, `interoperability`, `generation`) follows `api/` (routers — orchestration only, no business logic or SQL), `application/` (services/use cases), and, only where justified, `application/ports/` + `infrastructure/`. A **pragmatism rule** decides whether a module gets ports/adapters at all — don't add them speculatively:

| Module | Ports/adapters? | Why |
|---|---|---|
| `modeling` | No — direct service over `core/uml_domain` | Domain is already isolated; no variable infra to protect |
| `collaboration` | Yes, `LockStore` port | Redis today, a real candidate to change |
| `assistant` | Yes, `AiCommandInterpreter` port | Gemini today, local model is a realistic future swap |
| `interoperability` | No (yet) | Single format (XMI); YAGNI until a second format is real |
| `generation` | Yes, one port per generator | Spring Boot and Postman are two real, distinct outputs |
| `legacy` | No | Flat compat routes/WebSockets for the Angular client during transition, not core code |

`app/legacy/` preserves the old Django-era HTTP/WebSocket contracts untouched (`/api/chatbot/`, `/api/set_backup_uml/`, `/ws/canvas/`, etc.) so the existing frontend keeps working during migration — don't "clean up" its contract shape. New endpoints always go under `/api/v2/...` with plural resource names, and use the structured error shape:
```json
{ "code": "UML_INVALID_MODEL", "message": "...", "details": [] }
```
Domain errors are a real exception taxonomy (`UmlDomainError`, `UmlValidationError`, `CanvasNotFound`, `ConcurrentEditConflict`, ...) in `app/shared/errors/` — never `raise Exception(...)`.

### The `assistant` module's mandatory AI-output validation pipeline (CU6/CU7)

Any AI-derived input (Gemini or otherwise; text, voice, or image) **must** flow through this pipeline with no bypass, ever (not even "for debug"):

```
User input → InterpretadorComandosModelado / AnalizadorDiagramaImagen
           → raw AI output (ComandoModelado / PropuestaModelo)
           → ValidadorComandoModelado / ValidadorModelo   ← mandatory, no exceptions
           → GestorElementosUML / GestorRelacionesUML     ← only things allowed to touch the UML model
```
AI output is treated exactly like untrusted HTTP input: validate schema/structure, validate that referenced element/relation IDs actually exist in the current model, and validate UML business rules (multiplicities, valid types, disallowed cycles). On validation failure, respond with an explicit error — never partially apply or silently "correct" what the AI proposed. All model calls go through the `AiCommandInterpreter` port; nothing calls the Gemini SDK directly from a router or from `application/`.

### Frontend architecture (`front_generador_bd/src/app/`)

```
core/      # singleton services, guards, interceptors — no UI
layout/    # AppShellComponent (login/dashboard, no project sidebar) and
           # ProjectShellComponent (single sidebar + toolbar shared by every
           # in-project view: canvas, SQL editor, tables, relationships, etc.)
shared/ui/ # presentational-only components (sc-button, sc-badge, sc-data-type-tag,
           # sc-table-card, sc-modal-shell, sc-icon, ...) — no HttpClient, no business logic
features/  # modeling, collaboration, assistant, interoperability, generation
           # each split into application/ (facades), infrastructure/ (x6 adapters,
           # gateways), ui/ (smart components)
```

Rules that matter when adding to this tree:
- Data flow is always `Component → Facade/Application Service → Gateway/Adapter → HttpClient`. Components never inject `HttpClient` directly.
- All canvas rendering code (AntV X6, and any remaining JointJS) is confined to `features/modeling/infrastructure/x6/` (or `.../jointjs/`) — never leaks into facades or shared UI.
- Every view inside an opened project uses `ProjectShellComponent`; every view outside one (login, dashboard) uses `AppShellComponent`. If it's unclear which one a new view belongs to, that's a sign the view isn't ready to build yet.
- Before adding a new button/badge/tag/card, check `shared/ui` first — copy-pasted markup for these is explicitly disallowed.
- All components are `standalone: true`; no per-feature NgModules.
- Styling uses semantic design tokens only (`bg-primary`, `text-on-primary-container`, the `gutter-*`/`toolbar-height`/`sidebar-width` spacing scale, `font-headline-*`/`font-body-*`/`font-code-*`) — never hardcoded hex colors or magic `px`/`mt-[13px]` values. Technical values (table names, SQL types, IDs) always render in `font-code-*`, never the body font.
- TypeScript is `strict: true`; `any` is disallowed unless documented inline with `// any justificado: ...`.

### Contracts and cross-system consistency

`contracts/uml-model.v2.json` is the single source of truth for the UML model shape shared by the Angular frontend, FastAPI backend, and the Spring/Postman generators in `back_generator_uml/`. Changes there ripple across all three — check `docs/domain-model/` and the relevant ADR before altering it.

### File-size / modularity discipline

Enforced by `scripts/check-file-size.py` (`.py`/`.ts`/`.html`/`.css`/`.scss`, ignoring `node_modules`/`dist`/`venv`/etc.): 800 lines is a preventive warning (refactor before adding more to that file), 1000 lines is a hard failure. When a facade/service is getting overloaded, split it by cohesive responsibility (see e.g. how `uml-editor.facade.ts` was decomposed into `editor-selection.service.ts`, `editor-history.service.ts`, `editor-command.service.ts`, or how backend command handlers live under `app/modeling/application/commands/` split per entity: `class_handlers.py`, `attribute_handlers.py`, `relation_handlers.py`, etc.) rather than splitting mechanically (`part1.ts`/`misc.ts` style splits are explicitly disallowed).

### Traceability

Every feature should be traceable to a use case (CU) in the requirements capture document; there's a traceability matrix at `docs/traceability/requirements-matrix.md`. Check `docs/architecture/adr/` before implementing anything touching concurrent collaboration (CU5, ADR-0003, pending) or offline sync (CU13, ADR-0004, pending) — those are frozen until their ADRs are resolved. Auth (ADR-0005) is approved and implemented in `app/shared/security/`.
