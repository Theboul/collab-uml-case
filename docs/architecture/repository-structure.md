# Estructura del Repositorio y Estrategia de Coexistencia

Este documento analiza la organización de carpetas del repositorio tanto en su **fase inmediata de transición** como en su **fase objetivo final**, evaluando el impacto operativo y las mejores prácticas para un monorepo controlado.

---

## 1. Análisis de la Propuesta de Organización

Se ha evaluado la propuesta preliminar de incorporar el nuevo backend en una carpeta independiente dentro del monorepo actual:

```text
Diagramador_UML_Examen2/
├── front_generador_bd/      # Frontend Angular 20 actual
├── back_generador_bd/       # Backend Django legacy
├── backend_case/            # Nuevo backend FastAPI
├── back_generator_uml/      # Generador Spring Boot existente
├── contracts/               # Esquemas JSON canónicos compartidos
└── docs/                    # Documentación arquitectónica y de migración
```

### Veredicto Técnico: **Aprobada y Recomendada**
Esta organización presenta ventajas decisivas:
1. **Riesgo Cero sobre el Código Actual**: No altera rutas de importación, scripts de ejecución ni configuraciones Docker existentes de `front_generador_bd`, `back_generador_bd` o `back_generator_uml`.
2. **Aislamiento Total de Dependencias**: Permite crear para `backend_case` un entorno Python independiente (virtualenv con `pyproject.toml` o `requirements.txt`), usando dependencias modernas (FastAPI, Pydantic v2, SQLAlchemy 2 async) sin colisionar con las versiones fijadas en Django 5.
3. **Punto Neutro de Sincronización (`contracts/`)**: Define un directorio compartido para esquemas JSON/OpenAPI, sirviendo como única fuente de verdad contractual para Angular, FastAPI y Spring Boot.
4. **Despliegue y Pruebas Independientes**: Cada subsistema conserva su propio ciclo de arranque y verificación local.

---

## 2. Fase 1: Estructura Mínima Inmediata (Transición)

En esta fase, los nombres históricos de los componentes se preservan íntegramente para evitar modificaciones innecesarias en scripts de despliegue y herramientas locales.

```text
Diagramador_UML_Examen2/
│
├── .git/
├── docker-compose.db.yml           # Servicios compartidos: PostgreSQL + Redis
├── docker-compose.app.yml          # Configuración actual de servicios legacy
│
├── front_generador_bd/             # [PRESERVAR] Frontend Angular 20 + JointJS
│   ├── src/
│   │   ├── app/
│   │   │   ├── core/               # Modelos, contratos y servicios
│   │   │   ├── features/           # Componentes de canvas, IA y generadores
│   │   │   └── shared/
│   │   └── ...
│   └── package.json
│
├── back_generador_bd/              # [LEGACY TEMPORAL] Backend Django + Channels
│   ├── apps/
│   │   ├── generator/              # Módulo generador Flutter CRUD (reutilizable)
│   │   └── ...
│   ├── manage.py
│   └── requirements.txt
│
├── back_generator_uml/             # [PRESERVAR] Generador Spring Boot 3.5.5
│   ├── src/main/java/
│   ├── src/main/resources/templates/  # Plantillas Mustache para Spring y Postman
│   ├── pom.xml
│   └── Dockerfile
│
├── backend_case/                   # [NUEVO - FASTAPI] (Se creará en fase 4)
│   ├── src/
│   │   ├── domain/                 # Entidades y reglas puras UML 2.5
│   │   ├── schemas/                # Modelos Pydantic v2 (contratos canónicos)
│   │   ├── api/                    # Routers REST y WebSocket
│   │   ├── services/               # Orquestación de persistencia, IA y dispatch
│   │   └── infrastructure/         # Repositorios SQLAlchemy 2, Redis client
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
│
├── contracts/                      # [NUEVO - CONTRATOS COMPARTIDOS]
│   ├── uml-schema.v1.json          # Contrato legacy actual
│   ├── uml-model.v2.json           # Esquema formal UML 2.5 canónico
│   └── api/                        # Especificaciones OpenAPI de endpoints
│
└── docs/                           # [DOCUMENTACIÓN]
    ├── architecture/
    └── migration/
```

---

## 3. Fase 2: Estructura Objetivo Futura (Post-Retiro de Django)

Una vez que Django sea completamente retirado y todas las responsabilidades hayan sido asumidas y estabilizadas en FastAPI, se podrá realizar un renombramiento cosmético controlado de carpetas para alcanzar una estructura corporativa unificada y semánticamente limpia:

```text
Diagramador_UML_Examen2/
│
├── .git/
├── docker-compose.yml              # Unificación de DB, Redis, API, Gen y Front
│
├── apps/
│   ├── web-client/                 # (Anterior front_generador_bd) Angular 20
│   ├── core-api/                   # (Anterior backend_case) FastAPI Core
│   └── spring-generator/           # (Anterior back_generator_uml) Spring Boot 3
│
├── packages/
│   └── contracts/                  # Esquemas JSON Schema y tipados generados
│       ├── uml/
│       └── codegen/
│
└── docs/                           # Documentación de arquitectura y operaciones
```

> [!NOTE]
> La transición hacia la estructura de la Fase 2 es opcional y únicamente cosmética. La Fase 1 preserva la estabilidad técnica y la compatibilidad operativa sin interferir en los desarrollos cotidianos.
