---
paths:
  - "front_generador_bd/**/*.ts"
  - "front_generador_bd/**/*.html"
  - "**/*.component.ts"
---

# Angular / AntV X6 — reglas de SchemaCraft (front_generador_bd)

## Tooling

Config: `front_generador_bd/eslint.config.js` (flat config, `@angular-eslint` + `typescript-eslint`)
y `front_generador_bd/.prettierrc.json`.

```bash
cd front_generador_bd
pnpm run lint          # eslint sobre src/**/*.{ts,html}
pnpm run lint:fix
pnpm run format:check  # prettier --check
pnpm run format
ng build                # falla si hay errores de tsc en modo strict
```

TypeScript en modo `strict: true`. `any` prohibido salvo con comentario
`// any justificado: ...`; usar `unknown` + guard cuando el tipo es real pero desconocido
(forzado por `@typescript-eslint/no-explicit-any`).

## Arquitectura de carpetas

```text
front_generador_bd/src/app/
├── core/           # servicios singleton, guards, interceptors — sin UI
├── layout/         # AppShellComponent (login/dashboard) y ProjectShellComponent
│                    # (sidebar + toolbar únicos para toda vista dentro de un proyecto abierto)
├── shared/ui/       # componentes de presentación puros (sc-button, sc-badge,
│                    # sc-data-type-tag, sc-table-card, sc-modal-shell, sc-icon...)
│                    # sin HttpClient, sin lógica de negocio
└── features/        # modeling, collaboration, assistant, interoperability, generation
    └── <feature>/
        ├── application/     # facades / application services
        ├── infrastructure/  # adapters X6/JointJS, gateways HTTP, websockets
        └── ui/               # componentes "inteligentes" (container)
```

- **Flujo de datos obligatorio:** `Component → Facade/Application Service → Gateway/Adapter → HttpClient`.
  Ningún componente inyecta `HttpClient` directo (forzado por `no-restricted-imports` en el linter).
- **`shared/ui`** son componentes tontos: `@Input()`/`@Output()` únicamente, sin servicios de negocio.
  Si vas a copiar/pegar markup de botón/badge/tag/tarjeta entre dos sitios, en vez de eso créalo
  aquí una vez e impórtalo en ambos — sin excepciones.
- **Shell único:** toda vista dentro de un proyecto abierto (Canvas Designer, SQL Editor, Tables,
  Relationships, Migrations, Snapshots, Schema Settings) usa `ProjectShellComponent` (un solo
  `<sc-project-sidebar>`, un solo `<sc-project-toolbar>`). Login/Dashboard usan `AppShellComponent`.
  Si no está claro cuál corresponde a una vista nueva, esa vista no está lista para construirse.
- Todos los componentes son `standalone: true`. Nada de `NgModules` por feature.

## Convenciones de nombres (Angular Style Guide oficial)

| Tipo | Archivo | Clase | Selector |
|---|---|---|---|
| Componente | `nombre-feature.component.ts` | `NombreFeatureComponent` | `sc-nombre-feature` (kebab, prefijo `sc`) |
| Servicio | `nombre.service.ts` | `NombreService` | — |
| Facade (application) | `nombre.facade.ts` | `NombreFacade` | — |
| Gateway/Adapter (infra HTTP) | `nombre.gateway.ts` | `NombreGateway` | — |
| Guard | `nombre.guard.ts` | funcional (`CanActivateFn`), preferido sobre clase | — |
| Interceptor | `nombre.interceptor.ts` | funcional (`HttpInterceptorFn`), preferido sobre clase | — |
| Directiva | `nombre.directive.ts` | `NombreDirective` | `[scNombre]` (camelCase, prefijo `sc`) |
| Pipe | `nombre.pipe.ts` | `NombrePipe` | `scNombre` |
| Modelo/tipo de dominio | `nombre.model.ts` / `nombre.types.ts` | `interface`/`type` PascalCase | — |

