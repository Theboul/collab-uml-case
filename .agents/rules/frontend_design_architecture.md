# Reglas de Diseño y Arquitectura Frontend — SchemaCraft (Angular)

> Objetivo: que cada vista nueva se sienta parte de la misma app, que ningún componente visual se reescriba dos veces, y que un desarrollador nuevo pueda ubicar y reutilizar cualquier pieza de UI sin adivinar.

---

## 1. Design Tokens (fuente única de verdad)

Ningún componente debe usar colores, tipografías o espaciados "sueltos" (hex hardcodeado, `px` mágico). Todo sale de un archivo central de tokens.

### 1.1 Colores semánticos (no literales)
Definir en `tailwind.config.ts` (o `:root` con CSS variables si no se usa Tailwind) usando **nombres de rol**, no nombres de color:

| Token | Rol | Ejemplo de uso |
|---|---|---|
| `primary` | Acento de marca, botón principal, elemento activo | Botón "Guardar", tab seleccionado |
| `secondary` | Acento informativo secundario | Tipos de dato, enlaces |
| `tertiary` | Éxito / validación / sync | Badge "Válido", ícono de sync |
| `danger` | Destructivo | Botón eliminar, error |
| `neutral-*` | Texto, bordes, superficies | Texto secundario, separadores |
| `surface`, `surface-container`, `surface-container-high/low/lowest` | Jerarquía de fondos (elevación) | Fondo de página vs. tarjeta vs. modal |

**Regla:** un componente nunca escribe `bg-[#4F46E5]` ni `text-indigo-600`. Siempre `bg-primary`, `text-on-primary-container`, etc. Si un color no existe como token, se agrega al config antes de usarse — no se improvisa inline.

### 1.2 Tipografía
- `font-headline-*` → títulos (Inter, 600-700).
- `font-body-*` → texto de UI (Inter, 400-500).
- `font-code-*` → nombres de columnas, tipos de dato, badges técnicos (JetBrains Mono).

**Regla:** cualquier texto que represente un valor técnico (nombre de tabla, tipo SQL, ID) usa `font-code-*`, nunca Inter. Esto es lo que le da identidad "developer tool" a la app — no es opcional.

### 1.3 Espaciado
Usar únicamente la escala definida (`gutter-xs/sm/md/lg/xl`, `field-row-height`, `toolbar-height`, `sidebar-width`). Prohibido usar valores arbitrarios como `mt-[13px]` salvo casos de posicionamiento de canvas/SVG.

---

## 2. Arquitectura de componentes en Angular

### 2.1 Tres capas obligatorias

```
src/app/
├── core/           # Servicios singleton, guards, interceptors (sin UI)
├── layout/         # Shell de la app: header, sidebars, contenedor de rutas
├── shared/
│   └── ui/         # Componentes de presentación puros y reutilizables
│       ├── button/
│       ├── badge/
│       ├── data-type-tag/
│       ├── table-card/
│       ├── modal-shell/
│       └── ...
└── features/       # Vistas de negocio (dashboard, editor, exportador...)
    ├── dashboard/
    ├── canvas-editor/
    ├── sql-exporter/
    └── table-config-modal/
```

- **`shared/ui`**: componentes "tontos" (presentational). Reciben datos por `@Input()`, emiten eventos por `@Output()`. No inyectan servicios de negocio, no hacen llamadas HTTP. Ejemplo: `<sc-badge type="PK">`, `<sc-data-type-tag type="UUID">`.
- **`features/*`**: componentes "inteligentes" (container). Orquestan estado, servicios, y componen los componentes de `shared/ui`.
- **`layout/`**: existe **un único** componente de shell por contexto de navegación (ver sección 3). Las features nunca declaran su propio header o sidebar.

**Regla dura:** si vas a copiar y pegar HTML de un componente a otro, en vez de eso creas un componente en `shared/ui` y lo importas en ambos lugares. Sin excepciones para botones, badges, tags de tipo de dato, avatares o tarjetas.

### 2.2 Standalone components
Todos los componentes se crean como `standalone: true`. Nada de `NgModules` por feature salvo que el equipo decida lo contrario explícitamente. Esto simplifica el árbol de imports y evita shared modules gigantes.

### 2.3 Contratos de Input/Output tipados
Cada componente de `shared/ui` expone su forma de datos como `interface` o `type`, no `any`:

