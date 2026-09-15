# Matriz de Trazabilidad de Requisitos — CASE UML (Examen 2)

**Fuente de Verdad Funcional:** `proyecto_actual.md` (SPEC MASTER).  
**Criterio Arquitectónico:** Modular Monolith + Ports & Adapters selectivo.  
**Regla de Dependencia:** $PA2 \rightarrow PA1$, $PA3 \rightarrow PA1$, jamás a la inversa. $PA4$ constituye un contexto cliente separado.

---

## 1. Contexto A — Herramienta CASE Colaborativa

### Iteración 1 — Núcleo del Modelador (PA1)

| CU | Funcionalidad | Área / Paquete | Componente Backend (`backend_case`) | Núcleo de Dominio (`core/uml_domain`) | Pruebas Asociadas | Estado |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CU1** | Crear nuevo lienzo UML | PA1: Gestión de Lienzos | `app/modeling/api/routes.py`<br>`app/modeling/application/canvas_service.py` | `model.py` (`Lienzo.crear_nuevo`)<br>`events.py` (`LienzoCreado`) | `test_modeling_api.py::test_create_canvas_cu1`<br>`test_lienzo_and_events.py` | **Implementado** (Persistencia relacional/JSONB y eventos) |
| **CU2** | Ingresar a lienzo existente | PA1: Gestión de Lienzos | `app/modeling/api/routes.py`<br>`app/modeling/infrastructure/canvas_repository.py` | `model.py` (`Lienzo`) | `test_modeling_api.py::test_get_canvas_cu2`<br>`test_get_nonexistent_canvas_returns_404` | **Implementado** (Recuperación íntegra y versionado) |
| **CU3** | Gestionar elementos del diagrama | PA1: Modelado UML | `app/modeling/api/routes.py`<br>`app/modeling/application/canvas_service.py` | `model.py` (`UmlDomainModel.agregar_clase`)<br>`events.py` (`ElementoAgregado`) | `test_modeling_api.py::test_add_class_cu3`<br>`test_add_duplicate_class_returns_422` | **Parcial** (Creación lista; modificación y borrado por completar) |
| **CU4** | Gestionar relaciones del diagrama | PA1: Modelado UML | `app/modeling/api/routes.py`<br>`app/modeling/application/canvas_service.py` | `model.py` (`agregar_asociacion`)<br>`adapters/multiplicity_parser.py` | `test_modeling_api.py::test_add_association_cu4`<br>`test_add_association_with_nonexistent_class_returns_404` | **Parcial** (Creación lista; modificación y borrado por completar) |

---

### Iteración 2 — Colaboración e Interoperabilidad (PA2)

| CU | Funcionalidad | Área / Paquete | Componente Backend (`backend_case`) | Núcleo de Dominio (`core/uml_domain`) | Pruebas Asociadas | Estado |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CU5** | Colaborar en la edición | PA2: Colaboración | `app/collaboration/` (pendiente de implementar según ADR-0003: endpoint WebSocket + LockStore) | N/A (PA1 aislado) | Sin pruebas del mecanismo aprobado todavía — pendiente a medida que se implemente el roadmap de ADR-0003 | **No implementado en el stack activo (X6)** — solo un No-Op gateway confirmado; ADR-0003 aprobado, implementación pendiente siguiendo el roadmap de 4 pasos |
| **CU8** | Importar y exportar modelos UML | PA2: Interoperabilidad | `app/interoperability/api/routes.py` (`POST /canvases/import`, `GET /canvases/{id}/export/xmi`)<br>`app/interoperability/application/xmi_mapping.py`, `xmi_import_service.py` | N/A (PA1 aislado; `CU8 <<include>> CU9` — reutiliza `UMLValidator` antes de persistir un import) | `test_cu08_import_export.py` (5 tests: import del XMI real de EA, XML malformado → 422, export bien formado, round-trip export→import semánticamente equivalente, 403 `CANVAS_ACCESS_FORBIDDEN` en export) | **Implementado (MVP)** — formato confirmado XMI 1.1/UML 1.3 (dialecto real de Enterprise Architect 2.5, verificado contra `docs/spec/ejemplo de diagrama de clases ea.xml`). Cubre clases/atributos/operaciones/parámetros/asociaciones/layout x-y. Generalización: export implementado, import sin verificar contra un archivo real (no hay ejemplo con herencia todavía). Fuera de alcance documentado: interfaces/enumeraciones/dataTypes-como-tipo-real/dependencias/realizaciones (sin soporte en `mappers.py` ni en `contracts/uml-model.v2.json` hoy) y geometría fina de aristas. Sin UI de frontend todavía. |
| **CU9** | Validar modelo UML | PA1 / Transversal | `app/modeling/api/routes.py` (`POST /canvases/{canvas_id}/validate`)<br>`app/modeling/application/canvas_service.py` (`CanvasService.validar_lienzo`)<br>`app/application/mappers.py` (`ValidationResultMapper`, reutilizado también por `UmlApplicationService`) | `validation.py` (`UMLValidator`, pipeline de funciones `_rule_*` sobre `ValidationContext`; reglas VUML-01 a VUML-07 y VUML-09 a VUML-12) | `test_validator.py` (9 tests unitarios puros, sin modificar)<br>`test_canvas_validation.py` (5 tests: modelo válido, ciclo de herencia vía VUML-07, 404, 403 sin acceso, no-mutación del modelo) | **Implementado y conectado como compuerta** — endpoint de solo lectura sobre el modelo persistido, mismo control de acceso que `GET /{canvas_id}`. Pendiente (fuera de esta fase): VUML-08 y VUML-13 documentados en `docs/domain-model/validation-rules.md` sin implementar; `ValidationSeverity.INFO` disponible en el dominio sin ninguna regla que lo emita todavía. |

