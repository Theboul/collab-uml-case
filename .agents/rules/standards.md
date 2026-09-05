# Reglas y Estándares del Proyecto — Diagramador UML CASE

## Principios Obligatorios

1. **Aislamiento de `core/uml_domain`**:
   - Jamás importar frameworks (FastAPI, SQLAlchemy, Pydantic, HTTP) dentro de `core/uml_domain`.
   - Se prohíbe modificar `core/uml_domain` sin confirmación explícita previa del usuario.

2. **Regla de Pragmatismo en Puertos/Adaptadores**:
   - `modeling`: servicio directo sobre `core/uml_domain` (sin ports).
   - `collaboration`: con puerto `LockStore` (Redis).
   - `assistant`: con puerto `AiCommandInterpreter` (Gemini / LLM local).
   - `interoperability`: plano inicialmente (XMI).
   - `generation`: con puerto por generador (Spring y Flutter).
   - `legacy`: rutas y WebSockets planos para soportar el frontend Angular actual.

3. **Restricciones de Código en Backend (`backend_case`)**:
   - No `from x import *`.
   - No `raise Exception("...")` genérico — utilizar la taxonomía en `app/shared/errors/`.
   - No lógica de negocio ni consultas SQL dentro de routers `api/`.
   - No llamadas directas a APIs externas fuera de `infrastructure/`.
   - Funciones delimitadas a ~40 líneas.

4. **Restricciones de Código en Frontend (`front_generador_bd`)**:
   - TypeScript `strict: true`. Prohibido `any` no justificado documentalmente.
   - Flujo de datos estricto: `Component → Facade/Service → Adapter → HttpClient`.
   - Código JointJS confinado a adaptadores de infraestructura (`features/modeling/infrastructure/jointjs/`).

5. **Definition of Done**:
   - Todo código nuevo debe contar con tipos estáticos, lint limpio, tests de comportamiento crítico y pasar la suite completa de pruebas (`pytest` y `node --test`).

---

### Regla del módulo `assistant` (CU6, CU7) — no negociable

El flujo de cualquier entrada procesada por IA (Gemini u otro modelo, texto,
voz o imagen) es SIEMPRE:

```text
    Entrada del usuario
        ↓
    InterpretadorComandosModelado / AnalizadorDiagramaImagen
        ↓
    Salida cruda de la IA (ComandoModelado / PropuestaModelo)
        ↓
    ValidadorComandoModelado / ValidadorModelo   ← OBLIGATORIO, sin excepción
        ↓
    GestorElementosUML / GestorRelacionesUML     ← únicos que tocan ModeloUML
```

Reglas duras:

1. Ninguna función dentro de `app/assistant/` puede importar o llamar
   directamente a `GestorElementosUML`, `GestorRelacionesUML` ni a
   `core/uml_domain` sin pasar antes por el validador correspondiente.
   No existe bypass "temporal", "solo para debug" ni "solo en dev".

2. La salida de la IA se trata SIEMPRE como no confiable, igual que un
   input HTTP del usuario. Se valida:
   - Esquema/estructura (¿es un ComandoModelado bien formado?)
   - Referencias (¿los IDs de elementos/relaciones que menciona existen
     en el modelo actual?)
   - Reglas de negocio UML (multiplicidades, tipos válidos, ciclos no
     permitidos, etc. — las mismas que ya aplica `ValidadorModelo`
     para CU9)

3. Si la validación falla, el sistema responde con un error explícito
   al usuario (nunca aplica el cambio parcialmente ni "corrige"
   silenciosamente lo que la IA propuso).

4. Toda invocación a un modelo de IA pasa por el puerto
   `AiCommandInterpreter` (nunca se llama al SDK de Gemini directo
   desde un router o desde `application/`). Esto además es lo que
   permite cumplir la regla de pragmatismo ya definida (Gemini hoy,
   modelo local mañana, sin tocar el resto del módulo).

5. Test obligatorio antes de dar por cumplido el DoD de CU6/CU7:
   un caso donde la IA devuelve un comando/propuesta inválido
   (referencia a un elemento inexistente, tipo de relación no soportado,
   texto ambiguo) y se verifica que el modelo NO cambia y el error
   se propaga correctamente.

