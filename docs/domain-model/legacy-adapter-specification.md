# Especificación del Adaptador Bidireccional Legacy ↔ Domain Model V2

Este documento define las reglas de transformación y los algoritmos de mapeo bidireccional entre el formato **Legacy (v1)** (utilizado por JointJS, el generador Spring Boot y el generador Flutter) y el **UML Domain Model V2 (canónico)**.

---

## 1. Arquitectura del Flujo de Transformación

El adaptador actúa como un puente de mediación gobernado por contratos estables:

```text
    [JointJS Canvas (Angular)]
                 │
                 ▼ (Legacy DTO: clases, rels, positions)
+-------------------------------------------------------------+
|               LEGACY ADAPTER (Input Pipeline)               |
|  - Extrae coordenadas hacia UmlVisualLayout (opcional)      |
|  - Parsea visibilidades, parámetros tipados y tipos         |
|  - Mapea relaciones legacy a Generalization / Realization / |
|    Dependency / Association con aggregationKind             |
|  - Convierte labels ["*", "1"] a MultiplicityRange          |
+-------------------------------------------------------------+
                 │
                 ▼
+-------------------------------------------------------------+
|                 UML DOMAIN MODEL V2 CANÓNICO                |
|  - Entidades y relaciones con semántica formal propia       |
|  - schemaVersion: "2.0.0"                                   |
|  - Referencias exclusivas mediante IDs estables             |
|  - Layout opcional y desacoplado                            |
+-------------------------------------------------------------+
                 │
                 +--------------------+--------------------+
                 │                    │                    │
                 ▼                    ▼                    ▼
+----------------------------+ +---------------+ +----------------------------+
| Spring Boot Adapter        | | JointJS Proj. | | Flutter Adapter            |
| (V2 -> UmlSchema v1        | | (V2 + Layout  | | (V2 -> uml_json v1         |
|  con Auditoría de Pérdidas)| |  -> Cells)    | |  con Auditoría de Pérdidas)|
+----------------------------+ +---------------+ +----------------------------+
                 │                    │                    │
                 ▼                    ▼                    ▼
        [Spring Boot 3.5.5]        [Canvas]        [Flutter App Generator]
```

---

## 2. Principio Mandatorio: No Pérdida Silenciosa de Información (*No Silent Loss*)

Los generadores legacy (`back_generator_uml` y `flutter_generator.py`) fueron diseñados para un subconjunto restringido de elementos UML (únicamente clases con atributos simples y asociaciones binarias o herencia básica).

> [!CRITICAL]
> **Ninguna característica del modelo V2 no soportada por los generadores legacy puede ser descartada o degradada silenciosamente.**

El adaptador downstream ejecutará un proceso de **Auditoría de Compatibilidad** que generará un reporte estructurado (`TransformationReport`):

```json
{
  "targetGenerator": "spring-boot-v1",
  "isCompatible": false,
  "warnings": [
    {
      "code": "WARN_VISIBILITY_IGNORED",
      "elementId": "attr-cust-email",
      "message": "La visibilidad PROTECTED (#) no es soportada por las plantillas Mustache legacy de Spring Boot; se mapeará como private."
    }
  ],
  "degradations": [
    {
      "code": "DEGRADE_REALIZATION_TO_ASSOCIATION",
      "elementId": "realiz-service-impl",
      "message": "La relación de Realización de Interfaz no es soportada nativamente por el generador Spring Boot v1; no se emitirá en el UmlSchema legacy."
    }
  ],
  "unsupportedErrors": [
    {
      "code": "ERR_MULTIPLE_INHERITANCE",
      "elementId": "cls-specialized",
      "message": "La clase posee múltiples generalizaciones, incompatible con la generación de entidades Java estándar."
    }
  ]
}
```

Si el reporte contiene errores no soportados (`unsupportedErrors`), la exportación se detiene informando al usuario exactamente qué elemento del modelo V2 impide la traducción fiel hacia el generador seleccionado.

---

## 3. Reglas de Transformación Upstream (Legacy v1 → Domain Model V2)

### A. Descomposición de Clases y Layout Visual
1. **Extracción Espacial Opcional**:
   * Si la clase legacy contiene `position: {x, y}` y `size: {width, height}`, estos valores se retiran de la definición lógica y se almacenan en `visualLayout.nodes[class.id]`.
   * Si el payload carece de coordenadas (modo headless o importación por script), `visualLayout` se establece en `null` sin afectar la validez del modelo.
