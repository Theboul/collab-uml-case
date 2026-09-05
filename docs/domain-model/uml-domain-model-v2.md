# Especificación del UML Domain Model V2 (Canónico)

## 1. Visión y Principios del Modelo de Dominio

El **UML Domain Model V2** constituye el núcleo semántico canónico del sistema CASE. Representa formalmente diagramas de clases alineados con el estándar **OMG UML 2.5**, desacoplado de cualquier tecnología de presentación gráfica (JointJS, SVG, Canvas), de persistencia relacional (SQLAlchemy, Django ORM), de frameworks web (FastAPI) o de generación específica (Spring Boot, Flutter).

### Principios Arquitectónicos Fundamentales

1. **Agnóstico de Frameworks y Librerías de Serialización**:
   El modelo de dominio puro se implementa mediante estructuras de datos nativas del lenguaje (ej. `dataclasses` de Python o POPO - *Plain Old Python Objects*), **sin dependencia alguna de Pydantic, SQLAlchemy o frameworks web**. Las librerías de validación de esquemas (como Pydantic) pertenecen exclusivamente a los adaptadores de entrada/salida de la capa perimetral (API DTOs).
2. **FastAPI como Orquestador, no Contenedor de Reglas**:
   FastAPI no contiene las reglas de dominio ni las restricciones UML; su rol es coordinar las peticiones HTTP/WebSocket, invocar al motor de dominio puro (`UML Domain Engine`) y despachar las respuestas correspondientes.
3. **Separación Estricta: Semántica de Dominio vs. Presentación Gráfica**:
   El estado lógico y el estado visual son ortogonales:
   * **`UmlDomainModel` (Semántica Pura)**: Entidades lógicas, atributos con tipos y visibilidad, operaciones con parámetros, relaciones tipadas con multiplicidades formales y restricciones de integridad. Carece de coordenadas (`x`, `y`), colores o dimensiones.
   * **`UmlVisualLayout` (Presentación Gráfica Opcional e Independiente)**: Metadatos espaciales opcionales (posiciones de nodos, dimensiones de cajas, waypoints de conectores, nivel de zoom y paneo). **El modelo semántico es 100% operable en modo headless (CLI, CI/CD, generación de código) en ausencia total de layout.**
4. **Identidad Estable e Inmutable**:
   Todas las entidades y referencias inter-elementos utilizan identificadores estables e inmutables (UUID v4). Ninguna relación se vincula por nombre o etiqueta volátil.
5. **Versionado Semántico Explícito**:
   Todo modelo y contrato incorpora formalmente `schemaVersion` (ej. `"2.0.0"`).

```text
+-------------------------------------------------------------------------+
|                              UML Diagram                                |
|                                                                         |
|  +---------------------------------+   +-----------------------------+  |
|  |       UmlDomainModel (V2)       |   |   UmlVisualLayout (Opcional)|  |
|  |  (Semántica pura, clases, tipos,|   |  (Coordenadas x,y, bounds,  |  |
|  |   multiplicidades, validación)  |   |   waypoints, zoom, viewport)|  |
|  +---------------------------------+   +-----------------------------+  |
+-------------------------------------------------------------------------+
```

---

## 2. Definición Formal de Entidades del Metamodelo

### 2.1. Enumeraciones Fundamentales

```text
enum VisibilityKind {
    PUBLIC = "+"
    PRIVATE = "-"
    PROTECTED = "#"
    PACKAGE = "~"
}

enum PrimitiveType {
    STRING = "String"
    INTEGER = "Integer"
    FLOAT = "Float"
    BOOLEAN = "Boolean"
    DATE = "Date"
    DATETIME = "DateTime"
    VOID = "void"
    ANY = "Any"
}

// Conforme a UML 2.5: Aggregation y Composition son modalidades de extremo de Asociación
enum AggregationKind {
    NONE = "none"             // Asociación regular
    SHARED = "shared"         // Agregación (rombo hueco)
    COMPOSITE = "composite"   // Composición (rombo relleno)
}

enum ParameterDirectionKind {
    IN = "in"
    OUT = "out"
    INOUT = "inout"
    RETURN = "return"
}
```

---

### 2.2. Elementos Estructurales y Clasificadores