**Prefijo `sc` obligatorio** para todo componente/directiva **nuevo**. El prefijo `app-` que
persiste en `features/modeling` (canvas JointJS legado) queda aceptado por el linter solo ahí
mientras dura la migración a X6 — no usarlo en código nuevo ni "corregirlo" masivamente sin que
el usuario lo pida explícitamente (es transición documentada, no un descuido).

## Motor de canvas (AntV X6 activo / JointJS legado)

Todo el código de renderizado de canvas vive confinado en:
- `features/modeling/infrastructure/x6/` — nodos custom en `x6/nodes/`, servicios de
  sincronización del canvas (`*.service.ts`) en la misma carpeta. **Motor activo.**
- `features/modeling/infrastructure/jointjs/` — legado, en migración hacia X6.

`eslint.config.js` bloquea con `no-restricted-imports` cualquier `import` de `@antv/x6`,
`@antv/x6-plugin-*` o `jointjs` fuera de esas carpetas. Si el linter marca uno de estos imports
en otro lugar, la corrección correcta es mover la lógica a un adapter/servicio ahí — nunca
deshabilitar la regla inline. Nunca lógica de negocio dentro de un adaptador X6/JointJS.

Si un servicio/facade de este módulo supera ~500-700 líneas o mezcla ciclo de vida + selección +
interacción + traducción de modelo, se descompone por responsabilidad (ejemplo ya aplicado):
```text
infrastructure/x6/
├── uml-graph.service.ts            # ciclo de vida, plugins y setup del canvas
├── uml-selection.service.ts        # selección visual y ports
├── uml-node-interaction.service.ts # detección de hitboxes, clics y hover
└── uml-diagram-adapter.service.ts  # traducción ModeloUML <-> X6 Cells
```
Prohibido crear servicios vacíos que solo reenvíen llamadas sin aportar abstracción real, y
prohibido dividir mecánicamente (`part1.ts`/`misc.ts`).

## Design tokens (fuente única de verdad — no literales)

- **Colores:** siempre semánticos (`bg-primary`, `text-on-primary-container`, `surface`,
  `surface-container-*`, `danger`, `neutral-*`). Nunca `bg-[#4F46E5]` ni `text-indigo-600`. Si un
  color no existe como token, se agrega al config antes de usarse.
- **Tipografía:** `font-headline-*` (títulos), `font-body-*` (texto UI), `font-code-*` (nombres de
  tabla, tipos SQL, IDs — cualquier valor técnico). Un valor técnico en `font-body-*` es un bug.
- **Espaciado:** solo la escala (`gutter-xs/sm/md/lg/xl`, `field-row-height`, `toolbar-height`,
  `sidebar-width`). Prohibido `mt-[13px]` salvo posicionamiento de canvas/SVG.
- **Íconos:** un único set (Material Symbols Outlined) vía `<sc-icon name="..." size="18">`, nunca
  `<span class="material-symbols-outlined">` directo en una feature.

## Accesibilidad (no negociable)

- Todo `<input>` con `<label>` asociado (`for`/`id`, o `sr-only` si se oculta visualmente).
- Todo interactivo con `:hover`, `:focus-visible` y `:disabled` vía tokens.
- Contraste mínimo AA (4.5:1).

## Checklist antes de dar por terminada una vista nueva

1. ¿Solo tokens de color/tipografía/espaciado, cero valores hardcodeados?
2. ¿Reutiliza `ProjectShellComponent`/`AppShellComponent` en vez de dibujar su propio header/sidebar?
3. ¿Todo botón/badge/tag/tarjeta viene de `shared/ui`, no copiado/pegado?
4. ¿Íconos vía `sc-icon`?
5. ¿Inputs con label y estados focus/disabled?
6. ¿Componente standalone con Inputs/Outputs tipados (sin `any`)?

Si alguna respuesta es "no", la vista no está lista para mergear.
