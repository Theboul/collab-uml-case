# Secuencia de Migración y Estrategia de Ramas

Este documento detalla el plan de ejecución ordenado cronológicamente para la migración del sistema CASE, minimizando el acoplamiento y garantizando puntos de control estables a lo largo del proceso.

---

## 1. Estrategia de Ramas y Control de Versiones

Para asegurar la trazabilidad y la capacidad de restauración inmediata ante cualquier eventualidad:

```text
  (tag: v1.0.0-legacy-baseline)
            |
main -------o-------------------------------------------------> [Release v2.0]
             \                                                    ^
develop-v2    +---[Fase 1..3]---+---[Fase 4..6]---+---[Fase 7..9]-+
                   \             \             \
feature/            +--[cont.]    +--[fastapi]  +--[collab]
```

### Reglas de Git:
1. **Punto de Congelamiento (Baseline Tag)**:
   Antes de escribir la primera línea de código ejecutable, se creará una etiqueta inmutable en la rama principal:
   ```bash
   git tag -a v1.0.0-legacy-baseline -m "Baseline estable previo a la arquitectura v2 FastAPI"
   ```
2. **Rama de Integración Principal**:
   Se creará la rama `develop-v2` a partir de dicho tag. Todo el trabajo de modernización y coexistencia convergerá en `develop-v2`.
3. **Ramas de Funcionalidad (`feature/*`)**:
   Cada fase de la secuencia se desarrollará en una rama corta aislada (ej. `feature/contracts-definition`, `feature/fastapi-scaffolding`, `feature/persistence-migration`).
4. **Rama `main` Protegida**:
   `main` continuará reflejando la versión estable operable hasta que se completen todas las fases de migración y verificación integral.

---

## 2. Secuencia de Migración Detallada (10 Fases)

```text
[1. Congelar Baseline]
         |
[2. Documentar Contratos Legacy]
         |
[3. Definir UML Domain Model V2]
         |
[4. Inicializar FastAPI (backend_case)]
         |
[5. Migrar Persistencia y Proyectos]
         |
[6. Migrar Gestión de Lienzos]
         |
[7. Migrar Colaboración (WS + WebRTC Signaler)]
         |
[8. Migrar Orquestación IA (Gemini)]
         |
[9. Integrar Generadores (Spring Boot + Flutter)]
         |
[10. Retirar Django y Limpieza Final]
```

---

### Fase 1: Congelar Baseline y Crear Tag de Respaldo
* **Objetivo**: Asegurar el estado actual del repositorio para permitir comparación y rollback en cualquier momento.
* **Acciones**:
  * Ejecutar suite de pruebas actual (si existe).
  * Crear tag `v1.0.0-legacy-baseline`.
  * Crear rama `develop-v2`.

---

### Fase 2: Documentar y Extraer Contratos Legacy
* **Objetivo**: Formalizar las estructuras JSON que actualmente intercambian Angular, Django y Spring Boot.
* **Acciones**:
  * Crear directorio `contracts/`.
  * Documentar `contracts/uml-schema.v1.json` con base en el payload que recibe `back_generator_uml/src/main/resources/templates/`.
  * Documentar endpoints actuales de Django (`/api/backup/`, `/api/ai/`, señalización WS).

---

### Fase 3: Diseñar el UML Domain Model V2 Canónico
* **Objetivo**: Establecer el esquema agnóstico e independiente del metamodelo UML 2.5.
* **Acciones**:
  * Crear `contracts/uml-model.v2.json` definiendo entidades: `Package`, `Class`, `Attribute`, `Operation`, `Parameter`, `Generalization`, `Association`, `Multiplicity`, `Visibility`.
  * Diseñar adaptadores/mapeadores bidireccionales entre `uml-model.v2.json` y `uml-schema.v1.json` para no forzar cambios en Spring Boot.

---