#### A. `UmlParameter`
Representa un argumento de una operación/método.
* `name`: `string` (Identificador del parámetro, ej. `productId`).
* `type`: `string` (Tipo primitivo o referencia a otra clase).
* `direction`: `ParameterDirectionKind` (Por defecto: `IN`).
* `defaultValue`: `string | null` (Valor predeterminado opcional).
* `multiplicity`: `MultiplicityRange` (Por defecto: `1..1`).

#### B. `UmlOperation`
Representa un método o comportamiento de un clasificador.
* `id`: `string` (UUID v4 único y estable).
* `name`: `string` (Nombre de la operación, ej. `calcularTotal`).
* `visibility`: `VisibilityKind` (Por defecto: `PUBLIC`).
* `returnType`: `string` (Tipo de retorno, ej. `Float` o `void`).
* `parameters`: `List<UmlParameter>` (Lista ordenada de parámetros).
* `isStatic`: `boolean` (Miembro de clase / estático).
* `isAbstract`: `boolean` (Operación abstracta / polimórfica).

#### C. `UmlAttribute`
Representa una propiedad estructural de un clasificador.
* `id`: `string` (UUID v4 único y estable).
* `name`: `string` (Nombre del atributo, ej. `precioUnitario`).
* `type`: `string` (Tipo de dato primitivo o referencia por nombre/id).
* `visibility`: `VisibilityKind` (Por defecto: `PRIVATE`).
* `defaultValue`: `string | null` (Valor por defecto opcional).
* `multiplicity`: `MultiplicityRange` (Por defecto: `1..1`).
* `isStatic`: `boolean` (Miembro estático de clase).
* `isReadOnly`: `boolean` (Equivalente a constante / inmutable).
* `isDerived`: `boolean` (Valor calculado, denotado con `/`).

#### D. `UmlClass`
Representa una entidad o clasificador en el diagrama.
* `id`: `string` (UUID v4 inmutable en el proyecto).
* `name`: `string` (Nombre de la clase, PascalCase, ej. `Factura`).
* `visibility`: `VisibilityKind` (Por defecto: `PUBLIC`).
* `isAbstract`: `boolean` (Indica si no puede ser instanciada).
* `isInterface`: `boolean` (Indica si es un clasificador de tipo interfaz).
* `stereotype`: `string | null` (Ej. `<<entity>>`, `<<service>>`, `<<interface>>`).
* `attributes`: `List<UmlAttribute>` (Colección de atributos propios).
* `operations`: `List<UmlOperation>` (Colección de métodos propios).
* `documentation`: `string | null` (Documentación semántica).

#### E. `MultiplicityRange`
Especificación formal de cardinalidad UML.
* `lowerBound`: `integer` (Mínimo de instancias, $\ge 0$).
* `upperBound`: `integer | null` (Máximo de instancias; `null` denota `*` / ilimitado).
* *Representaciones canónicas*:
  * `0..1` $\rightarrow$ `lowerBound: 0, upperBound: 1`
  * `1` ó `1..1` $\rightarrow$ `lowerBound: 1, upperBound: 1`
  * `*` ó `0..*` $\rightarrow$ `lowerBound: 0, upperBound: null`
  * `1..*` $\rightarrow$ `lowerBound: 1, upperBound: null`

---

### 2.3. Semántica Propia de Relaciones (UML 2.5)

En estricta concordancia con la especificación formal OMG UML 2.5, las relaciones no son enlaces genéricos sin tipificar, sino que cada una posee su **semántica formal propia e independiente**:

#### A. `UmlAssociation` y `AssociationEnd`
Una asociación representa una relación estructural entre clasificadores.
* **`AssociationEnd`**: Cada extremo de la asociación contiene:
  * `classId`: `string` (UUID v4 estable de la clase conectada).
  * `roleName`: `string | null` (Nombre de navegación de la propiedad en este extremo).
  * `multiplicity`: `MultiplicityRange` (Multiplicidad en este extremo).
  * `isNavigable`: `boolean` (Indica navegabilidad hacia este extremo).
  * **`aggregationKind`**: `AggregationKind` (`NONE`, `SHARED`, `COMPOSITE`).
    * `NONE`: Asociación binaria ordinaria.
    * `SHARED`: Agregación compartida (rombo hueco en el extremo del todo).
    * `COMPOSITE`: Composición existencial (rombo relleno en el extremo del todo).