---

### Iteración 3 — Automatización y Generación (PA3)

| CU | Funcionalidad | Área / Paquete | Componente Backend (`backend_case`) | Generadores / Servicios | Pruebas Asociadas | Estado |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CU6** | Gestionar mediante texto o voz | PA3: Asistencia IA | `app/assistant/` (con puerto `AiCommandInterpreter`) | Entrada $\rightarrow$ `ComandoModelado` $\rightarrow$ `Validador` $\rightarrow$ PA1 | `test_legacy_parity_api.py::test_chatbot_success` | **Parcial** (IA operativa; pendiente estructuración en `ComandoModelado`) |
| **CU7** | Generar desde imagen | PA3: Asistencia IA | `app/assistant/` (`AnalizadorDiagramaImagen`) | Imagen $\rightarrow$ `PropuestaModelo` $\rightarrow$ Validación $\rightarrow$ Confirmación | `test_legacy_parity_api.py::test_uml_from_image` | **Parcial** (Detección operativa; pendiente flujo formal de `PropuestaModelo`) |
| **CU10** | Generar backend Spring Boot | PA3: Generación | `app/generation/` (`SpringGeneratorPort`) | Modelo UML $\rightarrow$ `EspecificacionBackend` $\rightarrow$ Java/Spring Boot 3 | `test_spring_generator_characterization.py` (6 tests de integración) | **Implementado** (Generador Java 3.3.3 funcional) |
| **CU11** | Generar artefactos Postman | PA3: Generación | `app/generation/` (`PostmanGeneratorPort`) | `EspecificacionBackend` $\rightarrow$ Colección Postman v2.1 | `test_postman_generator_characterization.py` (4 tests) | **Implementado** (`PostmanCollectionGenerator.java`) |

---

## 2. Contexto B — Aplicación Móvil de Gestión (PA4)

> [!NOTE]
> La aplicación móvil **NO es generada por el CASE**. Constituye un artefacto de evaluación independiente que se adapta al backend Spring Boot generado por CU10.

| CU | Funcionalidad | Área / Paquete | Componente Cliente Móvil | Pruebas Asociadas | Estado |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CU12** | Ejecutar aplicación móvil de gestión | PA4: Aplicación Móvil | `mobile_app_reference/` (Estructura base Dart / Flutter) | `test_flutter_generator_characterization.py` | **Scaffolding disponible** (Listo para adaptarse en evaluación) |
| **CU13** | Trabajar offline y sincronizar | PA4: Operación Local | Persistencia local (SQLite) + cola `OperacionPendiente` + sync | *Por diseñar en PA4* | **Pendiente de diseño** (Estrategia de conflictos) |
| **CU14** | Operar mediante asistente de voz local | PA4: Operación Local | Audio $\rightarrow$ ReconocedorLocal $\rightarrow$ `ComandoMovil` $\rightarrow$ Gestor | *Por diseñar en PA4* | **Pendiente de diseño** (Motor on-device sin cloud) |
