# backend_case — Núcleo FastAPI del Sistema CASE UML 2.5

Este directorio aloja el nuevo backend del sistema CASE. Opera como API Gateway, orquestador de peticiones y punto de entrada para los servicios de modelado UML 2.5, interoperabilidad y futura colaboración en tiempo real.

---

## 1. Propósito

1. Servir como API REST moderna y asíncrona para clientes de modelado UML (Angular frontend, herramientas CLI y servicios externos).
2. Orquestar la validación semántica formal del metamodelo UML 2.5 y los perfiles de compatibilidad para generadores de código (Spring Boot y Flutter).
3. Proveer una frontera desacoplada donde los contratos de transporte HTTP (`contracts/uml-model.v2.json`) se validan mediante **Pydantic v2** antes de delegar la lógica de negocio al motor de dominio puro.

---

## 2. Relación con `core/uml_domain/`

Existe una **regla de dependencia estricta y unidireccional**:

```text
FastAPI (HTTP / Web)
        │
        ▼
Application Layer (Mappers & Services)
        │
        ▼
core.uml_domain (Modelo y Validadores Puros)
```

* **`core/uml_domain/`** es un módulo de Python puro de la biblioteca estándar, completamente independiente de FastAPI, Pydantic, SQLAlchemy o frameworks web.
* **`backend_case/`** consume `core/uml_domain/` como biblioteca de dominio interna.
* **Los modelos Pydantic** residen exclusivamente en `backend_case/app/schemas/` y actúan como DTOs de frontera perimetral.

---

## 3. Endpoints Disponibles (API v2)

| Método | Ruta | Descripción |
| :---: | :--- | :--- |
| `GET` | `/health` | Chequeo de salud del servicio (`{"status": "ok"}`). |
| `GET` | `/api/v2/info` | Metadatos del servicio y versión de esquema UML soportada (`2.0.0`). |
| `POST` | `/api/v2/uml/validate` | Valida semánticamente un modelo UML 2.5 (`VUML-01` a `VUML-13`). |
| `POST` | `/api/v2/uml/compatibility/spring` | Evalúa si el modelo es exportable a Spring Boot v1 (detecta herencia múltiple o features no soportadas). |
| `POST` | `/api/v2/uml/compatibility/flutter` | Evalúa la compatibilidad con la generación de pantallas Flutter CRUD. |

Documentación interactiva disponible en tiempo de ejecución:
* Swagger UI: `http://localhost:8001/docs`
* ReDoc: `http://localhost:8001/redoc`

---

## 4. Ejecución Local

### Requisitos Previos:
* Python 3.12 o superior.

### Pasos:
```bash
# Desde la raíz del repositorio
python -m uvicorn backend_case.app.main:app --host 0.0.0.0 --port 8001 --reload
```

---

## 5. Ejecución de Pruebas

```bash
# Ejecutar suite de pruebas de la API FastAPI
python -m pytest backend_case/tests/ -v

# Ejecutar la totalidad de pruebas del repositorio (Dominio + Legacy + FastAPI)
python -m pytest tests/ backend_case/tests/ -v
```

---

## 6. Funcionalidades NO Implementadas Todavía (Futuras SPECs)

De forma deliberada y para mantener el backend mínimo y libre de sobrecarga prematura, esta SPEC **no incluye**:
* Persistencia en PostgreSQL (gestión de proyectos, usuarios y tablas relacionales).
* Redis (pub/sub de WebSockets y cerrojos de edición distribuida).
* Señalización WebRTC en FastAPI (permanece operando en Django Channels temporalmente).
* Integración con Gemini / Inteligencia Artificial (permanece en Django temporalmente).
* Invocación HTTP directa a Spring Boot o generación de archivos ZIP en disco.
* Autenticación y control de acceso (JWT / RBAC).
