# RULE-CODE-QUALITY — Estándar de Codificación, Modularidad y Límites de Tamaño

## 1. Objetivo

Todo código nuevo o modificado debe mantenerse:
* Legible
* Modular
* Testeable
* Reutilizable
* Fácil de mantener
* Con responsabilidades claramente separadas

**Regla de oro:** La IA NO debe resolver funcionalidades acumulando lógica indefinidamente dentro de archivos existentes.

Esta regla es de cumplimiento obligatorio en todo el repositorio para:
* Angular / TypeScript
* FastAPI / Python
* Tests, services, facades, handlers, repositories, components, adapters

---

## 2. Regla de Tamaño Máximo de Archivos

### Límite Absoluto
Ningún archivo fuente de aplicación podrá superar:
```text
1000 líneas
```
Este es un límite de seguridad estricto, no un objetivo de llenado.

### Límite Preventivo (Warning)
Si un archivo alcanza o supera:
```text
800 líneas
```
debe analizarse obligatoriamente si necesita dividirse antes de añadir cualquier funcionalidad nueva.

---

## 3. Escala de Tamaños Recomendados

* **0 – 300 líneas:** Tamaño ideal. Máxima cohesión y legibilidad.
* **300 – 500 líneas:** Aceptable si la cohesión es fuerte.
* **500 – 800 líneas:** Zona de alerta. Revisar responsabilidades antes de extender.
* **800 – 999 líneas:** Refactor preventivo obligatorio antes de seguir agregando código.
* **>= 1000 líneas:** **Fallo bloqueante** de validación de calidad.

> **Regla:** No dividir un archivo únicamente para cumplir el conteo métrico. La separación debe obedecer a criterios arquitectónicos y responsabilidades funcionales reales.

---

## 4. Principio de Responsabilidad Única (SRP)

Cada archivo y clase debe tener una única razón para cambiar.

### Antipatrón (God Object):
```text
uml-editor.facade.ts
├── estado reactivo
├── persistencia HTTP
├── selección y viewport
├── undo/redo
├── comandos de clases/atributos/relaciones
├── atajos de teclado
├── validaciones de negocio
├── mappers
└── manipulación de X6
```

### Arquitectura Modular Recomendada:
```text
application/
├── uml-editor.facade.ts          # Fachada delgada / orquestador
├── editor-selection.service.ts   # Estado y operaciones de selección
├── editor-history.service.ts     # Pila y ejecución de Undo/Redo
├── editor-command.service.ts     # Despacho y sincronización de comandos
└── editor-state.service.ts       # Signals de layout y modelo
```
La fachada orquesta las dependencias, pero no implementa internamente la lógica exhaustiva de cada subsistema.

---

## 5. Regla de Métodos y Funciones

Cada función o método debe realizar una única tarea concreta.

* **<= 30 líneas:** Ideal.
* **30 – 60 líneas:** Aceptable si la lógica es secuencial y clara.
* **> 60 líneas:** Revisar extracción de sub-operaciones.
* **> 100 líneas:** Refactor obligatorio salvo justificación matemática/algorítmica excepcional.

Prohibido escribir funciones que mezclen simultáneamente:
```text
validación + transformación + persistencia + renderizado + manejo de errores
```

---

## 6. Regla de Clases y Servicios

Una clase no debe convertirse en un "God Object". Si una clase:
1. Inyecta un exceso de dependencias (>5-6).
2. Maneja múltiples conceptos de dominio dispares.
3. Supera 500-700 líneas.
4. Contiene grupos de métodos que operan sobre subconjuntos desconectados de propiedades.

Debe delegar en servicios especializados. Ejemplo en X6:
```text
infrastructure/x6/
├── uml-graph.service.ts            # Ciclo de vida, plugins y setup del canvas
├── uml-selection.service.ts        # Selección visual y ports
├── uml-node-interaction.service.ts # Detección de hitboxes, clics y hover
└── uml-diagram-adapter.service.ts  # Traducción de ModeloUML <-> X6 Cells
```
*Prohibido crear servicios vacíos o artificiales que solo reenvíen llamadas sin aportar abstracción real.*

---

## 7. Backend (FastAPI) — Arquitectura y Handlers Granulares

Mantener separación limpia de capas:
* `api/`: Rutas HTTP y WebSockets (solo orquestan request/response).
* `application/`: Casos de uso y orquestadores.
* `domain/`: `core/uml_domain` aislado (reglas puras).
* `infrastructure/`: Adaptadores de base de datos, caché y servicios externos.
* `schemas/`: Contratos de entrada y salida (Pydantic).

Los handlers de comandos deben desacoplarse por entidad:
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
*Prohibido acumular todos los handlers dentro de `canvas_service.py` o en los routers de `api/`.*

---

## 8. Frontend (Angular) — Arquitectura

