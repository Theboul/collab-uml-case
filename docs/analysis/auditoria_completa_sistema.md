# Informe de Auditoría Integral del Sistema CASE UML (SchemaCraft)
**Fecha:** 13 de Septiembre de 2026  
**Alcance:** Backend (`backend_case`, `core/uml_domain`), Frontend (`front_generador_bd`), Infraestructura, Seguridad, Pruebas y Trazabilidad (CU1–CU14)  
**Versión del Sistema:** 2.0.0 (FastAPI + Angular 20 + AntV X6)  
**Normativa de Referencia:** `AGENTS.md`, `requirements-matrix.md`, ADRs (`0003`, `0005`, `0007`), `SPEC MASTER (proyecto_actual.md)`.

---

## 1. Resumen Ejecutivo y Cuadro de Mando

El sistema se encuentra en una etapa de **transición arquitectónica avanzada**. Se ha logrado con éxito el desacoplamiento de la biblioteca de dominio puro (`core/uml_domain`), la migración de las operaciones clave de modelado y autenticación a FastAPI (`backend_case`) y la modernización del canvas interactivo a AntV X6 sobre Angular 20.

No obstante, la auditoría revela **puntos ciegos críticos**: convivencia de dos motores gráficos y dos bases de datos, omisión de la compuerta de validación obligatoria en endpoints de IA heredados, 438 errores de ESLint, 285 errores de Mypy y un fallo de empaquetado que bloquea la ejecución unificada de Pytest.

### 1.1 Cuadro de Salud General

| Área Evaluada | Calificación | Estado | Veredicto |
| :--- | :---: | :---: | :--- |
| **Aislamiento de Dominio (`core/uml_domain`)** | **10 / 10** | 🟢 EXCELENTE | 100% puro. Zero frameworks. Cobertura completa de reglas UML 2.5. |
| **Límites de Archivo (RULE-CODE-QUALITY)** | **10 / 10** | 🟢 CUMPLIDO | 259/259 archivos < 1000 líneas. No hay God Objects monolíticos. |
| **Compilación Frontend (`ng build`)** | **10 / 10** | 🟢 EXITOSO | Bundle Angular 20 SSR compila sin errores bloqueantes. |
| **Autenticación e Identidad (ADR-0005)** | **9.0 / 10** | 🟢 MUY BUENO | JWT híbrido, cookies HttpOnly, rotación, roles Anfitrión/Colaborador. |
| **Arquitectura Backend (`backend_case`)** | **7.5 / 10** | 🟡 ACEPTABLE | Modular Monolith en marcha, pero con módulos vacíos y duplicidad de apps. |
| **Suite de Pruebas Pytest** | **7.0 / 10** | 🟡 PARCIAL | 125 tests pasan por separado; falla la ejecución global por falta de `__init__.py`. |
| **Tipado Estático Python (Mypy)** | **5.0 / 10** | 🔴 CRÍTICO | 285 errores de tipos (desajustes SQLAlchemy `Column` vs tipos nativos). |
| **Linter Python (Ruff)** | **6.0 / 10** | 🟡 REGULAR | 275 violaciones de estilo y anotaciones obsoletas (140 auto-reparables). |
| **Linter Frontend (ESLint)** | **3.5 / 10** | 🔴 CRÍTICO | 438 errores bloqueantes, concentrados en `src/services/` legados. |
| **Consistencia de UI y Shells** | **6.5 / 10** | 🟡 PARCIAL | Falta `ProjectShellComponent`, `sc-modal-shell` y `sc-code-block`. |

---

## 2. Clasificación de Severidad de Hallazgos

| Nivel | Cantidad | Descripción |
| :--- | :---: | :--- |
| 🔴 **CRÍTICO** | **4** | Bloquean pipelines de CI/CD, violan reglas duras de arquitectura o comprometen la integridad de datos. |
| 🟠 **ALTO** | **5** | Deuda técnica estructural, bifurcación de persistencia o funcionalidades de CU incompletas. |
| 🟡 **MEDIO** | **6** | Componentes de UI faltantes, dependencias obsoletas en bundle, tipografía/nomenclatura. |
| 🔵 **BAJO / INFO** | **4** | Advertencias de empaquetado ESM/CommonJS, warnings de deprecación de dependencias. |

---

## 3. Catálogo Detallado de Hallazgos y Vulnerabilidades

### 🔴 Hallazgos Críticos

