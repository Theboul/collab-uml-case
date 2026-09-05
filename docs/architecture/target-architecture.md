# Arquitectura Objetivo del Diagramador CASE UML

Este documento describe la arquitectura objetivo para la evolución del sistema CASE colaborativo de modelado de diagramas de clases UML 2.5 hacia una plataforma robusta, reactiva y desacoplada, utilizando **FastAPI** como núcleo operativo central e integrando subsistemas especializados sin disrupciones.

---

## 1. Visión General de la Arquitectura Objetivo

El sistema evoluciona desde un monolito Django acoplado hacia una arquitectura orientada a servicios ligeros y modulares centrados en el dominio UML:

```text
+-----------------------------------------------------------------------+
|                            FRONTEND                                   |
|   Angular 20 + JointJS Canvas Engine + WebRTC Client (DataChannels)   |
+-----------------------------------------------------------------------+
                     | HTTP / REST                  ^ WebSocket / WSS
                     v (JSON Contracts)             | (Presence & Sync)
+-----------------------------------------------------------------------+
|                    FASTAPI CORE GATEWAY & DOMAIN                      |
|                                                                       |
|  [UML Domain Engine] <---> [Validation Engine (UML 2.5 Constraints)]  |
|  [Canvas / Project Manager] [Collaboration & Room Manager (WS/STUN)]  |
|  [AI Orchestration Hub]    [Code Generation Dispatcher]               |
+-----------------------------------------------------------------------+
        |                 |                    |                 |
        | SQL             | PubSub/Cache       | HTTP/REST       | Internal Mod.
        v                 v                    v                 v
+---------------+  +--------------+  +-------------------+  +------------------+
|  PostgreSQL   |  |    Redis     |  |   Spring Boot     |  | Flutter Template |
|  (Persistencia|  |  (Presencia, |  |   Generator       |  | Engine (CRUD)    |
|   de Modelos, |  |   Eventos    |  | (Java 21, API REST|  | (Generador Dart/ |
|   Proyectos y |  |   y Locks    |  |  Postman, Spring) |  |  Flutter app)   |
|   Snapshots)  |  |   efímeros)  |  +-------------------+  +------------------+
+---------------+  +--------------+            |
                                               v
                                     [Generación de Backend]
```

---

## 2. Principios Arquitectónicos Clave

1. **UML Domain-Driven Core (Agnóstico de UI)**:
   El modelo semántico de clases UML (entidades, atributos, métodos, relaciones, multiplicidades, visibilidad) reside formalmente en el backend, independiente de coordenadas gráficas, estilos de JointJS, wrappers SVG o tecnologías de renderizado.

2. **Server-Authoritative con Colaboración P2P Asistida**:
   La fuente de verdad canónica del modelo UML es el servidor FastAPI respaldado por PostgreSQL. WebRTC DataChannel se mantiene para la interacción peer-to-peer de bajísima latencia (arrastre de nodos en tiempo real, punteros remotos y telemetría de interacción), mientras que las mutaciones estructurales del modelo UML (añadir clase, alterar tipos, vincular relaciones) se confirman y sincronizan con autoridad en el servidor.

3. **Contratos Canónicos Formales (`contracts/`)**:
   Todas las comunicaciones entre Frontend, FastAPI y los Generadores de Código están normadas por esquemas JSON Schema (`UmlSchema` v2). Ningún subsistema depende de estructuras internas de base de datos o de tipos específicos de un framework.

4. **Desacoplamiento de Motores de Generación**:
   Los generadores de código de destino (Spring Boot con Java 21 y Postman, así como Flutter CRUD) operan como consumidores de contratos. FastAPI actúa como despachador (*dispatcher*), orquestando la exportación sin acoplar la lógica de dominio CASE al runtime de Spring Boot ni al código de Flutter.

5. **Evolución por Estrangulamiento (*Strangler Fig Pattern*)**:
   FastAPI asume progresivamente las capacidades de dominio mientras Django opera como backend legacy para funciones no migradas, eliminando cualquier riesgo de reescritura tipo "Big Bang".

---

## 3. Topología de Componentes y Red

| Componente | Rol en Arquitectura Objetivo | Protocolo / Puerto |
| :--- | :--- | :--- |
| **Angular Frontend** | UI de modelado JointJS, gestión de canvas y cliente WebRTC/WS | HTTP / WSS (`http://localhost:4200`) |
| **FastAPI Core** | Núcleo de dominio UML, persistencia, validación, IA y dispatching | REST / ASGI WSS (`http://localhost:8000`) |
| **Spring Boot Generator** | Subsistema autónomo de generación de backend Spring Boot y Postman | HTTP REST (`http://localhost:7000/generate`) |
| **PostgreSQL** | Almacén relacional transaccional (Proyectos, Diagramas, Snapshot UML) | TCP 5432 |
| **Redis** | Broker de canales WebSocket, presencia de participantes y cerrojos de edición | TCP 6379 |
| **Google Gemini API** | Motor LLM/Multimodal para diagramación desde prompts, audio e imágenes | HTTPS externo |

---

## 4. Flujo de Información de Extremo a Extremo

### A. Creación y Edición de Diagrama
1. El usuario interactúa sobre el canvas JointJS en Angular.
2. Los eventos de presentación (coordenadas `x, y`, posiciones de enlaces) actualizan el estado visual local y se transmiten por WebRTC a otros pares conectados para fluidez instantánea.
3. Las operaciones de modelo (creación de clase, renombrado de atributo, cambio de multiplicidad) envían un payload tipado a FastAPI (`PUT /api/v1/diagrams/{id}/operations`).
4. FastAPI valida la operación contra reglas UML 2.5, persiste la mutación en PostgreSQL y emite el evento de sincronización a través de WebSocket/Redis a todos los clientes del lienzo.

### B. Generación de Backend (Spring Boot + Postman)
1. Angular solicita a FastAPI la exportación de código: `POST /api/v1/diagrams/{id}/export/spring-boot`.
2. FastAPI extrae el modelo canónico estructurado del proyecto y valida su integridad relacional.
3. FastAPI envía el contrato `UmlSchema` validado mediante HTTP POST a `http://localhost:7000/generate`.
4. El generador Spring Boot procesa sus plantillas Mustache, empaqueta el proyecto y la colección Postman en un ZIP y lo devuelve por stream a FastAPI.
5. FastAPI transmite el archivo ZIP descargable a Angular.

### C. Generación de Aplicación Flutter CRUD
1. Angular solicita la exportación de la app móvil de gestión: `POST /api/v1/diagrams/{id}/export/flutter`.
2. FastAPI valida las entidades y mapea los tipos del modelo a tipos Dart.
3. El módulo de plantillas Flutter genera el proyecto Dart/Flutter compilable para consumir el backend Spring Boot.
4. Se empaqueta en ZIP y se entrega al usuario.

### D. Asistencia por Inteligencia Artificial (Gemini)
1. El cliente envía prompt de texto, audio transcrito o imagen de boceto a FastAPI (`POST /api/v1/ai/generate-diagram`).
2. FastAPI invoca a Gemini mediante el SDK oficial de Python usando Structured Outputs con el JSON Schema de UML 2.5.
3. FastAPI valida semánticamente la respuesta del LLM garantizando identificadores consistentes y relaciones válidas.
4. FastAPI calcula un layout algorítmico inicial o provee las entidades al frontend para que JointJS las distribuya en el canvas.
