# Reporte de Línea Base y Pruebas de Caracterización Legacy (SPEC-04)

Este documento registra los resultados oficiales obtenidos durante la ejecución de las pruebas de caracterización del sistema legacy. Su propósito es establecer una línea base verificable que proteja el comportamiento funcional existente antes de iniciar la implementación del **UML Domain Model V2**.

---

## 1. Matriz de Resultados de Ejecución

| ID | Subsistema | Prueba | Resultado | Observación |
| :--- | :--- | :--- | :---: | :--- |
| **T-FE-01** | Frontend Angular | Serialización de clase UML (F01) | **PASS** | Estructura de `classes` y `attributes` coincide con la especificación de `DiagramExportService`. |
| **T-FE-02** | Frontend Angular | Serialización y parseo de atributos | **PASS** | Detección de tipos y nombres mediante delimitador `:`. |
| **T-FE-03** | Frontend Angular | Serialización de operaciones (F02) | **PASS** | Métodos parseados en `name`, `parameters` y `returnType`. |
| **T-FE-04** | Frontend Angular | Serialización de relaciones (F03) | **PASS** | `sourceId`, `targetId`, `type` y `labels` preservados fielmente. |
| **T-FE-05** | Frontend Angular | Multiplicidades legacy soportadas | **PASS** | `1`, `*`, `0..1`, `0..*`, `1..*` validados en enlaces. |
| **T-FE-06** | Frontend Angular | Exportación del modelo combinado (F08) | **PASS** | El payload completo exportado reproduce la totalidad de clases y relaciones de F08. |
| **T-SPRING-01** | Generador Spring | Generación básica de estructura (F01) | **PASS** | Plantillas Mustache validadas (`pom.xml`, `Application`, `Entity`, `Repository`, `Service`, `Controller`, `properties`). |
| **T-SPRING-02** | Generador Spring | Compilación del proyecto generado | **NOT EXECUTED** | Entorno de pruebas no dispone de runtime local de Java 21 / Maven (`mvn`). |
| **T-SPRING-03** | Generador Spring | Asociación 1:N (F03) | **PASS** | Caracterización de `@OneToMany` (mappedBy) y `@ManyToOne` en entidades JPA. |
| **T-SPRING-04** | Generador Spring | Asociación N:M con intermedia (F04) | **PASS** | Entidad intermedia autogenerada (`PedidoProducto`) con sendos `@ManyToOne` y colecciones `@OneToMany`. |
| **T-SPRING-05** | Generador Spring | Composición (F06) | **PASS** | `@OneToMany` con `cascade = CascadeType.ALL` y `orphanRemoval = true` activo. |
| **T-SPRING-06** | Generador Spring | Generalización (F07) | **PASS** | `@Inheritance(strategy = InheritanceType.JOINED)` en padre y `extends Persona` sin PK en hijo. |
| **T-POST-01** | Generador Postman | Colección Postman v2.1 válida (F01) | **PASS** | Schema oficial `collection.json` v2.1.0 y variable `baseUrl` configurada. |
| **T-POST-02** | Generador Postman | Operaciones CRUD completas (F01) | **PASS** | 5 peticiones generadas: Listar (GET), Obtener por ID (GET), Crear (POST), Actualizar (PUT), Eliminar (DELETE). |
| **T-POST-03** | Generador Postman | Bodies de ejemplo tipados | **PASS** | Generación de payloads JSON con valores por defecto acordes al tipo (`int` $\rightarrow$ `1`, `String` $\rightarrow$ `"ejemplo"`). |
| **T-POST-04** | Generador Postman | Cobertura de modelo combinado (F08) | **PASS** | Carpetas y endpoints creados para todas las entidades del dominio de ventas. |
| **T-FLUTTER-01** | Generador Flutter | Estructura de proyecto Flutter (F01) | **PASS** | `pubspec.yaml`, `lib/main.dart`, `lib/config.dart`, modelos, servicios y vistas generados. |
| **T-FLUTTER-02** | Generador Flutter | Vistas CRUD para entidad (F01) | **PASS** | Generación de `{clase}_list_view.dart`, `{clase}_form_view.dart` y `{clase}_detail_view.dart`. |
| **T-FLUTTER-03** | Generador Flutter | Selección de entidad foránea (F03) | **PASS** | Modelo `Pedido` contiene referencia a `Cliente` y formulario incluye lógica de vinculación. |
| **T-FLUTTER-04** | Generador Flutter | Análisis estático `flutter analyze` | **NOT EXECUTED** | Entorno de pruebas no dispone del Flutter SDK instalado. |

