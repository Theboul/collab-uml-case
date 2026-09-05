# Reporte de Implementación del UML Domain Model V2 y Adaptadores (SPEC-05)

Este documento detalla la implementación del **UML Domain Model V2** y la suite de adaptadores bidireccionales, desarrollada de forma aislada y sin alterar el código productivo del sistema legacy.

---

## 1. Clases y Módulos Implementados

Toda la implementación reside en `core/uml_domain/`:

### A. Dominio Puro (`core/uml_domain/model.py`)
* **Clasificadores**:
  * `UmlClassifier`: Base con `id` estable, `name`, `visibility` y `documentation`.
  * `UmlClass`: Soporta `is_abstract`, `is_interface`, `stereotype`, `attributes` y `operations`.
  * `UmlInterface`: Interfaz formal con operaciones.
  * `UmlEnumeration`: Enumeración con literales tipados.
  * `UmlDataType`: Tipo estructurado con atributos.
* **Propiedades y Comportamiento**:
  * `UmlAttribute`: Identificador UUID, tipo, visibilidad (`+`, `-`, `#`, `~`), `defaultValue`, `multiplicity: MultiplicityRange`, flags de `is_static`, `is_read_only` y `is_derived`.
  * `UmlOperation`: Firma formal, tipo de retorno, visibilidad, flags `is_static`, `is_abstract` y lista ordenada de `UmlParameter`.
  * `UmlParameter`: Dirección (`IN`, `OUT`, `INOUT`, `RETURN`), tipo, nombre y valor por defecto.
* **Relaciones con Semántica Propia**:
  * `UmlAssociation`: Asociación binaria compuesta por dos instancias de `AssociationEnd`.
  * `AssociationEnd`: Contiene `class_id` estable, `role_name`, `multiplicity`, `is_navigable` y `aggregation_kind` (`NONE`, `SHARED`, `COMPOSITE`). Conforme a UML 2.5, **agregación y composición no son subclases de Relationship**, sino modalidades del extremo de asociación.
  * `UmlGeneralization`: Herencia taxonómica directa (`specific_class_id`, `general_class_id`), sin multiplicidades ni roles.
  * `UmlRealization`: Implementación contractual de interfaz (`client_class_id`, `supplier_interface_id`).
  * `UmlDependency`: Dependencia débil (`client_class_id`, `supplier_class_id`).
* **Multiplicidades Estructuradas**:
  * `MultiplicityRange`: Cotas enteras inmutables (`lower >= 0`, `upper >= lower` o `None` para `*`). Propiedades `is_many`, `is_optional` y formato `to_uml_str()`.
* **Presentación Visual Opcional e Independiente**:
  * `UmlVisualLayout`: Diccionario desacoplado de `nodes` (`ElementLayout(x, y, width, height)`), `links` (`RelationshipLayout(vertices)`) y `viewport` (`zoom`, `pan_x`, `pan_y`). El modelo semántico es 100% autosuficiente y funcional sin layout.
* **Contenedor Raíz**:
  * `UmlDomainModel`: `schema_version = "2.0.0"`, `model_id` (UUID), nombre, descripción y colecciones de clasificadores, relaciones y layout opcional.

### B. Motor de Validación (`core/uml_domain/validation.py`)
* `UMLValidator`:
  * `VUML-01`: Validación de `schema_version`.
  * `VUML-02`: Unicidad e inmutabilidad de identificadores (UUIDs).
  * `VUML-03`: Nombres obligatorios y no vacíos.
  * `VUML-04`: Unicidad de atributos dentro de una misma clase.
  * `VUML-05`: Unicidad de firmas de métodos (nombre + tipos de parámetros).
  * `VUML-06`: Existencia de extremos y prohibición de auto-herencia en generalizaciones.
  * `VUML-07`: Detección algorítmica de ciclos en la jerarquía de herencia mediante DFS (garantía de Grafo Acíclico Dirigido - DAG).
  * `VUML-09`: Validación de que la realización apunte exclusivamente a una interfaz.
  * `VUML-10` / `VUML-11`: Integridad referencial de dependencias y asociaciones.
  * `VUML-12`: Invariante de composición existencial: la multiplicidad en el extremo del compuesto no puede tener `upper > 1`.
* `SpringCompatibilityValidator`:
  * `VGEN-SB-01`: Detección y bloqueo de herencia múltiple de clases concretas (incompatible con Java/JPA).
  * `VGEN-SB-03`: Advertencia estructurada sobre interfaces y realizaciones no soportadas en plantillas v1.
