# Matriz de Responsabilidades y Subsistemas de la Arquitectura

Este documento establece de forma exhaustiva las responsabilidades funcionales, los límites técnicos y el desacoplamiento entre cada subsistema de la arquitectura objetivo y de transición.

---

## 1. Frontend Angular (`front_generador_bd`)

El frontend Angular 20 debe conservarse inicialmente, sirviendo como interfaz gráfica unificada para el usuario.

### A. Elementos a Conservar Inicialmente
* **JointJS (v3.7.7) como Motor de Renderizado Gráfico**: Conservar el lienzo interactivo, la manipulación de formas visuales (rectángulos de clases, conectores de asociación/herencia/composición) y la detección de eventos de arrastre.
* **Cliente WebRTC DataChannel**: Conservar para la sincronización P2P instantánea y de ultra-baja latencia de coordenadas de punteros y movimiento interactivo en sesiones colaborativas.
* **Módulos UI de Captura Multimodal**: Conservar la captura de audio (`SpeechRecognitionService`), el selector de imágenes de bocetos y los modales de exportación.

### B. Elementos a Refactorizar Progresivamente
1. **Desacoplamiento del Modelo UML respecto a JointJS**:
   * *Estado actual*: El modelo semántico está embebido en atributos internos de las celdas de JointJS (`cell.get('attributes')`, SVG styling, `custom.ClassElement`).
   * *Refactorización*: Separar formalmente el estado del modelo (`UmlDomainModel`) del estado visual del canvas (`JointJSPresenter`). La UI de JointJS será una proyección visual del modelo semántico.
2. **Capa de Servicios HTTP**:
   * Modificar `environment.ts` para permitir el enrutamiento selectivo de peticiones: endpoints legados hacia Django (`http://localhost:8000/api/legacy`) y endpoints migrados hacia FastAPI (`http://localhost:8001/api/v1`).
3. **Servicios WebSocket**:
   * Reemplazar la señalización acoplada a Django Channels por un cliente WebSocket estándar compatible con el gestor de salas ASGI de FastAPI.
4. **Despacho de Exportaciones**:
   * Enrutar las solicitudes de descarga de código hacia la API de FastAPI en lugar de llamar directamente a scripts dispersos o a Django.

---

## 2. Backend Django Legacy (`back_generador_bd`)

Django 5.2.6 se clasifica formalmente como **backend legacy en modo mantenimiento** durante el período de transición.

### Responsabilidades Temporales Mantenidas
1. **Señalización WebRTC Legacy**: Servir provisionalmente como canal de señalización para clientes que no hayan migrado al nuevo protocolo de salas.
2. **Generador Flutter CRUD Existente**: Mantener la ejecución del módulo `apps/generator` (generador de 2,689 líneas que crea el código Dart para pantallas CRUD) mientras se valida su desacoplamiento o integración final.
3. **Módulo de Backups Existente**: Proporcionar persistencia temporal de esquemas si algún cliente aún apunta a sus endpoints antiguos.
4. **Endpoints de Gemini Existentes**: Servir como fallback para la generación de diagramas por texto/imagen hasta que FastAPI estabilice su propio hub de orquestación de IA.

---

## 3. Futuro Backend FastAPI (`backend_case`)

FastAPI asumirá de forma definitiva el rol de **API Gateway y orquestador de aplicación**. Es crucial destacar que **FastAPI no contiene las reglas de dominio ni las validaciones del metamodelo UML; las coordina**, delegando la lógica de negocio al motor de dominio puro (`UML Domain Engine`):

### Responsabilidades Clave
1. **Coordinación de Flujos de Negocio**: Administración del ciclo de vida de los proyectos, versionado de diagramas y control de acceso.
2. **Orquestación del UML Domain Engine & Validación 2.5**:
   * Invoca al motor de dominio puro para la validación estricta de restricciones de metamodelo UML 2.5 (detección de ciclos de herencia en DAG, nombres de atributos duplicados, coherencia de multiplicidades, tipos de visibilidad válidos).
   * Ejecuta la verificación de perfiles de compatibilidad antes de autorizar exportaciones a generadores.
3. **Persistencia Centralizada y Versionado**:
   * Persistencia estructurada en PostgreSQL con esquema relacional normalizado + snapshots JSONB para restauración instantánea.
4. **Colaboración y Control de Concurrencia**:
   * Control de sesiones de 2 a 3 participantes concurrentes.
   * Gestión de cerrojos de edición pesada (edición modal de atributos/métodos) para evitar colisiones de edición simultánea.
5. **Orquestación de IA Multimodal (Gemini Hub)**:
   * Consumo del SDK oficial de Google GenAI usando salida estructurada (JSON Schema estricto).
   * Generación y ajuste de diagramas a partir de texto, notas de voz e imágenes de bocetos en pizarra.