#### [BUG-CRIT-01] Fallo de Importación en Suite Global de Pruebas Pytest
* **Ubicación:** `tests/domain_model/test_end_to_end_compatibility.py:16`
* **Descripción:** Al ejecutar `python -m pytest`, la prueba intenta importar:
  ```python
  from tests.spring_generator.test_spring_generator_characterization import SpringGeneratorSimulator
  ```
  Esto lanza `ModuleNotFoundError: No module named 'tests.spring_generator'`.
* **Causa Raíz:** El directorio `tests/` y su subdirectorio `tests/spring_generator/` carecen de archivos `__init__.py`. Al tener `pytest.ini` con `--import-mode=importlib`, Python no reconoce `tests` como un paquete regular durante la recolección global.
* **Impacto:** Falla la integración continua (Quality Gate del DoD). Paradójicamente, si se corren `backend_case/tests` (68 tests) y `tests/domain_model` (45 tests) de forma aislada, todos pasan.
* **Remediación:** Crear `tests/__init__.py` y `tests/spring_generator/__init__.py`.

#### [BUG-CRIT-02] Violación de la Regla No Negociable de Asistencia IA (CU6 / CU7)
* **Ubicación:** `backend_case/app/legacy/api_router.py:29-63` y `170-220`
* **Descripción:** Los endpoints `/api/chatbot/` y `/api/uml_from_image/` invocan directamente a `call_gemini()` o `call_gemini_from_image()`, parsean el texto markdown con expresiones regulares y devuelven el JSON directamente al cliente sin validación alguna.
* **Violación de Estándar:** Contraviene explícitamente `AGENTS.md` §5:
  > *"Toda salida de IA es tratada como NO CONFIABLE y DEBE pasar por validación antes de tocar el dominio (...) Ninguna función puede modificar el modelo sin pasar por ValidadorComandoModelado / ValidadorModelo"*.
* **Impacto:** Si Gemini genera identificadores rotos, clases sin nombre o tipos SQL incompatibles, estos se inyectan en el estado del diagrama sin verificación semántica. Además, el módulo canónico `backend_case/app/assistant/` permanece como un cascarón vacío.
* **Remediación:** Implementar el puerto `AiCommandInterpreter` en `app/assistant/`, migrar la llamada hacia allí y forzar el paso por `UMLValidator.validate()` antes de emitir respuesta.

#### [BUG-CRIT-03] 438 Errores de ESLint Bloqueando el Quality Gate Frontend
* **Ubicación:** `front_generador_bd/src/services/**` (múltiples archivos)
* **Descripción:** La ejecución de `pnpm run lint` arroja **438 errores**.
* **Distribución de Errores:**
  * `@typescript-eslint/no-explicit-any`: 312 ocurrencias (uso sistemático de `any` en servicios legados).
  * `@angular-eslint/prefer-inject`: 48 ocurrencias (inyección por constructor en lugar de `inject()`).
  * `@typescript-eslint/no-unused-vars`: 52 ocurrencias (imports y variables muertas).
  * `@typescript-eslint/no-inferrable-types`: 26 ocurrencias.
* **Causa Raíz:** Los servicios legados en `src/services/` (creados para el diagrama anterior) no fueron refactorizados bajo las reglas de TypeScript strict de Angular 20.
* **Impacto:** Incumplimiento del Definition of Done (DoD).
* **Remediación:** Si `src/services/` solo atiende al diagrama legacy (`/legacy-diagram`), excluir temporalmente esa ruta en `eslint.config.js` o tipar dichos servicios mediante DTOs.

#### [BUG-CRIT-04] 285 Errores de Mypy en Backend (`backend_case`)
* **Ubicación:** `backend_case/app/modeling/infrastructure/canvas_repository.py`, `db_models.py`, `routes.py`
* **Descripción:** `python -m mypy backend_case/app core/uml_domain` arroja **285 errores**.
* **Causa Raíz:**
  1. En `db_models.py:51`, `Invalid base class "Base"`.
  2. En `canvas_repository.py`, asignación de tipos primitivos (`str`, `dict`, `datetime`) a variables tipadas internamente como `Column[T]` en SQLAlchemy 2.0 sin los plugins de Mypy adecuados (`sqlalchemy.ext.mypy.plugin`).
  3. Paso de atributos ORM (`canvas.version`) a DTOs (`CanvasResult(version=canvas.version)`) donde el constructor espera `int` y recibe `Column[int]`.
  4. Funciones de router en `modeling/api/routes.py` sin tipo de retorno anotado (`[no-untyped-def]`).
