# Estrategia de Transición y Convivencia Arquitectónica

Este documento define la estrategia técnica de convivencia temporal entre el backend Django legado y el nuevo backend FastAPI, garantizando una transición fluida y sin interrupciones operativas mediante la aplicación del patrón **Strangler Fig (Higo Estrangulador)**.

---

## 1. Modelo de Coexistencia Temporal

Durante el proceso evolutivo, el frontend Angular interactuará simultáneamente con ambos backends, diferenciando el destino de cada petición según el nivel de madurez de cada módulo:

```text
                               +-----------------------------+
                               |     Angular Frontend        |
                               |    (localhost:4200)         |
                               +-----------------------------+
                                       |             |
                        Rutas Legadas  |             |  Rutas Migradas
                        (vía Proxy/    |             |  (v1 REST & WS)
                         Directo)      |             |
                                       v             v
                    +--------------------+      +--------------------+
                    |   Django Legacy    |      |    FastAPI Core    |
                    |  (localhost:8000)  |      |  (localhost:8001)  |
                    +--------------------+      +--------------------+
                               |                           |
                               +------------+ +------------+
                                            | |
                                            v v
                                  +--------------------+
                                  |    PostgreSQL      |
                                  |   (Esquemas o      |
                                  | Tablas Separadas)  |
                                  +--------------------+
```

---

## 2. Estrategia de Enrutamiento y Configuración de Red

Para evitar colisiones de puertos y garantizar claridad de tráfico en los entornos de desarrollo y pruebas:

| Servicio | Puerto Local | Rol en la Transición |
| :--- | :--- | :--- |
| **Angular** | `4200` | Cliente único de presentación |
| **Django Legacy** | `8000` | Mantiene endpoints de generación Flutter, backups antiguos y fallback |
| **FastAPI Core** | `8001` | Asume incrementalmente persistencia v2, validación UML, IA y salas |
| **Spring Boot Gen** | `7000` | Generador autónomo llamado por FastAPI vía HTTP |
| **PostgreSQL** | `5432` | Base de datos compartida |
| **Redis** | `6379` | Broker de mensajes para Channels (Django) y WebSockets (FastAPI) |

### Mecanismo de Enrutamiento en Angular:
En el frontend se adoptará un enfoque de **Gateway por Entornos** mediante `src/environments/environment.ts`:

```typescript
export const environment = {
  production: false,
  legacyApiUrl: 'http://localhost:8000/api',
  legacyWsUrl: 'ws://localhost:8000/ws',
  coreApiUrl: 'http://localhost:8001/api/v1',
  coreWsUrl: 'ws://localhost:8001/api/v1/ws',
  features: {
    useFastApiForProjects: false,    // Flag de migración gradual
    useFastApiForAi: false,
    useFastApiForCollaboration: false,
    useFastApiForGenerators: false
  }
};
```
Este mecanismo de feature flags en el cliente permite activar componentes en FastAPI de forma granular y revertir a Django en segundos si se detecta alguna discrepancia funcional.

---

## 3. Matriz de Mitigación de Riesgos de la Transición

| Riesgo Técnico Identificado | Severidad | Estrategia de Mitigación Preventiva |
| :--- | :--- | :--- |
| **Ruptura de la UI de Angular** | **Alta** | No modificar la estructura del DOM de Angular ni la lógica de dibujo de JointJS durante las primeras etapas. Solo se adaptan los adaptadores de servicio HTTP/WS. |
| **Incompatibilidad de Contratos JSON** | **Crítica** | Se establece `contracts/` con esquemas JSON Schema formalizados. FastAPI incluirá validadores y transformadores que aseguren compatibilidad bidireccional entre el formato v1 (legacy) y el formato v2 (UML 2.5 canónico). |
| **Colisión de Persistencia (Doble Escritura)** | **Alta** | **Regla estricta de una sola fuente de escritura por entidad.** Durante la transición de un módulo (ej. proyectos), la responsabilidad de escritura se transfiere por completo a FastAPI. Django no escribe en las mismas tablas que FastAPI. |
| **Conflictos de WebSockets / Concurrencia** | **Media** | Las salas de colaboración gestionadas por Django operarán en endpoints separados (`/ws/canvas/legacy/{id}`) respecto a las de FastAPI (`/api/v1/ws/rooms/{id}`). Un lienzo específico opera en un solo backend a la vez. |
| **Generador Spring Boot Incompatible** | **Alta** | FastAPI preservará con exactitud el formato JSON esperado por `back_generator_uml/` (`UmlSchema`), validándolo con pruebas de contrato automatizadas antes de disparar el envío HTTP. |
| **Dependencia Oculta del Generador Flutter** | **Media** | El código de generación de Flutter en Django (`back_generador_bd/apps/generator/`) se documentará como biblioteca pura de generación para desacoplar su lógica de los modelos ORM de Django antes de su migración final. |

---

## 4. Gobernanza del Código y Prevención de Deuda Técnica

Para asegurar el éxito de la estrategia Strangler:
1. **Congelamiento de Nuevas Características en Django**: No se desarrollará ninguna nueva funcionalidad sobre `back_generador_bd`. Cualquier nuevo requerimiento se creará exclusivamente en `backend_case`.
2. **Correcciones en Legacy Limitadas a Bloqueantes**: Si se detecta un error crítico en Django durante la transición, se corregirá puntualmente sin refactorizaciones estructurales.
3. **Validación Automática de Contratos**: Cada endpoint migrado a FastAPI debe contar con pruebas unitarias que contrasten el JSON de respuesta contra los esquemas de `contracts/`.