---

## 2. Resumen Estadístico de Pruebas

| Estado | Cantidad | Porcentaje |
| :--- | :---: | :---: |
| **PASS** (Superadas) | 16 | 88.9% |
| **FAIL** (Fallidas) | 0 | 0.0% |
| **NOT EXECUTED** (Omitidas por ausencia de runtime en host) | 2 | 11.1% |
| **BLOCKED** (Bloqueadas) | 0 | 0.0% |
| **TOTAL** | **18** | **100.0%** |

---

## 3. Clasificación Formal de Comportamientos y Defectos Legacy Encontrados

En estricta conformidad con la directiva de **NO modificar código productivo ni corregir defectos durante esta SPEC**, se documentan formalmente los siguientes hallazgos:

### A. EXPECTED LEGACY BEHAVIOR (Comportamientos Esperados Confirmados)
1. **Asociaciones N:M en Spring Boot y Flutter**: Tanto Java como Python crean una entidad intermedia artificial cuyo nombre resulta de la concatenación alfabética de ambas entidades (`PedidoProducto`). Ambas clases originales reciben `@OneToMany` hacia la intermedia.
2. **Herencia y Llaves Primarias**: En `generalization`, la clase hija no define su propio `@Id` ni atributo autoincremental; hereda la clave primaria de la superclase (`@Inheritance(strategy = InheritanceType.JOINED)`).
3. **Estructura de Vistas en Flutter**: `flutter_generator.py` no utiliza la convención moderna `lib/screens/`, sino que organiza todas las pantallas bajo `lib/views/` con sufijo `_view.dart` (`_list_view.dart`, `_form_view.dart`, `_detail_view.dart`), manteniendo `lib/widgets/` y `lib/config.dart`.

### B. KNOWN LEGACY DEFECTS (Defectos Conocidos de la Implementación Actual)
1. **Parseo Frágil de Atributos sin Tipo**: En `DiagramExportService.parseAttributesFromText`, si el usuario escribe un nombre sin dos puntos (ej. `"codigo"` en lugar de `"codigo: String"`), el servicio asigna silenciosamente un string vacío `type: ""`, lo que provoca errores de compilación aguas abajo en Spring Boot y Flutter.
2. **Cardinalidades No Soportadas o Vacías**: En `ProjectGenerator.java` y `FlutterCRUDGenerator.py`, si una asociación carece de etiquetas en `labels`, se asume silenciosamente `sourceCard = "*"` y `targetCard = "1"`, convirtiendo asociaciones no etiquetadas en relaciones `ManyToOne` sin advertir al usuario.
3. **Colisiones de Edición Concurrente en Colaboración**: El protocolo P2P no implementa bloqueos ni versionado; la operación `edit_text` sobreescribe destructivamente el contenido si dos colaboradores editan la misma caja simultáneamente.
4. **Acoplamiento de Señalización de Gemini**: `services_gemini.py` utiliza coincidencia heurística de cadenas en español ("eliminar", "borra", "cambia") para discernir si debe emitir un JSON de borrado o de creación, lo cual es frágil ante prompts en otros idiomas o formulaciones indirectas.

### C. UNDETERMINED (Aspectos a Validar con Runtime Dedicado)
1. **Compilación de Entidades Compuestas en Java 21**: La compilación real de proyectos Spring Boot generados para relaciones circulares complejas de ManyToMany requiere verificación en un entorno que cuente con Maven y JVM instalados.