* **`UmlAssociation`**:
  * `id`: `string` (UUID v4 único).
  * `name`: `string | null` (Nombre de la asociación).
  * `memberEnds`: `[AssociationEnd, AssociationEnd]` (Lista de extremos miembros).

#### B. `UmlGeneralization`
Representa una relación taxonómica de herencia y sustitución (Liskov) entre un clasificador más específico y uno más general.
* `id`: `string` (UUID v4 único).
* `specificClassId`: `string` (UUID de la subclase).
* `generalClassId`: `string` (UUID de la superclase).
* *Semántica*: No posee multiplicidades ni roles en los extremos. Requiere aciclicidad estricta (grafo DAG).

#### C. `UmlRealization`
Representa una relación contractual donde un clasificador cliente implementa la especificación definida por un clasificador proveedor (interfaz).
* `id`: `string` (UUID v4 único).
* `clientClassId`: `string` (UUID de la clase implementadora).
* `supplierInterfaceId`: `string` (UUID de la interfaz realizada).
* *Semántica*: Indica cumplimiento de contrato de métodos; no hereda estructura interna de atributos.

#### D. `UmlDependency`
Representa una relación de uso donde un clasificador cliente requiere la presencia o servicios de un clasificador proveedor para su funcionamiento.
* `id`: `string` (UUID v4 único).
* `clientClassId`: `string` (UUID de la clase dependiente).
* `supplierClassId`: `string` (UUID de la clase requerida).
* *Semántica*: Acoplamiento débil en tiempo de compilación o ejecución, sin relación estructural en base de datos.

---

## 3. Estructura Raíz del Modelo Canónico

```json
{
  "schemaVersion": "2.0.0",
  "modelId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "name": "SistemaGestionAcademica",
  "description": "Modelo canónico UML 2.5",
  "classes": [ ... ],
  "associations": [ ... ],
  "generalizations": [ ... ],
  "realizations": [ ... ],
  "dependencies": [ ... ],
  "visualLayout": {
    "viewport": { "zoom": 1.0, "panX": 0, "panY": 0 },
    "nodes": {
      "cls-uuid-1": { "x": 120, "y": 80, "width": 200, "height": 160 }
    },
    "links": {
      "assoc-uuid-1": {
        "vertices": [{ "x": 320, "y": 140 }]
      }
    }
  }
}
```

> [!NOTE]
> `visualLayout` es un bloque completamente opcional. Si se omite o es `null`, el modelo semántico es autosuficiente para validación, persistencia y generación de código.

---

## 4. Comparativa: Modelo Legacy vs. UML Domain Model V2

| Dimensión | Formato Legacy (Actual) | UML Domain Model V2 (Nuevo) |
| :--- | :--- | :--- |
| **Separación de capas** | Atributos gráficos y lógicos entremezclados en JointJS. | Separación estricta entre Dominio Semántico y Layout Visual opcional. |
| **Agregación / Composición** | Tipos planos de relación (`type: "aggregation"`). | **`aggregationKind` (`none`, `shared`, `composite`) en `AssociationEnd`**. |
| **Generalización, Realización y Dependencia** | Tratadas genéricamente con strings de labels. | **Semántica propia y específica** para cada tipo de relación formal. |
| **Multiplicidades** | Strings no estructurados en un array `labels: ["*", "1"]`. | Objeto formal `MultiplicityRange` con cotas numéricas enteras. |
| **Visibilidad** | No tipificada o implícita en la etiqueta. | Enumeración formal (`+`, `-`, `#`, `~`) para atributos y métodos. |
| **Parámetros de métodos** | String plano no parseado (`parameters: "id: Long"`). | Lista ordenada de objetos `UmlParameter` con nombres y tipos. |
| **Identificadores** | Mezcla de IDs de celdas SVG y nombres de clases. | **UUIDs estables e inmutables** en todos los elementos y referencias. |
| **Versionado** | Inexistente o implícito. | **`schemaVersion` semántico explícito (`2.0.0`)**. |
| **Dependencia de librerías** | Atado a JointJS en cliente y Django en servidor. | **Puro e independiente** (sin acoplamiento a Pydantic, FastAPI ni ORMs). |