2. **Normalización de Identificadores**:
   * Las referencias se resuelven exclusivamente mediante IDs estables (UUID v4). Si una entidad legacy carece de ID, se le genera un UUID inmutable en el punto de ingesta.
3. **Parseo de Atributos**:
   * Detección de visibilidad prefijada (`+`, `-`, `#`, `~`), asignando `PRIVATE` (`-`) como valor predeterminado si no se especifica.
4. **Parseo de Métodos y Parámetros**:
   * El string plano legacy (ej. `"id: Long, nombre: String"`) se tokeniza y parsea en una lista de objetos `UmlParameter` con nombres, tipos y direcciones (`IN`).

### B. Mapeo de Relaciones hacia Semánticas Propias

El formato legacy agrupaba todas las conexiones bajo un campo genérico `type`. El adaptador las discrimina hacia entidades con semántica propia:

1. **Si `type == "generalization"`**:
   * Se crea una instancia de **`UmlGeneralization`** vinculando `specificClassId = sourceId` y `generalClassId = targetId`.
   * Se descartan multiplicidades ya que la herencia en UML 2.5 carece de cardinalidad en los extremos.
2. **Si `type == "realization"`**:
   * Se crea una instancia de **`UmlRealization`** con `clientClassId = sourceId` y `supplierInterfaceId = targetId`.
3. **Si `type == "dependency"`**:
   * Se crea una instancia de **`UmlDependency`** con `clientClassId = sourceId` y `supplierClassId = targetId`.
4. **Si `type in ["association", "aggregation", "composition"]`**:
   * Se crea una instancia de **`UmlAssociation`** con dos `memberEnds`:
     * `source`: `classId = sourceId`, multiplicidad parseada de `labels[0]`, `aggregationKind = NONE`.
     * `target`: `classId = targetId`, multiplicidad parseada de `labels[1]`.
     * **Determinación de `aggregationKind`**:
       * Si `type == "aggregation"`, el extremo target se establece con `aggregationKind: SHARED`.
       * Si `type == "composition"`, el extremo target se establece con `aggregationKind: COMPOSITE`.
       * Si `type == "association"`, ambos extremos tienen `aggregationKind: NONE`.

---

## 4. Reglas de Transformación Downstream (Domain Model V2 → Consumidores)

### 4.1. Adaptador hacia el Generador Spring Boot (`UmlSchema` v1)
* **Destino**: `back_generator_uml` (`ProjectGenerator.java`).
* **Transformación**:
  1. Las clases se serializan como objetos `{id, name, attributes, methods}`.
  2. Cada `UmlGeneralization` se serializa como `{id, type: "generalization", sourceId: specificClassId, targetId: generalClassId, labels: []}`.
  3. Cada `UmlAssociation` se proyecta como `{id, type, sourceId, targetId, labels: [srcMult, tgtMult]}`:
     * Si algún extremo posee `aggregationKind == COMPOSITE`, `type = "composition"`.
     * Si algún extremo posee `aggregationKind == SHARED`, `type = "aggregation"`.
     * De lo contrario, `type = "association"`.
     * `labels[0]` se reconstruye a partir de `source.multiplicity` (ej. `0..*` $\rightarrow$ `*`).
     * `labels[1]` se reconstruye a partir de `target.multiplicity`.
  4. Los parámetros de métodos se formatean como string concatenado `"param: Tipo"`.
  5. `visualLayout` es omitido en el payload para optimizar el transporte HTTP.

> [!NOTE]
> La compatibilidad con el generador Spring Boot queda sujeta a la validación mediante una suite formal de pruebas de regresión de contratos JSON antes de su despliegue operativo.

---

### 4.2. Adaptador hacia el Generador Flutter CRUD
* **Destino**: `back_generador_bd/uml_api/services/flutter_generator.py` (`FlutterCRUDGenerator`).
* **Transformación**:
  * Utiliza el mismo esquema serializado que Spring Boot, mapeando las clases y relaciones al formato esperado por el parser de multiplicidades para generar pantallas Dart.
  * Cualquier relación de tipo `Dependency` o `Realization` presente en V2 que no tenga impacto en las vistas CRUD genera un registro en el `TransformationReport`.

---

### 4.3. Proyección hacia el Canvas JointJS (Angular)
1. Si `visualLayout` está presente:
   * Se proyecta la geometría exacta de las celdas (`x, y, width, height`) y vértices de conectores.
2. Si `visualLayout` está ausente (`null`):
   * El cliente frontend invoca un algoritmo de layout automático (ej. Dagre o Force-Directed) para calcular posiciones iniciales no superpuestas sobre el lienzo.
