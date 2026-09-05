# Matriz de Protección para la Migración Arquitectónica

Esta matriz mapea los comportamientos y capacidades del sistema legacy con sus correspondientes **pruebas de caracterización protectoras** y el **componente de la arquitectura V2** que asumirá dicha responsabilidad, garantizando que ninguna funcionalidad se rompa o se degrade silenciosamente durante la modernización.

---

## 1. Matriz de Trazabilidad y Salvaguarda

| Comportamiento / Capacidad Legacy | Prueba Protectora | Fixture Asociado | Futuro Componente V2 Responsable | Mecanismo de Salvaguarda |
| :--- | :---: | :---: | :--- | :--- |
| **Serialización de Clases UML** | `T-FE-01` | `F01` | `LegacyInputAdapter` (Angular/FastAPI) | Conversión exacta de nodo a `UmlClass` con UUID estable. |
| **Parseo de Atributos y Tipos** | `T-FE-02` | `F01`, `F08` | `AttributeNormalizationService` | Detección de visibilidad y mapeo a `UmlAttribute` tipado. |
| **Parseo de Operaciones y Métodos** | `T-FE-03` | `F02`, `F08` | `OperationNormalizationService` | Descomposición formal de firma a `List<UmlParameter>`. |
| **Serialización de Enlaces y Relaciones** | `T-FE-04` | `F03`, `F04` | `RelationshipClassifier` | Mapeo a `Generalization`, `Realization`, `Dependency` o `Association` con `aggregationKind`. |
| **Interpretación de Multiplicidades** | `T-FE-05` | `F03`, `F04` | `MultiplicityParser` | Conversión formal a cotas enteras `MultiplicityRange(lower, upper)`. |
| **Exportación de Dominio Completo** | `T-FE-06` | `F08` | `UmlDomainEngine` & `CanvasSerializer` | Garantía de integridad estructural y coherencia de grafo. |
| **Generación de Proyecto Spring Boot** | `T-SPRING-01` | `F01` | `SpringLegacyAdapter` (Downstream) | Emisión del contrato `UmlSchema` v1 para `ProjectGenerator.java`. |
| **Asociación 1:N en JPA** | `T-SPRING-03` | `F03` | `SpringLegacyAdapter` | Preservación de pares `@OneToMany(mappedBy)` y `@ManyToOne`. |
| **Asociación N:M en JPA** | `T-SPRING-04` | `F04` | `SpringLegacyAdapter` | Generación de la entidad intermedia `{First}{Second}`. |
| **Composición en JPA** | `T-SPRING-05` | `F06` | `SpringLegacyAdapter` | Inyección de `cascade = ALL` y `orphanRemoval = true`. |
| **Generalización / Herencia JPA** | `T-SPRING-06` | `F07` | `SpringLegacyAdapter` | Herencia con estrategia `InheritanceType.JOINED` sin duplicación de `@Id`. |
| **Colección Postman v2.1.0** | `T-POST-01` | `F01` | `PostmanExportDispatcher` | Generación del JSON conforme al esquema oficial Postman v2.1. |
| **Operaciones CRUD en Postman** | `T-POST-02` | `F01` | `PostmanExportDispatcher` | Emisión de endpoints estándar `GET`, `POST`, `PUT`, `DELETE`. |
| **Bodies Tipados de Ejemplo** | `T-POST-03` | `F01` | `PostmanExportDispatcher` | Valores mock acordes al tipo de atributo. |
| **Cobertura de Dominio en Postman** | `T-POST-04` | `F08` | `PostmanExportDispatcher` | Generación exhaustiva de carpetas para cada clase del modelo. |
| **Estructura Proyecto Flutter CRUD** | `T-FLUTTER-01` | `F01` | `FlutterExportModule` | Creación de `pubspec.yaml`, `main.dart`, `models`, `services`, `views`. |
| **Pantallas de Gestión CRUD Dart** | `T-FLUTTER-02` | `F01` | `FlutterExportModule` | Vistas de listado, formulario de captura y detalle por entidad. |
| **Selección de Claves Foráneas en UI** | `T-FLUTTER-03` | `F03` | `FlutterExportModule` | Dropdown y vinculación en formulario para relaciones foráneas. |
| **Protocolo de Señalización Colaborativa** | Documentado | N/A | `FastAPI ConnectionManager` (ASGI WS) | Sustitución de Django Channels preservando eventos `join`, `leave`, `announce`, `signal`. |
| **Telemetría y Arrastre en Canvas** | Documentado | N/A | `WebRTC DataChannel Client` | Retención de comunicación P2P para operaciones `move`, `resize`, `update_vertices`. |
| **Orquestación de IA Multimodal** | Documentado | `Gemini Sample` | `FastAPI Gemini Hub` (Structured Outputs) | Sustitución de regex heurístico por JSON Schema formal de Gemini. |

---

## 2. Regla de Regresión Cero

Durante la implementación posterior de los componentes V2 (`UML Domain Model V2`, adaptadores y FastAPI):
1. Todas las pruebas de caracterización de esta matriz **deben continuar ejecutándose y pasando exitosamente**.
2. Cualquier fallo en `T-FE-*`, `T-SPRING-*`, `T-POST-*` o `T-FLUTTER-*` representará una violación de compatibilidad regresiva y bloqueará la integración.
3. El `TransformationReport` downstream asegurará que las características no soportadas por los generadores legacy emitan diagnósticos explícitos en lugar de pérdidas silenciosas.
