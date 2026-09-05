# ADR-0007: Exclusión de Generación Móvil del CASE y Conservación de Scaffolding para Evaluación

**Estado:** Aprobado  
**Fecha:** 2026-09-05  
**Decisores:** Equipo de Arquitectura / Antigravity  
**Casos de Uso relacionados:** CU10, CU11, CU12, CU13, CU14  

---

## Contexto

El documento de especificación formal del proyecto (`proyecto_actual.md`, SPEC MASTER) establece en sus Secciones 1 y 32:
> *"La herramienta CASE no tiene como requisito generar automáticamente la interfaz móvil... Su interfaz móvil no constituye un artefacto que deba ser generado automáticamente por la herramienta, sino que será construida para el dominio de gestión definido durante la evaluación."*

En el código heredado (Django `back_generador_bd`), existía un archivo `flutter_generator.py` de 2.689 líneas que pretendía generar vistas CRUD en Dart desde el backend. Esto generaba una contradicción de alcance con los requisitos y acoplaba innecesariamente el pipeline de generación del CASE (`generation/`).

## Decisión

1. **Exclusión de `generation/`**: El módulo `backend_case/app/generation/` contendrá exclusivamente los puertos y adaptadores para:
   - Backend Spring Boot 3 (CU10).
   - Colecciones de prueba Postman v2.1 (CU11).
2. **Conservación como Scaffolding de Apoyo**: Se conserva el código de generación Dart en la raíz bajo `mobile_app_reference/flutter_scaffolding.py` con propósito exclusivo de **plantilla de apoyo/scaffolding reutilizable** para el Contexto B (PA4 / CU12–CU14).
3. **Rol en la Evaluación**: Durante la jornada de evaluación, este scaffolding permitirá acelerar la construcción manual del frontend móvil, adaptándolo a los contratos REST y documentación OpenAPI expuestos por el backend Spring Boot generado en vivo.

## Consecuencias

### Positivas:
- **Cero contradicciones con la SPEC**: La herramienta CASE se enfoca con precisión en lo exigido (Spring Boot + Postman).
- **Desacoplamiento total de Django**: Se elimina la dependencia de Django y se puede retirar la carpeta `legacy/`.
- **Aceleración en la evaluación**: Se cuenta con modelos, servicios y estructura Flutter ya probada para conectar la app móvil (CU12–CU14) sin empezar de cero.

### Negativas / Mitigaciones:
- El scaffolding Dart deberá ajustarse manualmente al dominio específico asignado en la evaluación, lo cual es exactamente el escenario previsto y exigido por la SPEC MASTER.
