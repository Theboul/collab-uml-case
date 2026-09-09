# CU4 — Gestionar relaciones del diagrama de clases

**Estado de este documento:** Ficha de Captura de Requisitos (original) + Análisis técnico actualizado contra el código real del repositorio. Ver sección 5 para el detalle de qué parte del alcance original ya está implementada y qué falta.

---

## 1. Ficha de Caso de Uso (Captura de Requisitos)

| Campo | Detalle |
|---|---|
| **Caso de uso** | CU4: Gestionar relaciones del diagrama de clases |
| **Propósito** | Permitir que los usuarios creen, configuren, modifiquen y eliminen las relaciones necesarias para representar correctamente la semántica de un diagrama de clases UML |
| **Actores** | A1 (Anfitrión), A2 (Colaborador) |
| **Iniciador** | Usuario |
| **Precondición** | El usuario debe encontrarse dentro de un lienzo activo y deben existir los elementos que participarán en la relación |

**Flujo de suceso principal**

*Crear:*
1. El usuario selecciona el tipo de relación
2. Selecciona el elemento origen
3. Selecciona el elemento destino
4. El sistema crea la relación
5. El usuario configura sus propiedades
6. El sistema valida y almacena la relación

*Editar:*
1. El usuario selecciona una relación existente
2. Modifica sus propiedades
3. El sistema valida y actualiza la relación

*Eliminar:*
1. El usuario selecciona una relación
2. Solicita eliminarla
3. El sistema elimina la relación del modelo

| Campo | Detalle |
|---|---|
| **Poscondición** | La relación UML queda creada, modificada o eliminada de forma consistente |
| **Excepción** | Si los elementos no existen, la relación es incompatible o alguna propiedad no es válida, el sistema rechaza la operación |

---

## 2. Diagrama de comunicación conceptual (Análisis)

*No existía en el documento original. Se propone aquí siguiendo el mismo patrón boundary/control/entity usado en CU1-CU3, para consistencia del documento de Análisis. Cubre el flujo "Crear" — el único implementado hoy (ver sección 5).*

```
:A1/A2 ──1: seleccionarTipoRelacion(tipo)──► :LienzoBoundary
:A1/A2 ──2: seleccionarOrigenDestino(idOrigen, idDestino)──► :LienzoBoundary
:A1/A2 ──3: configurarPropiedades(nombre, roles, multiplicidades, agregacion)──► :LienzoBoundary
                                                            │
                                                            │ 4: agregarAsociacion(...)
                                                            ▼
                                                  :CanvasService (control)
                                                            │
                                                            │ 5: obtenerLienzo(canvasId)
                                                            ▼
                                                  :CanvasRepository (control)
                                                            │
                                                            │ 6: lienzo
                                                            ▼
                                          :UmlDomainModel (entity) ◄── find_classifier_by_id(origen_id)
                                                            │                find_classifier_by_id(destino_id)
                                                            │ 7: agregar_asociacion(...)
                                                            │    [valida existencia de origen/destino]
                                                            ▼
                                          :UmlAssociation (entity, nueva instancia)
                                                            │
                                                            │ 8: RelacionAgregada (evento de dominio)
                                                            ▼
                                                  :CanvasService (control)
                                                            │
                                                            │ 9: guardar(lienzo) — vía mappers
                                                            ▼
                                                  :CanvasRepository (control) ──► PostgreSQL (JSONB)
                                                            │
                                                            │ 10: CanvasDetailSchema
                                                            ▼
:A1/A2 ◄──11: lienzo actualizado (201 Created)────── :LienzoBoundary
```

**Objetos participantes:**
- **Boundary:** `LienzoBoundary` (UI Angular — panel de creación de relación)
- **Control:** `CanvasService` (application), `CanvasRepository` (infrastructure)
- **Entity:** `UmlDomainModel`, `UmlAssociation`, `AssociationEnd`, `MultiplicityRange` (todos en `core/uml_domain`)

> **Nota (verificada contra el repo):** el diagrama de arriba ilustra la ruta REST directa (`POST /associations` → `CanvasService.agregar_asociacion`). Existe una **segunda ruta**, confirmada con `cat` real del código: `POST /api/v2/canvases/{canvas_id}/commands` → `RelationCommandHandler` (`backend_case/app/modeling/application/commands/relation_handlers.py`), que soporta `CREATE_RELATION`, `UPDATE_RELATION`, `UPDATE_MULTIPLICITY` y `DELETE_RELATION` (incluye generalización, agregación y composición además de asociación simple). Ver sección 5 para el detalle de qué tan completa está esta ruta respecto al patrón de eventos de dominio del resto del proyecto.

---