* `FlutterCompatibilityValidator`:
  * `VGEN-FL-01`: Advertencia de omisión de pantallas de formulario para clases abstractas.

### C. Suite de Adaptadores (`core/uml_domain/adapters/`)
* `LegacyMultiplicityParser`: Conversión estricta de cadenas (`1`, `*`, `0..1`, `0..*`, `1..*`, `2..5`) hacia `MultiplicityRange`. Lanza excepción explícita ante entradas inválidas.
* `LegacyInputAdapter`: Ingesta de JSON legacy (F01 a F08), separando el layout visual (`position`, `size`, `vertices`) hacia `UmlVisualLayout` y mapeando clases y relaciones a entidades V2.
* `LegacyOutputAdapter`: Proyección desde V2 hacia el contrato legacy `{classes, relationships}` con auditoría `TransformationReport`.
* `SpringLegacyMapper`: Especialización para Spring Boot que emite el payload `UmlSchema` v1.
* `FlutterLegacyMapper`: Especialización para Flutter CRUD que emite el payload `uml_json` para `FlutterCRUDGenerator`.

---

## 2. Decisiones Arquitectónicas Aplicadas

1. **Aislamiento Total de Frameworks**: El módulo `core/uml_domain/` utiliza exclusivamente la biblioteca estándar de Python (`dataclasses`, `enum`, `uuid`, `typing`). No existe acoplamiento a Pydantic ni FastAPI.
2. **Principio No Silent Loss**: El adaptador de salida genera un `TransformationReport` que registra explícitamente advertencias, degradaciones y errores no soportados si un modelo V2 incluye características que los generadores legacy no admiten (ej. `UmlInterface` o `UmlDependency`).
3. **Contrato Formal V2 Materializado**: Se creó el archivo [contracts/uml-model.v2.json](file:///c:/Users/alex/Documents/Software/Diagramador_UML_Examen2/contracts/uml-model.v2.json), con el esquema JSON Schema Draft 2020-12 validado.

---

## 3. Desviaciones Respecto al Diseño

* **Ninguna**: La implementación reproduce exactamente la especificación de diseño aprobada en SPEC-03 y refinada en la revisión documental.

---

## 4. Cobertura y Resultados de Pruebas

Se ejecutó la totalidad de la suite de pruebas del proyecto:

```text
Suite Node.js (Frontend Legacy):      6 PASS / 0 FAIL
Suite Pytest (SPEC-04 Characterization): 12 PASS / 2 SKIPPED (mvn & flutter ausentes)
Suite Pytest (SPEC-05 V2 Domain & Adapters): 32 PASS / 0 FAIL
-------------------------------------------------------------------------------------
TOTAL:                               50 PASS / 2 SKIPPED / 0 FAIL (0 REGRESIONES)
```

### Pruebas Nuevas Destacadas:
* **Prueba de Aceptación End-to-End (`test_end_to_end_compatibility.py`)**:
  * `F08 Legacy` $\rightarrow$ `LegacyInputAdapter` $\rightarrow$ `UML Domain Model V2` $\rightarrow$ `UMLValidator (PASS)` $\rightarrow$ `SpringLegacyMapper` $\rightarrow$ `Spring Generator Simulator`: Generó exitosamente la totalidad de las 6 entidades, repositorios y relaciones sin modificar el código de Spring.
  * `F08 Legacy` $\rightarrow$ `LegacyInputAdapter` $\rightarrow$ `UML Domain Model V2` $\rightarrow$ `UMLValidator (PASS)` $\rightarrow$ `FlutterLegacyMapper` $\rightarrow$ `FlutterCRUDGenerator.generate_project`: Generó un proyecto Flutter real con `pubspec.yaml`, `main.dart`, 6 modelos Dart y 6 vistas CRUD en `lib/views/` sin tocar `flutter_generator.py`.
* **Pruebas de Round-Trip**: Validación de equivalencia semántica para `F01`, `F03`, `F04`, `F06`, `F07` y `F08`.

---

## 5. Limitaciones Conocidas

1. **Generadores Legacy Unidireccionales**: Los generadores actuales (`back_generator_uml` y `flutter_generator.py`) solo soportan clases concretas y asociaciones/herencias simples. Elementos avanzados como `UmlInterface`, `UmlEnumeration` o `UmlDependency` quedan auditados como degradaciones no emitidas en dichos generadores.
2. **Entorno sin Compiladores Host**: Al no estar instalados localmente Java 21/Maven ni el Flutter SDK, las pruebas `T-SPRING-02` y `T-FLUTTER-04` permanecen como `SKIPPED`.