* **Remediación:** Configurar el plugin de SQLAlchemy en `pyproject.toml`, tipar los retornos explícitos de los endpoints y tipar las conversiones de modelos ORM a objetos de dominio.

---

### 🟠 Hallazgos Altos

#### [BUG-HIGH-01] Persistencia Dividida: Doble Base de Datos SQLite en Ejecución
* **Ubicación:** `backend_case/app/main.py:40-51`, `shared/db/base.py`, `legacy/database.py`
* **Descripción:** Durante el ciclo de vida (`lifespan`), se ejecutan dos rutinas independientes:
  1. `await init_db()`: crea `shared_case.db` (tablas `canvases`, `users`, `user_identities`, `user_sessions`, `project_collaborators`).
  2. `await init_legacy_db()`: crea `legacy_uml.db` (tabla `backup_uml_records`).
* **Impacto:** Fragmentación del almacenamiento. Si se consulta un backup o se guarda un snapshot desde rutas legacy, los datos van a un archivo SQLite distinto al que gestiona los lienzos V2, impidiendo la sincronización y auditoría homogénea.
* **Remediación:** Unificar `BackupUMLRecord` bajo el `Base` canónico de `shared/db/base.py` y eliminar el motor secundario de `legacy/database.py`.

#### [BUG-HIGH-02] Coexistencia Híbrida de Motores Gráficos en Frontend (JointJS vs AntV X6)
* **Ubicación:** `front_generador_bd/package.json`, `src/app/diagram/`, `src/app/features/modeling/`
* **Descripción:** En `package.json` coexisten `@antv/x6` (^2.19.2) y `jointjs` (^3.7.7). La aplicación mantiene dos editores simultáneos:
  * `/diagram/:roomId` $\rightarrow$ Nuevo editor X6 (`UmlEditorComponent`).
  * `/legacy-diagram/:roomId` $\rightarrow$ Editor legado JointJS (`Diagram`).
* **Impacto:** Sobrecarga severa del tamaño del bundle (`chunk-4RX72WQL.js` añade 640 kB de JointJS). Además, incluye dependencias CommonJS obsoletas (`jquery`, `backbone`) que impiden tree-shaking óptimo.
* **Remediación:** Establecer fecha de congelación/deprecación para `/legacy-diagram`, desinstalar `jointjs`, `jquery` y `backbone`, y retirar `src/app/diagram/` y `src/app/side-panel/`.

#### [BUG-HIGH-03] Ausencia de `ProjectShellComponent` (Violación de AGENTS.md §4.3)
* **Ubicación:** `front_generador_bd/src/app/layout/`
* **Descripción:** `AGENTS.md` §4.3 exige explícitamente:
  > *"Todas las vistas que viven dentro de un proyecto abierto (...) comparten un solo layout component: `ProjectShellComponent` con un sidebar izquierdo de navegación (`<sc-project-sidebar>`) y un header/toolbar superior (`<sc-project-toolbar>`)"*.
* **Estado Actual:** En `src/app/layout/` solo existe `app-shell/`. El nuevo editor `UmlEditorComponent` dibuja su propia toolbar, paleta y layout de manera autocontenida sin usar un cascarón de proyecto común.
* **Impacto:** Si se agregan nuevas pantallas internas (como Editor SQL, Snapshots o Configuración de Esquema), se duplicarán menús y cabeceras en lugar de reutilizar un shell compartido.

#### [BUG-HIGH-04] Duplicidad de Capa de Aplicación en Backend (`app/application/` vs `app/modeling/application/`)
* **Ubicación:** `backend_case/app/application/`
* **Descripción:** Coexiste un directorio `backend_case/app/application/` huérfano con `mappers.py` y `services.py` (`UmlApplicationService`), al mismo tiempo que existe `backend_case/app/modeling/application/` (`canvas_service.py`).
* **Impacto:** Confusión arquitectónica sobre dónde deben residir los servicios de aplicación y mappers de modelos UML.
* **Remediación:** Reubicar `services.py` y `mappers.py` dentro de `app/modeling/application/` o `app/shared/mappers/` y eliminar la carpeta redundante.

#### [BUG-HIGH-05] Módulos de Generación e Interoperabilidad Vacíos
* **Ubicación:** `backend_case/app/generation/`, `backend_case/app/interoperability/`
* **Descripción:** Ambos paquetes contienen únicamente `__init__.py`. Los generadores reales residen en `back_generator_uml/` (Java Spring Boot) y `backend_case/app/legacy/flutter_generator.py`, pero la API FastAPI no tiene puertos formales expuestos en V2.
* **Impacto:** CU10 y CU11 solo son consumibles mediante procesos externos o scripts, no como servicios integrados en la API Gateway V2.

