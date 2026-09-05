# Plantilla y Scaffolding Móvil (Contexto B — PA4)

> [!IMPORTANT]
> **Alineación con la SPEC MASTER (`proyecto_actual.md`)**:
> La herramienta CASE **NO** tiene como requisito generar automáticamente la interfaz móvil.
> Según la Sección 1 y 32 de la SPEC MASTER:
> *"Su interfaz móvil no constituye un artefacto que deba ser generado automáticamente por la herramienta, sino que será construida para el dominio de gestión definido durante la evaluación."*

Este directorio conserva la implementación de `flutter_scaffolding.py` (anteriormente `flutter_generator.py` en Django) como **material de apoyo reutilizable** para el día de la evaluación:

1. **Estructura base del cliente móvil**:
   - Modelos Dart tipados (`lib/models/`).
   - Servicios HTTP para consumo del backend Spring Boot generado (`lib/services/`).
   - Vistas y componentes reutilizables (`lib/views/`).
2. **Propósito en la evaluación**:
   - Proveer la base estructural para implementar con rapidez la aplicación de gestión (CU12).
   - Servir como punto de partida para conectar la persistencia local y sincronización offline-first (CU13) y el reconocimiento de voz local (CU14) hacia el backend Spring Boot de CU10.
