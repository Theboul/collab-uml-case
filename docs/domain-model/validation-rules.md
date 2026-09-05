# Reglas de Validación Semántica UML 2.5 y Perfiles de Generación

Este documento formaliza el sistema de validación del proyecto, estableciendo una **separación arquitectónica estricta** entre la **Validación Semántica UML 2.5 pura** y la **Validación de Compatibilidad de Generación de Código**.

> [!IMPORTANT]
> **El motor de validación reside íntegramente en el motor de dominio (`UML Domain Engine`) como lógica de negocio pura desacoplada.** FastAPI no contiene estas reglas; únicamente coordina su invocación y maneja las respuestas HTTP correspondientes.

---

## 1. Separación de Fases de Validación

```text
       [Modelo UML V2]
              │
              ▼
+─────────────────────────────────────────────+
| FASE 1: VALIDACIÓN SEMÁNTICA UML 2.5 PURA   |
| (Agnóstica de cualquier lenguaje de destino)|
| - Grafo acíclico de herencia (DAG)          |
| - Consistencia de AssociationEnds           |
| - Coherencia de multiplicidades             |
| - Unicidad de identificadores estables      |
+─────────────────────────────────────────────+
              │
         ¿Es Válido? ── No ──> [Error de Metamodelo UML]
              │
              ├─ Si ──> [Modelo Persistible en Base de Datos]
              │
              ▼
+─────────────────────────────────────────────+
| FASE 2: COMPATIBILIDAD DE GENERACIÓN        |
| (Evaluada según el Target Generator Profile)|
|                                             |
| [Perfil Spring Boot v1]  [Perfil Flutter v1]|
| - Herencia simple Java   - Tipos Dart CRUD  |
| - Mapeo JPA/Mustache     - Entidades M:N    |
+─────────────────────────────────────────────+
              │
              ▼
   [TransformationReport]
  (Warnings, Degradaciones, Errores de Generación)
```

Un modelo puede ser **100% válido en UML 2.5** (ej. poseer herencia múltiple de interfaces, dependencias sutiles o agregaciones multinivel) y al mismo tiempo requerir advertencias o adaptaciones al ser exportado a un generador específico. Separar estas fases previene corromper el estándar UML con limitaciones técnicas de un generador de código particular.

---

## 2. Fase 1: Reglas de Validación Semántica UML 2.5 (Agnóstica)

### 2.1. Identificadores Estables y Metadatos
* **VUML-01 (schemaVersion Obligatorio)**: El documento debe contener un campo `schemaVersion` semánticamente válido (ej. `"2.0.0"`).
* **VUML-02 (IDs Estables Inmutables)**: Todos los clasificadores, propiedades, operaciones y relaciones deben tener un `id` único en formato UUID v4. No se permiten referencias por nombre mutable.
* **VUML-03 (Nombres de Clasificadores Válidos)**: El nombre de cada clase debe satisfacer `^[A-Za-z_][A-Za-z0-9_]*$`. No pueden existir dos clasificadores con el mismo nombre dentro del mismo espacio de nombres.

### 2.2. Propiedades y Operaciones
* **VUML-04 (Unicidad de Atributos)**: Dentro de una misma clase, ningún atributo puede compartir el mismo nombre.
* **VUML-05 (Unicidad de Firmas de Operación)**: No pueden coexistir dos operaciones con el mismo nombre y exactamente la misma secuencia de tipos de parámetros dentro de un clasificador.

### 2.3. Semántica de Generalización (Herencia)
* **VUML-06 (Herencia sin Auto-referencia)**: `specificClassId != generalClassId`.
* **VUML-07 (Grafo Acíclico Dirigido - DAG)**: La jerarquía de herencia entre clases no puede contener ciclos (detección algorítmica vía DFS o algoritmo de Kahn).
* **VUML-08 (No Instanciabilidad de Superclase Abstracta)**: Las clases hijas de superclases abstractas deben implementar métodos abstractos o declararse abstractas.

### 2.4. Semántica de Realización y Dependencia
* **VUML-09 (Realización Válida)**: `supplierInterfaceId` debe referenciar a un clasificador marcado como interfaz (`isInterface == true`).
* **VUML-10 (Existencia de Referencias en Dependencias)**: Tanto `clientClassId` como `supplierClassId` deben existir en el modelo.

### 2.5. Semántica de Asociación y `aggregationKind`
* **VUML-11 (Extremos Válidos en Asociación)**: Todo `memberEnd` debe apuntar a un `classId` existente en el modelo.
* **VUML-12 (Restricción de Composición Existencial)**: Si un extremo posee `aggregationKind: COMPOSITE` (rombo relleno), la clase subordinada (`part`) no puede pertenecer a más de un compuesto durante su ciclo de vida; por tanto, la multiplicidad en el extremo del compuesto (`whole`) no puede tener `upperBound > 1`.
* **VUML-13 (Coherencia de Multiplicidades)**: En todo `MultiplicityRange`, `lowerBound >= 0` y, si `upperBound != null`, `upperBound >= lowerBound`.

---

## 3. Fase 2: Perfiles de Compatibilidad de Generación de Código

Estas reglas se evalúan únicamente al solicitar la exportación hacia un generador específico y generan advertencias estructuradas en el `TransformationReport` sin invalidar el diagrama en el editor:

### Perfil A: Generador Spring Boot v1 (`back_generator_uml`)
* **VGEN-SB-01 (Herencia Múltiple)**: Si una clase posee más de una relación de generalización directa hacia otra clase concreta, se emite un error de compatibilidad bloqueante (Java no soporta herencia múltiple de clases).
* **VGEN-SB-02 (Tipos Primitivos Soportados)**: Atributos cuyos tipos no sean mapeables a tipos estándar de Java/JPA (`String`, `Integer`, `Long`, `Double`, `Boolean`, `LocalDate`) se marcan con advertencia de degradación hacia `String`.
* **VGEN-SB-03 (Realizaciones de Interfaz)**: Las relaciones de tipo `Realization` generan una advertencia indicando que el generador Mustache v1 no emitirá la palabra clave `implements`.

### Perfil B: Generador Flutter CRUD v1 (`flutter_generator.py`)
* **VGEN-FL-01 (Entidades de Gestión CRUD)**: Las clases marcadas como `isAbstract: true` emiten una advertencia informando que no se generarán pantallas de captura directa para dicha entidad.
* **VGEN-FL-02 (Multiplicidades ManyToMany)**: Si se detecta una asociación `*..*`, se audita la generación automática de la entidad intermedia para persistencia y navegación en pantallas móviles.
* **VGEN-FL-03 (Dependencias Débiles)**: Las relaciones de tipo `Dependency` se omiten de las pantallas de gestión emitiendo el correspondiente aviso en el reporte de transformación.