### Fase 4: Inicializar Backend FastAPI (`backend_case`)
* **Objetivo**: Crear la estructura modular del nuevo backend sin tocar el código existente.
* **Acciones**:
  * Crear directorio `backend_case/` con gestor de dependencias moderno (`pyproject.toml` o Poetry/Pipenv).
  * Configurar ASGI con Uvicorn, FastAPI, Pydantic v2 y motor asíncrono de SQLAlchemy 2.
  * Configurar variables de entorno y conexión a PostgreSQL y Redis en puertos no conflictivos (`8001`).
  * Implementar endpoint de health check: `GET /api/v1/health`.

---

### Fase 5: Migrar Persistencia y Gestión de Proyectos
* **Objetivo**: Transferir el guardado y carga de proyectos desde Django a FastAPI.
* **Acciones**:
  * Definir modelos SQLAlchemy en FastAPI (`Project`, `Diagram`, `DiagramSnapshot`).
  * Generar migraciones Alembic para crear tablas aisladas en PostgreSQL (`case_projects`, `case_diagrams`).
  * Implementar operaciones CRUD de proyectos en FastAPI.
  * Habilitar flag en Angular para guardar y listar proyectos desde FastAPI.

---

### Fase 6: Migrar Gestión de Lienzos y Estado Visual
* **Objetivo**: Desacoplar la semántica del diagrama de las coordenadas gráficas de JointJS.
* **Acciones**:
  * En FastAPI, implementar endpoints para guardar y recuperar el estado visual (coordenadas `x, y`, posiciones de enlaces) como JSONB asociado al modelo semántico.
  * Ajustar el servicio de canvas en Angular para sincronizar periódicamente snapshots a FastAPI.

---

### Fase 7: Migrar Colaboración en Tiempo Real y Señalización
* **Objetivo**: Sustituir Django Channels por WebSockets nativos de FastAPI respaldados por Redis.
* **Acciones**:
  * Implementar `ConnectionManager` en FastAPI para administrar salas de diagramas concurrentes.
  * Adaptar el protocolo de señalización WebRTC para conectar a los pares mediante el nuevo endpoint WebSocket de FastAPI.
  * Implementar cerrojos efímeros de edición en Redis para evitar colisiones de edición simultánea de atributos.
  * Conectar el cliente de colaboración de Angular al nuevo WebSocket de FastAPI.

---

### Fase 8: Migrar Orquestación de IA (Gemini)
* **Objetivo**: Modernizar y centralizar la generación por lenguaje natural e imágenes.
* **Acciones**:
  * Implementar servicio de IA en FastAPI utilizando el SDK oficial `google-genai` de Python.
  * Utilizar salida estructurada (*Structured Outputs*) restringida por el esquema `contracts/uml-model.v2.json`.
  * Migrar endpoints de generación por texto, transcripción de voz y visión multimodal.
  * Redirigir el módulo de IA en Angular hacia FastAPI.

---

### Fase 9: Integrar Despacho de Generadores (Spring Boot y Flutter)
* **Objetivo**: Centralizar la exportación de código desde la API de FastAPI.
* **Acciones**:
  * Implementar en FastAPI el cliente HTTP hacia el generador Spring Boot (`POST http://localhost:7000/generate`), traduciendo el modelo v2 al contrato v1.
  * Portar o encapsular el generador Flutter CRUD (extraído de Django) dentro de FastAPI como módulo de exportación autónomo.
  * Actualizar los modales de exportación en Angular para descargar ZIPs desde FastAPI.

---

### Fase 10: Validación Integral y Retiro de Django
* **Objetivo**: Apagar de forma definitiva el backend legacy.
* **Acciones**:
  * Comprobar que no existan llamadas a los puertos de Django en los logs de red.
  * Ejecutar la checklist formal de retiro (definida en `docs/migration/legacy-retirement-criteria.md`).
  * Eliminar el contenedor y la carpeta `back_generador_bd/`.
  * Integrar `backend_case` como servicio principal en el `docker-compose.yml` consolidado.