---

### 🟡 Hallazgos Medios

#### [BUG-MED-01] Componentes Compartidos Faltantes en `shared/ui`
* **Ubicación:** `front_generador_bd/src/app/shared/ui/`
* **Descripción:** Según `AGENTS.md` §4.4, la lista mínima de componentes compartidos debe incluir:
  * `sc-modal-shell`
  * `sc-code-block` (bloque con line numbers y syntax highlight)
* **Estado Actual:** No están implementados. Actualmente los modales (`new-project-modal`, `join-project-modal`, `uml-share-modal`) implementan su propio contenedor `<div>` con clases inline.
* **Remediación:** Crear `<sc-modal-shell>` y `<sc-code-block>` en `shared/ui/` y refactorizar los modales existentes.

#### [BUG-MED-02] Error Tipográfico en Ruta y Módulo: `landin-page`
* **Ubicación:** `front_generador_bd/src/app/landin-page/` y `app.routes.ts:14`
* **Descripción:** El componente y la ruta fueron nombrados `landin-page` en lugar de `landing-page`.
* **Impacto:** Falta de prolijidad en el código y en las rutas expuestas (`/legacy-landing`).

#### [BUG-MED-03] Warnings de Optimización por Módulos CommonJS en Angular 20
* **Ubicación:** `ng build` output:
  * `Module 'jquery' used by 'jointjs' is not ESM`
  * `Module 'backbone' used by 'jointjs' is not ESM`
  * `Module 'file-saver' used by 'backend-generator.service.ts' is not ESM`
* **Impacto:** Los módulos CommonJS causan *optimization bailouts* (impiden a esbuild eliminar código no utilizado en producción).
* **Remediación:** Eliminar JointJS y reemplazar `file-saver` por la API nativa del navegador (`HTMLAnchorElement.download` o `showSaveFilePicker`).

#### [BUG-MED-04] Linter Python (Ruff): 275 Violaciones de Estilo
* **Ubicación:** `core/uml_domain/validation.py`, `model.py`, `backend_case/app/**`
* **Descripción:** Infracciones masivas de:
  * `UP035`: Uso de `typing.Dict`, `typing.List` y `typing.Tuple` en Python 3.12+ (debe usarse `dict`, `list`, `tuple`).
  * `UP017`: Uso de `datetime.timezone.utc` en lugar del alias moderno `datetime.UTC`.
  * `UP042`: Clases Enum heredando de `(str, Enum)` en vez de `enum.StrEnum`.
  * `E501`: Líneas que exceden los 100 caracteres reglamentarios.
* **Remediación:** Ejecutar `python -m ruff check --fix backend_case core` y ajustar las líneas extensas.

#### [BUG-MED-05] Mutaciones Granulares de CU3/CU4 Incompletas vía Eventos
* **Ubicación:** `backend_case/app/modeling/api/routes.py`
* **Descripción:** La creación de clases y relaciones está completamente implementada. Sin embargo, la edición de propiedades de una clase existente (renombrar clase, cambiar tipo de atributo, editar multiplicidad de relación existente) o el borrado granular aún no tienen endpoints dedicados en `/api/v2/canvases/{id}/...`. Actualmente dependen de la sobreescritura completa del canvas (`execute_command` o snapshot).
* **Remediación:** Completar los endpoints REST granulares para actualizar/eliminar elementos y relaciones.

#### [BUG-MED-06] Inyección de Dependencias Legacy en Servicios Frontend
* **Ubicación:** `front_generador_bd/src/app/app.config.ts:19-21`
* **Descripción:** `DiagramService`, `FallbackService` y `RelationshipService` se registran explícitamente en el arreglo `providers` de `appConfig` y usan inyección por constructor, en lugar de utilizar `{ providedIn: 'root' }` y la función `inject()`.

---

### 🔵 Hallazgos Bajos / Informativos

#### [INFO-01] Advertencias de Deprecación en Pruebas con FastAPI / Starlette
* **Ubicación:** Salida de Pytest:
  * `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`
  * `StarletteDeprecationWarning: HTTP_422_UNPROCESSABLE_ENTITY is deprecated. Use HTTP_422_UNPROCESSABLE_CONTENT instead.`
* **Acción:** Actualizar las aserciones de código de estado en pruebas a `status.HTTP_422_UNPROCESSABLE_CONTENT` o 422 numérico.

