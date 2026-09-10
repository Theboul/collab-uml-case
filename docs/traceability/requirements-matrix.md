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
| **CU8** | Importar y exportar modelos UML | PA2: Interoperabilidad | `app/interoperability/` (Frontera de transformación Enterprise Architect) | N/A (PA1 aislado; `CU8 <<include>> CU9`) | *Por definir* | **Pendiente** (Decisión de formato físico en diseño) |
| **CU9** | Validar modelo UML | PA1 / Transversal | Reutilizado como guardián en `app/shared/errors/` | `validation.py` (`UMLValidator`, reglas VUML-01 a VUML-09) | `test_validator.py` (9 tests unitarios puros) | **Implementado en dominio** (Falta conectar como compuerta) |

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