## 3. Modelo de datos real

Ubicación: `core/uml_domain/model.py`

```python
class AggregationKind(str, Enum):
    NONE = "none"
    SHARED = "shared"       # agregación (rombo hueco)
    COMPOSITE = "composite" # composición (rombo relleno)

@dataclass(frozen=True)
class MultiplicityRange:
    lower: int
    upper: Optional[int] = None  # None = "*"
    # valida lower >= 0 y upper >= lower en __post_init__

@dataclass
class AssociationEnd:
    class_id: str
    role_name: Optional[str] = None
    multiplicity: MultiplicityRange = MultiplicityRange(1, 1)
    is_navigable: bool = True
    aggregation_kind: AggregationKind = AggregationKind.NONE

@dataclass
class UmlAssociation:
    id: str
    name: Optional[str] = None
    member_ends: Tuple[AssociationEnd, AssociationEnd]
```

**Método de mutación** (`UmlDomainModel.agregar_asociacion`): valida que origen y destino existan (`ElementoNoEncontrado` si no), construye ambos `AssociationEnd` con multiplicidad y agregación, agrega la asociación a `self.associations`, y devuelve `(UmlAssociation, RelacionAgregada)`.

**Parsing de multiplicidad** (`core/uml_domain/adapters/multiplicity_parser.py`) — convierte strings de UI a `MultiplicityRange`:

| Entrada | Resultado |
|---|---|
| `"*"`, `"0..*"` | `(0, None)` |
| `"1"`, `"1..1"` | `(1, 1)` |
| `"0..1"` | `(0, 1)` |
| `"1..*"` | `(1, None)` |
| `"2..5"` | `(2, 5)` — regex `^(\d+)\.\.(\*|\d+)$` |
| `"n"`, `"m"` | `(0, None)` — notación informal |
| formato inválido | `ValueError` explícito |

---

## 4. Contrato de API real

**Endpoint:** `POST /api/v2/canvases/{canvas_id}/associations`

**Request (`AddAssociationRequest`):**

```json
{
  "sourceClassId": "string (requerido)",
  "targetClassId": "string (requerido)",
  "name": "string | null",
  "sourceRole": "string | null",
  "targetRole": "string | null",
  "sourceMultiplicity": "string (default '1')",
  "targetMultiplicity": "string (default '1')",
  "sourceAggregation": "none | shared | composite (default 'none')",
  "targetAggregation": "none | shared | composite (default 'none')"
}
```

**Response — `201 Created`** (`CanvasDetailSchema` completo, camelCase):

```json
{
  "id": "canvas-uuid",
  "name": "Lienzo Asociaciones",
  "version": 3,
  "model": {
    "classes": [ "..." ],
    "associations": [
      {
        "id": "assoc-uuid",
        "name": "genera",
        "memberEnds": [
          { "classId": "...", "roleName": "origen", "multiplicity": { "lowerBound": 1, "upperBound": 1 }, "isNavigable": true, "aggregationKind": "none" },
          { "classId": "...", "roleName": "destino", "multiplicity": { "lowerBound": 0, "upperBound": 1 }, "isNavigable": true, "aggregationKind": "none" }
        ]
      }
    ]
  }
}
```

**Errores:**

| Código HTTP | `code` | Causa |
|---|---|---|
| 404 | `CANVAS_NOT_FOUND` | El lienzo no existe |
| 404 | `ELEMENT_NOT_FOUND` | `sourceClassId` o `targetClassId` no existen en el modelo |
| 422 | `UML_INVALID_MODEL` | Multiplicidad inválida (parser) o regla UML violada |
| 422 | *(validación Pydantic estándar)* | Falta un campo requerido en el request |
| 409 | `VERSION_CONFLICT` | Colisión de concurrencia (optimistic locking sobre `version`) |

---

## 5. Estado de implementación vs. alcance de la ficha original

*Actualizado con evidencia verificada directamente (`cat` del código real, no una descripción de terceros). Hay dos rutas de mutación conviviendo en el sistema — ver tabla.*