Estructura modular por feature:
* `domain/`: Modelos canónicos (`models/`) y contratos de comandos (`commands/`).
* `application/`: Facades y servicios de aplicación.
* `infrastructure/`: Adaptadores externos (AntV X6, JointJS, WebSockets, HTTP Gateways).
* `ui/`: Componentes de presentación (Smart & Dumb).

*Los componentes de UI jamás deben implementar lógica de negocio, cálculos de persistencia ni manipulación directa de grafos.*

---

## 9. Prohibición de Duplicación (DRY)

Antes de crear un nuevo servicio, helper, mapper, validador o tipo:
1. Buscar obligatoriamente en el repositorio si ya existe una implementación reutilizable.
2. Reutilizar tipos canónicos (ej. `VisibilityKind`, `UmlClassDto`, `UmlNodeSubElementEvent`).
3. Reutilizar mappers y validadores centrales.

---

## 10. Constantes Centralizadas

Prohibido utilizar "números mágicos" o cadenas sueltas en lógica de diseño o canvas.
* **Incorrecto:** `y: 42 + index * 16`, `width: 190`
* **Correcto:**
  ```typescript
  UML_NODE_DIMENSIONS.HEADER_HEIGHT
  UML_NODE_DIMENSIONS.ATTR_START_Y
  UML_NODE_DIMENSIONS.LINE_HEIGHT
  UML_NODE_DIMENSIONS.MIN_WIDTH
  ```

---

## 11. Complejidad y Flujo de Control

Evitar anidamientos profundos de `if/else`, `switch` o `try/catch`.
* Usar **guard clauses** al inicio de métodos.
* Preferir dispatchers o diccionarios de handlers en lugar de cadenas de `if/else if`.
* Separar validación previa de ejecución principal.

---

## 12. Validación Automática de Tamaño de Archivos

El proyecto cuenta con el script oficial:
```powershell
python scripts/check-file-size.py
```
Reglas del script:
1. Inspecciona recursivamente archivos `.py`, `.ts`, `.html`, `.css`, `.scss`.
2. Poda directorios de build y dependencias (`node_modules`, `dist`, `.git`, `.venv`, etc.).
3. Emite `[WARN]` si un archivo alcanza o supera 800 líneas.
4. Falla con código de salida `1` (`[ERROR]`) si cualquier archivo fuente supera 1000 líneas.

---

## 13. Pipeline de Verificación Obligatorio

Toda tarea o sesión de codificación debe culminar ejecutando la cadena completa:

### Backend:
```powershell
python scripts/check-file-size.py
python -m ruff check backend_case/app backend_case/tests
python -m pytest backend_case/tests/
```

### Frontend:
```powershell
python scripts/check-file-size.py
npm run build --prefix front_generador_bd
```

---

## 14. Regla de Refactor Preventivo

> Si al planificar o implementar una nueva funcionalidad se identifica que un archivo existente superaría las **800 líneas**, la IA debe:
> 1. Analizar las responsabilidades actuales del archivo.
> 2. Identificar subdominios o responsabilidades desacoplables.
> 3. Extraer los módulos cohesionados correspondientes.
> 4. Asegurar que las pruebas pasen intactas.
> 5. Implementar la nueva funcionalidad sobre la estructura modular resultante.
>
> **Nunca esperar a que el archivo sobrepase las 1000 líneas para refactorizar.**

---

## 15. Prohibición de Fragmentación Artificial

Queda terminantemente prohibido dividir archivos de manera mecánica o cosmética:
* `service-part1.ts`, `service-part2.ts`
* `facade_utils.py`, `misc.ts`

Cada archivo nuevo extraído debe poseer:
* Un nombre semántico que describa claramente su rol.
* Una responsabilidad cohesiva e independiente.
* Una interfaz pública (API) bien delimitada.

---

## 16. Regla de Imports y Dependencias

La dirección de dependencias es estrictamente unidireccional:
```text
UI → Application → Domain
Infrastructure → Application (implementa puertos)
Domain → NINGUNA dependencia externa (puro)
```
Prohibidas dependencias circulares en TypeScript y Python.

---

## 17. Definition of Done (DoD) de Calidad de Código

Ningún cambio o funcionalidad se considera terminado sin:
- [ ] Ningún archivo fuente supera 1000 líneas (`check-file-size.py`).
- [ ] Archivos entre 800 y 999 líneas justificados o refactorizados preventivamente.
- [ ] Responsabilidades arquitectónicas respetadas (sin God Objects).
- [ ] Cero duplicación de mappers, contratos o constantes.
- [ ] Constantes centralizadas aplicadas (sin magic numbers).
- [ ] Linter limpio (Ruff / ESLint).
- [ ] Type check limpio (Mypy / tsc strict).
- [ ] Pruebas unitarias/integración aprobadas (`pytest` / `ng test`).
- [ ] Compilación limpia (`ng build` código 0).