6. **Interoperabilidad y Dispatcher de Generadores**:
   * Conversión del modelo canónico al contrato requerido por el generador Spring Boot (`POST /generate`) mediante adaptadores downstream con auditoría de no pérdida de datos.
   * Orquestación de la generación del cliente Flutter CRUD.

---

## 4. Rol del Generador Spring Boot (`back_generator_uml`)

El generador Spring Boot 3.5.5 es un subsistema maduro y altamente especializado que transforma un esquema de clases UML en:
1. Una aplicación Spring Boot funcional (Java 21, Spring Data JPA, Controladores REST, Servicios y Repositorios).
2. Una colección de pruebas de Postman v2.1.0 lista para importar y validar el backend generado.

### Análisis de Estrategias de Integración desde FastAPI:

| Alternativa | Descripción | Viabilidad | Evaluación Técnica |
| :--- | :--- | :--- | :--- |
| **A. Llamar por HTTP REST** | FastAPI invoca `POST http://localhost:7000/generate` enviando el JSON `UmlSchema` y recibe un ZIP en streaming. | **RECOMENDADA** | Máximo desacoplamiento, cada servicio corre en su propio runtime óptimo (JVM vs Python), sin dependencias cruzadas de compilación. |
| **B. Ejecución directa del JAR** | FastAPI ejecuta `java -jar generator.jar --input model.json` mediante subprocess. | Desaconsejada | Lenta (arranque de JVM en cada llamada: 2-4 seg overhead), frágil manejo de procesos concurrentes, requiere JVM instalada en el contenedor de FastAPI. |
| **C. Compartir contrato JSON directo** | FastAPI escribe en volumen compartido y Spring Boot vigila la carpeta. | Desaconsejada | Complejidad innecesaria de sincronización, polling y permisos de archivos en disco. |

> [!TIP]
> **Recomendación Final: Opción A + C (Llamada HTTP sobre Contrato Formal)**.
> FastAPI actúa como cliente HTTP llamando al endpoint existente `/generate` del servicio Spring Boot, enviando el payload conforme al contrato estandarizado en `contracts/uml-schema.v1.json`.

---

## 5. Rol del Generador Flutter

Es imperativo aclarar formalmente la naturaleza de este componente:
* **NO es una aplicación móvil del modelador CASE**: No permite arrastrar cajas ni editar diagramas en dispositivos móviles.
* **ES un generador de código de aplicaciones de gestión CRUD**: Produce un proyecto completo de Flutter en lenguaje Dart con pantallas de listado, creación, edición y detalle para las entidades modeladas en el diagrama UML, listas para interactuar con las APIs generadas por Spring Boot.

### Integración con el Nuevo Modelo UML:
En la arquitectura objetivo, el generador Flutter se integrará como un módulo de plantillas en FastAPI (o microservicio de exportación), alimentado por el mismo contrato canónico `UmlSchema` validado, asegurando que las clases, tipos de datos y relaciones del diagrama se traduzcan limpiamente a clases Dart y vistas móviles.

---

## 6. Rol de PostgreSQL

PostgreSQL 15+ se establece como la **única fuente de persistencia transaccional y duradera**:
* **Proyectos y Metadatos**: Identificadores, nombres, propietarios, fechas de modificación y permisos.
* **Lienzos (Canvases)**: Definición de lienzos asociados a un proyecto.
* **Modelo Semántico UML**: Persistencia canónica de entidades (clases, atributos, tipos, métodos, visibilidades, asociaciones, herencias).
* **Snapshots de Estado Visual**: Coordenadas espaciales de JointJS (`x, y`, ancho, alto, puntos de quiebre de conectores) persistidas como `JSONB` versionado para restaurar la apariencia visual exacta al abrir el proyecto.
* **Registro de Sesiones de Colaboración**: Historial de usuarios autorizados y auditoría básica de cambios.

---

## 7. Rol de Redis

Redis 7 se utilizará estrictamente para funciones de alta velocidad y estado efímero:
* **Canal Pub/Sub para Servidores WebSocket**: Permite escalar horizontalmente las instancias de FastAPI ASGI garantizando la difusión de eventos en tiempo real entre múltiples trabajadores.
* **Presencia de Participantes y Conectividad**: Detección de usuarios activos en una sala de modelado con expiración automática por tiempo de vida (TTL / Heartbeat de 15 segundos).
* **Cerrojos Efímeros de Edición (Locks)**: Bloqueo temporal no destructivo cuando un usuario abre el modal de edición de una clase específica, evitando colisiones de sobreescritura entre 2 o 3 colaboradores concurrentes.