```ts
export interface ColumnBadge {
  label: 'PK' | 'FK' | 'UQ' | 'NN' | 'CHK';
  variant: 'primary' | 'warning' | 'neutral';
}
```

Esto evita que cada feature invente su propia forma de representar lo mismo (ej. una tabla con badges distintos a otra).

---

## 3. Consistencia de Shell (el problema que ya detectamos)

Todas las vistas que viven **dentro de un proyecto abierto** (Canvas Designer, SQL Code Editor, Tables & Entities, Relationships, Migrations, Snapshots, Schema Settings) comparten **un solo layout component**: `ProjectShellComponent`.

- Un solo sidebar izquierdo de navegación (`<sc-project-sidebar>`).
- Un solo header/toolbar superior (`<sc-project-toolbar>`) con: undo/redo, estado de guardado, exportar, compartir, avatar.
- Las features solo insertan su contenido vía `<router-outlet>` dentro del shell. Ninguna feature vuelve a dibujar el sidebar o el toolbar.

Las vistas **fuera de un proyecto** (Login, Dashboard/onboarding) usan un layout distinto: `AppShellComponent` (header horizontal, sin sidebar de proyecto). Esto es intencional, no un descuido — se documenta así para que nadie "corrija" la diferencia sin querer.

**Regla de verificación:** antes de mergear una nueva vista, revisar: ¿esta pantalla vive dentro de `ProjectShellComponent` o de `AppShellComponent`? Si no se sabe la respuesta, no se crea la vista todavía.

---

## 4. Componentes reutilizables mínimos a construir primero

Estos son los que ya aparecen repetidos en 2+ vistas — deben existir en `shared/ui` antes de seguir agregando pantallas:

| Componente | Usado en |
|---|---|
| `sc-button` (variants: primary/secondary/inverted/outlined) | Todas |
| `sc-badge` (PK/FK/UQ/NN/CHK) | Editor, modal de tabla, canvas |
| `sc-data-type-tag` (UUID, VARCHAR, NUMERIC...) | Editor, modal, canvas |
| `sc-table-card` (tarjeta de entidad en el canvas) | Canvas Designer, mini-preview del dashboard |
| `sc-avatar-stack` (grupo de avatares colaborativos) | Toolbar, tarjetas de proyecto |
| `sc-search-input` | Dashboard, sidebar de tablas |
| `sc-modal-shell` (header + tabs + footer de acciones de un modal) | Modal de tabla, exportador SQL |
| `sc-code-block` (bloque de SQL con line numbers y syntax highlight) | Exportador SQL, DDL preview del modal |
| `sc-empty-state` | Dashboard, listas vacías |

**Regla:** si una feature necesita algo parecido a uno de estos pero "un poco distinto", primero se evalúa si es una variante (`@Input() variant`) del componente existente antes de crear uno nuevo.

---

## 5. Íconos

- Un único set: Material Symbols Outlined, siempre vía un wrapper `<sc-icon name="database" size="18">` en vez de escribir `<span class="material-symbols-outlined">` directo en cada feature.
- Esto centraliza el fallback si la fuente no carga (evita el glitch de "texto literal" que vimos en las capturas) y permite cambiar de librería de íconos en un solo lugar el día de mañana.

---

## 6. Accesibilidad y estados (no negociable)

- Todo `<input>` tiene `<label>` asociado (`for`/`id`), incluso si se oculta visualmente (`sr-only`).
- Todo elemento interactivo tiene estado `:hover`, `:focus-visible` y `:disabled` definido con los tokens, no solo `:hover`.
- Contraste mínimo AA (4.5:1) entre texto y fondo — verificar especialmente los tonos lavanda/violeta claro sobre `surface` oscuro.

---

## 7. Checklist antes de dar por "terminada" una vista nueva

1. ¿Usa solo tokens de color/tipografía/espaciado, cero valores hardcodeados?
2. ¿Reutiliza `ProjectShellComponent` o `AppShellComponent` en vez de dibujar su propio header/sidebar?
3. ¿Todo botón, badge, tag de tipo de dato o tarjeta viene de `shared/ui`, no copiado/pegado?
4. ¿Los íconos pasan por `sc-icon`?
5. ¿Los inputs tienen label y los interactivos tienen estado focus/disabled?
6. ¿El componente es standalone y sus Inputs/Outputs están tipados (sin `any`)?

Si alguna respuesta es "no", la vista no está lista para mergear.