#### [INFO-02] Inconsistencia en Puerto de Desarrollo
* **Ubicación:** `backend_case/README.md` indica puerto 8001, mientras que `front_generador_bd/src/environments/environment.development.ts` apunta al puerto 8000 (`wsPort = 8000`).
* **Acción:** Unificar la documentación para indicar el puerto 8000 de manera canónica.

---

## 4. Estado de Cumplimiento de Casos de Uso (Trazabilidad)

```
[CU1: Crear Lienzo]            ==== 100% ==== [IMPLEMENTADO]
[CU2: Ingresar a Lienzo]       ==== 100% ==== [IMPLEMENTADO]
[CU3: Gestionar Elementos]     ====  70% ==== [PARCIAL: Creación lista, edición/borrado pendiente]
[CU4: Gestionar Relaciones]    ====  70% ==== [PARCIAL: Creación lista, edición/borrado pendiente]
[CU5: Colaboración Concurrente]====  50% ==== [EN PROGRESO: WS y presencia listos, LockStore pendiente]
[CU6: Asistente Texto/Voz]     ====  40% ==== [PARCIAL: Operativo en legacy, falta compuerta V2]
[CU7: Asistente Imagen]        ====  40% ==== [PARCIAL: Operativo en legacy, falta compuerta V2]
[CU8: Interoperabilidad XMI]   ====   0% ==== [PENDIENTE: Especificación lista, sin código]
[CU9: Validar Modelo UML]      ==== 100% ==== [IMPLEMENTADO: Dominio y API REST]
[CU10: Generador Spring Boot]  ==== 100% ==== [IMPLEMENTADO: Generador Java probado]
[CU11: Generador Postman]      ==== 100% ==== [IMPLEMENTADO: Generador Java probado]
[CU12: App Móvil Gestión]      ====  30% ==== [SCAFFOLDING: Plantilla Flutter lista]
[CU13: Sync Offline Móvil]     ====   0% ==== [CONGELADO: En espera de ADR-0004]
[CU14: Voz Local Móvil]        ====   0% ==== [PENDIENTE: Sin diseño on-device]
```

---

## 5. Plan de Remediación y Hoja de Ruta Priorizada

### Fase 1: Desbloqueo de Quality Gates y Pruebas (Prioridad Inmediata)
- [ ] **P1.1**: Crear `tests/__init__.py` y `tests/spring_generator/__init__.py`. Verificar que `python -m pytest` ejecute y apruebe los 125 tests.
- [ ] **P1.2**: Ejecutar `python -m ruff check --fix backend_case core` para subsanar automáticamente los 140 errores de sintaxis y tipado moderno.
- [ ] **P1.3**: Configurar `front_generador_bd/eslint.config.js` para ignorar `src/services/**` provisionalmente o tipar los parámetros `any` críticos.

### Fase 2: Integridad Arquitectónica y Seguridad (Alta Prioridad)
- [ ] **P2.1**: **Blindar IA (CU6/CU7)**: Crear `AiCommandInterpreter` en `backend_case/app/assistant/`. Enrutar la salida de Gemini obligatoriamente por `UMLValidator.validate()` antes de responder al frontend.
- [ ] **P2.2**: **Unificar Persistencia**: Mover `BackupUMLRecord` a `shared/db/base.py` y desmantelar `legacy_uml.db`.
- [ ] **P2.3**: **Corregir Mypy**: Configurar el plugin de SQLAlchemy en `pyproject.toml` y tipar los modelos de `canvas_repository.py`.

### Fase 3: Consistencia y Limpieza de Frontend (Media Prioridad)
- [ ] **P3.1**: Implementar `ProjectShellComponent` en `src/app/layout/project-shell/` y alojar allí la navegación de proyecto.
- [ ] **P3.2**: Crear `<sc-modal-shell>` y `<sc-code-block>` en `src/app/shared/ui/`.
- [ ] **P3.3**: Desinstalar `jointjs`, `jquery` y `backbone`. Remover `src/app/diagram/` y `src/app/side-panel/`. Corregir nombre de `landin-page` a `landing-page`.

### Fase 4: Avance de Casos de Uso Pendientes
- [ ] **P4.1 (CU5)**: Implementar Paso 3 de ADR-0003: `LockStore` sobre Redis para control granular de elementos concurrentes.
- [ ] **P4.2 (CU8)**: Diseñar el adaptador de importación/exportación XMI en `app/interoperability/`.
