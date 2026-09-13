# Decisión de diseño — filas de atributos del nodo de clase: SVG puro, no `foreignObject`

Contexto: Fase 2 del rediseño visual del nodo de clase UML (`uml-class-node.registration.ts`,
canvas X6 activo en `front_generador_bd/src/app/features/modeling/infrastructure/x6/`). El
compartimento de atributos pasa de un único `<text>` con `\n` por línea a filas reales, con
ícono de eliminar visible al hover, scroll interno tras 6-8 atributos, y ellipsis+tooltip en
nombres largos.

## Opciones evaluadas

1. **`foreignObject` con HTML real** dentro del nodo X6 (soportado nativamente por
   `@antv/x6@2.19.2` vía `Node.registry` shape `'html'`, sin dependencia nueva). Scroll interno,
   ellipsis y tooltip salen gratis vía CSS (`overflow-y:auto`, `text-overflow:ellipsis`, atributo
   `title`) en vez de lógica manual.
2. **Grupos SVG por fila** (`<g>` con `<rect>` de fondo + `<text>` + ícono `<path>`/`<use>`, uno
   por atributo). El hover-reveal del ícono funciona nativo vía CSS `:hover` (SVG lo soporta). El
   scroll interno y el ellipsis de nombres largos requieren lógica manual (clip-path + offset de
   traslación + listener de rueda; medición de texto con `getComputedTextLength()` y truncado en
   loop) — no hay atajo nativo para eso en SVG.

## Hallazgo que definió la decisión

El frontend legado (JointJS, en migración hacia X6 pero todavía activo y visible en el menú)
tiene una función de exportar el diagrama a imagen, real y funcionando hoy:

- `front_generador_bd/src/services/diagram/diagram.service.ts:1843` — `exportToImage(fileName)`
- Wireada en el menú lateral: `front_generador_bd/src/app/side-panel/side-panel.ts:174` y
  `side-panel.html:207-215` ("Exportar como Imagen")
- Implementación: clona el SVG del `paper` de JointJS, lo serializa con `XMLSerializer`, arma un
  blob `image/svg+xml`, lo carga en un `<img>` y lo rasteriza a `<canvas>`/PNG desde ahí.

Ese patrón (clonar SVG → serializar → `<img>` → `<canvas>`) es exactamente el que tiene problemas
conocidos de compatibilidad cuando el SVG contiene `<foreignObject>` con HTML embebido: varios
navegadores (Chrome en particular) no rasterizan ese contenido HTML al dibujar el `<img>` en el
`<canvas>`, o marcan el canvas como "tainted" y bloquean `toDataURL()`.

No existe ninguna decisión documentada sobre si `exportToImage()` se porta al editor X6 o se
retira junto con JointJS — no aparece en `docs/traceability/requirements-matrix.md` ni en
`docs/migration/legacy-retirement-criteria.md`, `migration-sequence.md` o
`transition-strategy.md`. Dado que es la única implementación de referencia para esa
funcionalidad, si en el futuro se porta al canvas X6 reusando el mismo patrón, un nodo con
`foreignObject` en el compartimento de atributos exportaría contenido en blanco o rompería la
exportación por completo — un bug silencioso, activado por una feature de otra fase, difícil de
razonar en el momento en que aparezca.

## Decisión

**Grupos SVG por fila (opción 2).** El costo adicional (scroll y ellipsis manuales) se paga una
sola vez, ahora, con contexto completo. El riesgo de `foreignObject` es silencioso y se activaría
recién si/cuando alguien porte `exportToImage()` a X6 — momento en el que nadie tendría por qué
recordar esta razón sin este documento.

Si en algún momento se retira formalmente `exportToImage()` (o se decide que el editor X6 nunca
tendrá exportación a imagen rasterizada), esta restricción deja de aplicar y se puede reconsiderar
`foreignObject` para simplificar el compartimento de atributos.

## Limitaciones aceptadas de la implementación (grupos SVG por fila)

Documentadas acá por el mismo motivo que la decisión de arriba: para que si aparecen como "bug"
más adelante, quien las encuentre tenga el contexto de que son conocidas y aceptadas, no un
descuido.

- **Indicador PK/FK**: fuera de alcance de Fase 2. Ni `UmlAttribute` (frontend) ni
  `contracts/uml-model.v2.json` tienen noción de clave primaria/foránea — es un modelo de
  diagrama de clases UML, no un modelo ER. Agregarlo requiere una decisión de contrato explícita
  (ripplea a `backend_case`, `back_generator_uml` y frontend), fuera del alcance de un rediseño
  visual.
- **El truncado (ellipsis) de nombres largos de atributo se recalcula solo cuando cambian los
  datos del atributo** (alta/edición/borrado), no en cada frame de un resize manual en vivo del
  nodo (arrastrar la esquina con el Transform de X6). El ancho usado para decidir dónde truncar
  con `getComputedTextLength()` se toma en el momento del render de las filas, no se vuelve a
  calcular mientras el usuario arrastra el borde del nodo. Con el ancho mínimo actual del nodo
  (180px) el caso "nombre ya truncado + el usuario justo angostó la caja" es un desajuste visual
  menor (el corte queda con el ancho de la última vez que cambiaron los datos), nunca overflow
  fuera de la caja ni un dato incorrecto — se resuelve solo en el próximo cambio de datos de ese
  atributo. Se puede cerrar más adelante enganchando el mismo recálculo al listener de
  `node:resized`, si en la práctica llega a notarse.