> [!NOTE]
> Redis **NO** se utilizará para almacenar el diagrama de manera permanente ni sustituirá las transacciones relacionales de PostgreSQL.

---

## 8. Fuente de Verdad del Estado del Diagrama

### Análisis de Modelos de Verdad para Sesiones Pequeñas (2–3 usuarios):

| Modelo | Dinámica | Ventajas | Desventajas |
| :--- | :--- | :--- | :--- |
| **A. Navegador (Client-Authoritative)** | Cada cliente mantiene su versión y se sincroniza por WebRTC puro. | Cero latencia local. | Conflictos frecuentes de estado ("split-brain"), si el usuario que hospeda cierra la pestaña se pierde la integridad. |
| **B. Servidor Puro (Server-Authoritative)** | Cada mínimo arrastre y pixel debe ser aprobado por el backend antes de renderizar. | Consistencia absoluta. | Sensación de retardo (lag) y rigidez en la interacción con el canvas. |
| **C. Híbrido Particionado (Recomendado)** | **Presentación efímera en navegador (P2P) + Semántica UML con autoridad en Servidor (FastAPI + DB).** | Experiencia fluida de usuario a 60 FPS + integridad relacional y persistencia confiable. | Requiere distinguir eventos de renderizado de eventos de modelo. |

### Decisión de Diseño:
Para grupos pequeños de 2–3 colaboradores, se adopta el **Modelo C (Híbrido Particionado)**:
* El movimiento visual, arrastre de cajas y punteros viajan directamente por **WebRTC DataChannels** entre navegadores para respuesta táctil inmediata.
* Toda operación que mute la semántica del diagrama (crear clase, borrar atributo, cambiar tipo, crear relación) es despachada al **Servidor FastAPI**, quien valida las reglas UML 2.5, persiste en PostgreSQL y notifica a los participantes como cambio canónico confirmado.

---

## 9. Ubicación y Consumo del UML Domain Model

El **UML Domain Model** debe ser un modelo puro y desacoplado, independiente de librerías de UI (JointJS), ORMs (SQLAlchemy / Django ORM), frameworks web (FastAPI / Spring) o SDKs de IA (Gemini).

```text
                  +-------------------------------+
                  | contracts/uml-model.v2.json   |
                  | (Contrato Serialización v2)   |
                  +-------------------------------+
                                  |
            +---------------------+---------------------+
            |                                           |
            v                                           v
+-----------------------+                   +-----------------------+
|  Frontend (Angular)   |                   |  UML Domain Engine    |
|  Tipos TypeScript     |                   |  (Python Puro POPO /  |
|  (Dominio desacoplado |                   |   dataclasses sin     |
|   de JointJS SVG)     |                   |   Pydantic ni web)    |
+-----------------------+                   +-----------------------+
            |                                           |
            | Proyección visual                         | Orquestado por
            v                                           v
+-----------------------+                   +-----------------------+
|   JointJS Canvas      |                   |   FastAPI Gateway     |
|   (Renderizado y      |                   |   (Pydantic solo en   |
|    coordenadas x,y)   |                   |    DTOs de frontera)  |
+-----------------------+                   +-----------------------+
                                                        |
                                                        | Adaptadores Downstream
                                                        v
                                            +-----------------------+
                                            | Spring Boot & Flutter |
                                            | Generators (Mustache) |
                                            +-----------------------+

### Cómo lo Consume Cada Subsistema:
* **Frontend Angular**: Importa interfaces de dominio TypeScript generadas desde el contrato formal. JointJS se limita a ser un consumidor visual que lee el modelo para proyectar celdas y notifica eventos de interacción.
* **UML Domain Engine**: Implementa el modelo canónico puro mediante clases nativas (`dataclasses` / POPO) con métodos de validación formal de reglas UML 2.5, **completamente independiente de Pydantic o frameworks web**.
* **FastAPI Gateway**: Emplea Pydantic v2 **exclusivamente como capa perimetral de serialización/deserialización (DTOs de entrada/salida)** para HTTP/WebSocket, orquestando las llamadas hacia el motor de dominio.
* **PostgreSQL (SQLAlchemy)**: Mapea las propiedades del modelo de dominio a tablas relacionales y columnas JSONB sin contaminar el dominio con dependencias del ORM.
* **Generador Spring Boot y Flutter**: Reciben el payload legacy transformado por el adaptador downstream, previa auditoría de no pérdida de datos (`TransformationReport`).
* **Gemini LLM**: El JSON Schema canónico se le suministra directamente en la directiva `response_schema` del API de Gemini, garantizando que el modelo retornado cumpla exactamente la sintaxis esperada.