| Sub-flujo de la ficha | Ruta REST (`/associations`) | Ruta de comandos (`/commands` → `RelationCommandHandler`) |
|---|---|---|
| **Crear** — asociación binaria | ✅ Implementado, probado (`test_add_association_cu4`), emite `RelacionAgregada` | ✅ Implementado (`CREATE_RELATION`/`ADD_RELATION`/`ADD_ASSOCIATION`), reutiliza `agregar_asociacion()` — sí emite evento |
| **Crear** — generalización | ❌ No expuesto | ⚠️ Implementado, pero hace `lienzo.modelo.generalizations.append(gen)` **directo**, sin pasar por un método del dominio ni emitir evento |
| **Crear** — realización, dependencia | ❌ No implementado en ninguna ruta | ❌ No implementado en ninguna ruta |
| **Editar** (multiplicidad, roles, nombre, tipo de agregación) | ❌ No implementado | ⚠️ Implementado (`UPDATE_RELATION`/`EDIT_RELATION`/`UPDATE_MULTIPLICITY`), pero **muta los objetos directamente** (`asoc.member_ends[0].multiplicity = ...`) sin pasar por un método del dominio y **devuelve `(None, None)` — no emite ningún evento** |
| **Eliminar** | ❌ No implementado | ⚠️ Implementado (`DELETE_RELATION`/`DELETE_ASSOCIATION`), filtra las listas directamente y limpia `visual_layout["links"]`, pero también **devuelve `(None, None)` — no emite evento** |
| Validación de existencia de elementos | ✅ `ElementoNoEncontrado` → `404 ELEMENT_NOT_FOUND` | ⚠️ Parcial — `CREATE_RELATION` sí valida vía `agregar_asociacion()`; `UPDATE`/`DELETE` no validan que el `relationId` exista antes de intentar mutar (fallan en silencio si no se encuentra, ej. `next((...), None)` sin manejo del caso `None` en `UPDATE_MULTIPLICITY`) |
| Validación de propiedad inválida | ✅ Multiplicidad inválida → `422 UML_INVALID_MODEL`; VUML-11/12/13 | ⚠️ Mismo parser de multiplicidad reutilizado (`LegacyMultiplicityParser`), pero sin confirmar si las excepciones se propagan igual desde el dispatcher de comandos |

**Conclusión corregida:** la ficha completa (crear/editar/eliminar, cualquier tipo de relación) **sí está funcionalmente cubierta en su mayor parte**, pero no de la forma prolija que el resto del proyecto exige. Estado actualizado tras el fix del 2026-09-06:

1. **✅ RESUELTO — Bug de `CREATE_RELATION` con `type: "GENERALIZATION"`.** Verificado con `git grep` que la dataclass real usa `specific_class_id`/`general_class_id`. El handler fue corregido (antes usaba `specific_classifier_id`/`general_classifier_id`, kwargs inexistentes que causaban `TypeError`). Se agregó `test_create_generalization_relation_command` con aserciones sobre los nombres de campo reales (`specificClassId`, `generalClassId`), y la suite completa pasó tras el cambio.
2. **Editar y eliminar no emiten eventos de dominio.** Esto rompe el patrón "método explícito devuelve evento" que se estableció como estándar (`agregar_clase`, `agregar_asociacion`) y dejaría a CU5/CU13 sin nada que capturar el día que necesiten loguear cambios — exactamente el problema que ese patrón se creó para evitar.
3. **La mutación de generalización, edición y eliminación ocurre por fuera del dominio** (`lienzo.modelo.associations.append/pop` directo desde el handler), violando la regla propia del proyecto de que toda mutación pasa por un método explícito de `UmlDomainModel`. El bug ya corregido del punto 1 fue consecuencia directa de esto — y sigue siendo un riesgo latente mientras el patrón no se corrija de raíz (el próximo campo mal escrito no tiene por qué avisar con un `TypeError` tan obvio).
4. **Realización y dependencia no están implementadas en ninguna ruta** — ahí sí hay una brecha real, no solo de prolijidad.
5. **Validación de `relationId` inexistente en editar/eliminar es inconsistente** — puede fallar silenciosamente en vez de devolver un error claro.

---

## 6. Reglas de validación aplicables (VUML)

De `core/uml_domain/validation.py`:

- **VUML-02** — Unicidad de ID: el id de la asociación no colisiona con clasificadores ni otras relaciones.
- **VUML-11** — Integridad referencial: ambos extremos deben apuntar a un `class_id` existente.
- **VUML-12** — Invariante de composición (OMG UML 2.5): si un extremo es `COMPOSITE`, su multiplicidad superior no puede ser mayor a 1.
- **VUML-13** — Consistencia de rango: `lowerBound >= 0` y `upperBound >= lowerBound`, garantizado por el constructor de `MultiplicityRange`.
- *(Reservadas para generalización, no aplican a asociación: VUML-06 prohíbe autoreferencia, VUML-07 detecta ciclos por DFS.)*

---

## 7. Casos de prueba existentes

`backend_case/tests/test_modeling_api.py` (Ruta REST)
- `test_add_association_cu4` — crea dos clases, las asocia con multiplicidades distintas (`1` y `0..1`), verifica 201 y estructura de `memberEnds`.
- `test_add_association_with_nonexistent_class_returns_404` — asocia contra un id inexistente, verifica `404 ELEMENT_NOT_FOUND`.

`tests/domain_model/test_validator.py` (Capa de Dominio Puro — verificado con `git grep`)
- `test_missing_reference` (L70) — verifica rechazo por `VUML-11` cuando una asociación apunta a un clasificador inexistente.
- `test_invalid_composition_multiplicity` (L130) — verifica rechazo por `VUML-12` cuando un extremo `COMPOSITE` posee multiplicidad superior > 1.
- *(Adicionales relevantes)*: `test_circular_generalization` (L91, `VUML-07`) y `test_realization_pointing_to_non_interface` (L112, `VUML-09`).

`backend_case/tests/test_canvases_commands.py` (Ruta de Comandos)
- Prueba `CREATE_RELATION` (Paso 6) y `UPDATE_RELATION` (Paso 7, mutando a `AGGREGATION`).
- Prueba la eliminación en cascada de relaciones al borrar una clase (`DELETE_ELEMENT`, Paso 9).
- `test_create_generalization_relation_command` (agregado 2026-09-06) — verifica `CREATE_RELATION` con `type: GENERALIZATION`, cubre el bug ya corregido de la sección 5.

**Nota de verificación pendiente:** tras el fix del bug y este test nuevo, el conteo total de la suite saltó de 80 a 96 items (78→94 passed, 2 skipped constante). Solo un test nuevo fue documentado explícitamente en esta sesión; el resto de la diferencia (15 tests) no fue explicado ni verificado. No bloquea el trabajo, pero queda pendiente correr `pytest backend_case/tests/ tests/ -v --tb=no -q` para confirmar el origen de esos tests antes de considerar la suite completamente auditada.

**Cobertura faltante confirmada:**
- Test HTTP de multiplicidad inválida vía ruta REST (`422 UML_INVALID_MODEL`)
- Test HTTP de `VUML-12` (composición con multiplicidad > 1) vía ruta REST
- Test de comando `DELETE_RELATION` directo y `UPDATE_MULTIPLICITY`
- Test de que `UPDATE_RELATION`/`DELETE_RELATION` con un `relationId` inexistente devuelvan un error explícito en vez de fallar silenciosamente
- Test de que editar/eliminar una relación emita el evento de dominio correspondiente, una vez se creen los eventos formales

---

## 8. Pendientes para cerrar el CU4 completo

El punto 0 (bug de kwarg en `UmlGeneralization`) ya fue resuelto y verificado el 2026-09-06 — ver sección 5, punto 1. Lo que queda es formalizar el resto del ciclo de vida de relaciones para que siga el mismo patrón que ya funciona bien en `agregar_asociacion()`:

1. **Agregar métodos formales al dominio** que reemplacen la mutación directa del handler:
   - `UmlDomainModel.editar_asociacion(relacion_id, ...)` → valida existencia, muta, devuelve `RelacionModificada`
   - `UmlDomainModel.eliminar_asociacion(relacion_id)` → valida existencia, remueve, devuelve `RelacionEliminada`
   - `UmlDomainModel.agregar_generalizacion(...)` → hoy el handler hace `.append()` directo (ya corregido en cuanto a nombres de campo, pero sigue sin pasar por el dominio); debería seguir el mismo patrón que `agregar_asociacion()`
2. **Agregar los eventos faltantes** a `core/uml_domain/events.py`: `RelacionModificada`, `RelacionEliminada` (ya están `ElementoAgregado`/`RelacionAgregada`, falta el resto del ciclo de vida)
3. **Actualizar `RelationCommandHandler`** para que llame a estos métodos nuevos en vez de mutar `lienzo.modelo.associations`/`generalizations` directamente — esto no cambia el comportamiento observable, solo lo alinea con la regla de mutación explícita del proyecto y evita que un bug similar al ya corregido vuelva a pasar desapercibido
4. **Cerrar el manejo de `relationId` inexistente** en `UPDATE_RELATION`/`UPDATE_MULTIPLICITY`/`DELETE_RELATION` — lanzar `ElementoNoEncontrado`, que el handler global ya traduce a `404 ELEMENT_NOT_FOUND`
5. `agregar_realizacion()`, `agregar_dependencia()` — brecha real, no solo de prolijidad; no existen en ninguna ruta
6. Tests HTTP: multiplicidad inválida (`422`), `VUML-12` vía endpoint, `relationId` inexistente, y que editar/eliminar emitan el evento correcto
7. Actualizar la matriz de trazabilidad y confirmar si la existencia del sistema de comandos amerita su propio ADR corto (no bloqueante para seguir, pero pendiente de decidir)