# SPEC MASTER — Sistema CASE Colaborativo para Modelado UML y Generación de Software

**Estado:** Especificación base para análisis técnico, diseño e implementación
**Objetivo del documento:** Servir como fuente de verdad para Antigravity antes de modificar o generar código.
**Regla principal:** No implementar funcionalidades, tecnologías o comportamientos que contradigan esta especificación. Cuando una decisión todavía no esté definida, deberá identificarse como decisión pendiente de Diseño y no asumirse arbitrariamente.

---

# 1. VISIÓN DEL PRODUCTO

El proyecto consiste en construir una herramienta CASE colaborativa especializada en modelado de diagramas de clases UML y automatización de generación de software.

El producto posee dos contextos funcionales relacionados, pero conceptualmente separados.

## Contexto A — Herramienta CASE colaborativa

Es el producto principal.

Debe permitir:

* crear y recuperar lienzos UML;
* construir diagramas de clases;
* manipular elementos y relaciones;
* colaborar en tiempo real;
* utilizar texto y voz como mecanismo alternativo de modelado;
* generar modelos desde imágenes;
* importar y exportar modelos con Enterprise Architect;
* validar modelos UML;
* generar un backend Spring Boot;
* generar artefactos compatibles con Postman.

## Contexto B — Aplicación móvil de gestión

Es una aplicación utilizada para demostrar y validar el software generado.

No debe confundirse con la herramienta CASE.

La aplicación móvil:

* utilizará los servicios del backend generado;
* será construida para un dominio de gestión definido durante la evaluación;
* deberá funcionar parcialmente sin Internet;
* deberá almacenar información localmente;
* deberá sincronizar información posteriormente;
* deberá reconocer voz localmente;
* deberá interpretar instrucciones localmente.

La herramienta CASE **no tiene como requisito generar automáticamente la interfaz móvil**.

---

# 2. OBJETIVO GENERAL

Construir una herramienta CASE que aumente la productividad del desarrollo permitiendo pasar desde un modelo UML colaborativo hasta un backend estructurado y comprobable, incorporando mecanismos inteligentes de interacción sin comprometer la consistencia del modelo.

El sistema debe demostrar:

| Objetivo          | Resultado esperado                              |
| ----------------- | ----------------------------------------------- |
| Modelado          | Construcción correcta de diagramas UML          |
| Colaboración      | Varios usuarios editan el mismo modelo          |
| Automatización    | Texto, voz e imagen producen operaciones UML    |
| Interoperabilidad | Intercambio con Enterprise Architect            |
| Calidad           | Modelos validados antes de operaciones críticas |
| Generación        | Backend Spring Boot estructurado                |
| Verificación      | Recursos Postman compatibles con el backend     |
| Movilidad         | Aplicación móvil consumiendo el backend         |
| Offline           | Operaciones locales sin Internet                |
| IA local móvil    | Voz e interpretación funcionando localmente     |

---

# 3. FUENTE DE VERDAD FUNCIONAL

La implementación estará dirigida por los siguientes casos de uso.

## Iteración 1 — Núcleo del modelador

| CU  | Funcionalidad                     |
| --- | --------------------------------- |
| CU1 | Crear nuevo lienzo UML            |
| CU2 | Ingresar a un lienzo existente    |
| CU3 | Gestionar elementos del diagrama  |
| CU4 | Gestionar relaciones del diagrama |

## Iteración 2 — Colaboración e interoperabilidad

| CU  | Funcionalidad                   |
| --- | ------------------------------- |
| CU5 | Colaborar en la edición         |
| CU8 | Importar y exportar modelos UML |
| CU9 | Validar modelo UML              |

## Iteración 3 — Automatización y generación

| CU   | Funcionalidad                  |
| ---- | ------------------------------ |
| CU6  | Gestionar mediante texto o voz |
| CU7  | Generar desde imagen           |
| CU10 | Generar backend Spring Boot    |
| CU11 | Generar artefactos Postman     |

## Iteración 4 — Aplicación móvil

| CU   | Funcionalidad                          |
| ---- | -------------------------------------- |
| CU12 | Ejecutar aplicación móvil de gestión   |
| CU13 | Trabajar offline y sincronizar         |
| CU14 | Operar mediante asistente de voz local |

---

# 4. ACTORES

## A1 — Anfitrión

Usuario de la herramienta CASE que crea originalmente un lienzo.

Es responsable de iniciar el espacio de trabajo y obtener el mecanismo utilizado para permitir la incorporación posterior de colaboradores.

A1 puede utilizar todas las capacidades CASE.

## A2 — Colaborador

Usuario que entra a un lienzo existente.

Nunca deberá comenzar desde un modelo vacío cuando el lienzo ya posee información.

Al ingresar deberá recuperar el estado actual del proyecto.

## AM1 — Usuario de aplicación móvil

Usuario final del sistema de gestión construido para demostrar el backend generado.

AM1 pertenece exclusivamente al contexto móvil.

A1 y A2 **no deben utilizarse como actores del sistema móvil**.

---

# 5. MODELO DE ANÁLISIS OBLIGATORIO

La arquitectura deberá preservar cuatro áreas conceptuales.

## PA1 — Gestión de Lienzos y Modelado UML

Es el núcleo del sistema CASE.

Responsabilidades:

* lienzos;
* participantes;
* mecanismos de acceso;
* modelo UML;
* elementos UML;
* relaciones UML;
* propiedades;
* multiplicidades;
* validación.

PA1 debe poder existir independientemente de:

* colaboración;
* inteligencia artificial;
* interoperabilidad;
* generación de software.

### Regla arquitectónica crítica

PA1 **NO puede depender de PA2 o PA3**.

La dirección permitida es:

```text
PA2 ------+
          |
          +------> PA1
          |
PA3 ------+
```

Nunca:

```text
PA1 ---> PA2
PA1 ---> PA3
```

---

# 6. PA2 — COLABORACIÓN E INTEROPERABILIDAD

PA2 utiliza el modelo administrado por PA1.

Sus dos responsabilidades principales son:

### Colaboración

Debe permitir varios participantes conectados al mismo lienzo manteniendo un estado coherente.

### Interoperabilidad

Debe aislar la representación interna UML de la representación procedente de herramientas externas.

Enterprise Architect es la herramienta externa mínima que debe soportarse.

El formato físico exacto de intercambio será una decisión de Diseño.

Antigravity **no deberá asumir XMI u otro formato concreto hasta que éste sea definido explícitamente**.

---

# 7. PA3 — ASISTENCIA INTELIGENTE Y GENERACIÓN CASE

PA3 contiene todas las capacidades automáticas que operan sobre PA1.

Debe incluir conceptualmente:

* interpretación de instrucciones;
* reconocimiento de comandos de modelado;
* análisis de imágenes;
* generación de propuestas UML;
* transformación del modelo;
* generación de backend;
* generación de artefactos de prueba.

PA3 puede depender de PA1.

PA1 nunca deberá conocer internamente cómo funciona la IA.

---

# 8. PA4 — APLICACIÓN MÓVIL Y OPERACIÓN LOCAL

PA4 constituye un contexto separado del editor CASE.

Debe consumir los servicios proporcionados por el backend generado.

Debe permitir:

* ejecución convencional;
* persistencia local;
* operación sin conectividad;
* registro de operaciones pendientes;
* sincronización;
* reconocimiento local de voz;
* interpretación local de instrucciones.

PA4 no necesita conocer:

* cómo fue construido el diagrama;
* cómo funciona la colaboración;
* cómo se interpretó una imagen;
* cómo se generó internamente el backend.

---

# 9. MODELO UML COMO FUENTE DE VERDAD

Dentro de la herramienta CASE deberá existir una representación estructurada del modelo UML.

La representación visual del lienzo **no debe convertirse en la única fuente de verdad**.

Conceptualmente:

```text
Interfaz gráfica
       |
       v
Operaciones de modelado
       |
       v
Modelo UML estructurado
       |
       v
Persistencia
```

El backend generado, la interoperabilidad, la IA y la colaboración deberán trabajar sobre una representación coherente del modelo, no interpretar directamente elementos visuales de la interfaz cada vez que necesiten información.

---

# 10. REGLA DE MODIFICACIÓN DEL MODELO

Toda modificación deberá pasar por operaciones controladas.

Flujo conceptual:

```text
Entrada
   |
   v
Operación estructurada
   |
   v
Validación
   |
   v
Aplicación del cambio
   |
   v
Actualización del modelo
   |
   v
Persistencia
```

Los mecanismos inteligentes nunca modificarán directamente el estado persistente.

---

# 11. CU1 — CREACIÓN DE LIENZO

Al crear un lienzo deberán producirse como mínimo:

```text
Lienzo
ModeloUML inicial
Identificador único
Mecanismo de acceso
Estado inicial persistido
```

El resultado debe permitir que posteriormente otro usuario utilice el mecanismo de acceso para incorporarse.

La creación debe ser atómica desde la perspectiva del usuario.

No se deberá dejar un lienzo parcialmente creado ante un error.

---

# 12. CU2 — INGRESO A LIENZO

Cuando un participante entra:

```text
mecanismo de acceso
        |
        v
validar acceso
        |
        v
identificar lienzo
        |
        v
recuperar modelo actual
        |
        v
registrar participante
        |
        v
sincronizar estado
        |
        v
mostrar lienzo
```

Regla crítica:

**un colaborador que ingresa tarde debe visualizar el estado actual del modelo y no una copia vacía o desactualizada.**

---

# 13. CU3 Y CU4 — OPERACIONES UML

La aplicación deberá soportar operaciones controladas sobre:

### Elementos

* crear;
* modificar;
* eliminar.

### Relaciones

* crear;
* modificar;
* eliminar;
* configurar propiedades;
* configurar multiplicidades cuando corresponda.

La eliminación de un elemento deberá verificar previamente referencias y relaciones relacionadas.

No deberá ser posible producir silenciosamente un modelo internamente inconsistente.

---

# 14. CU5 — COLABORACIÓN EN TIEMPO REAL

La concurrencia constituye uno de los riesgos técnicos principales.

No debe solucionarse mediante bloqueo permanente del diagrama completo.

La unidad de control deberá ser la mínima técnicamente razonable.

Ejemplos:

```text
Atributo UML
Operación UML
Relación UML
Elemento UML
```

Si:

```text
Usuario A modifica atributo nombre
Usuario B modifica atributo dirección
```

el sistema debería permitir concurrencia cuando ambas modificaciones sean independientes.

Si ambos modifican el mismo recurso incompatible, el sistema deberá:

```text
detectar conflicto
        |
        v
evitar sobrescritura silenciosa
        |
        v
resolver/rechazar/notificar según estrategia de Diseño
```

La estrategia concreta de concurrencia se determinará posteriormente en Diseño.

Antigravity deberá conservar este requisito al proponer la solución.

---

# 15. CU6 — INTERACCIÓN MEDIANTE TEXTO Y VOZ

Texto y voz constituyen mecanismos alternativos de entrada.

No constituyen modelos UML independientes.

Pipeline obligatorio:

```text
Texto/Voz
   |
   v
Interpretación
   |
   v
ComandoModelado
   |
   v
Validación del comando
   |
   +-------------------+
   |                   |
   v                   v
Operación elemento   Operación relación
   |                   |
   +---------+---------+
             |
             v
          ModeloUML
```

La IA no podrá alterar `ModeloUML` directamente.

Ejemplo:

```text
"Crear una clase Cliente con nombre y correo"
```

deberá convertirse primero en una representación estructurada equivalente.

Por ejemplo conceptualmente:

```text
tipoOperacion: CREAR_CLASE
clase: Cliente
atributos:
  - nombre
  - correo
```

El formato exacto de esta representación será definido durante Diseño.

---

# 16. CU7 — GENERACIÓN DESDE IMAGEN

Una imagen no debe transformarse inmediatamente en cambios definitivos.

Pipeline:

```text
Imagen
   |
   v
Análisis
   |
   v
PropuestaModelo
   |
   v
Validación
   |
   v
Revisión/confirmación
   |
   v
ModeloUML
```

La entidad conceptual `PropuestaModelo` debe existir para separar:

```text
lo inferido
```

de:

```text
lo confirmado
```

Una interpretación con baja confianza no deberá modificar automáticamente el modelo persistido.

---

# 17. CU8 — INTEROPERABILIDAD

Se necesita un mecanismo que permita:

```text
Enterprise Architect
        |
        v
Representación externa
        |
        v
Transformación
        |
        v
Modelo interno
```

y:

```text
Modelo interno
        |
        v
Transformación
        |
        v
Representación externa
        |
        v
Enterprise Architect
```

La representación interna no deberá quedar acoplada directamente a Enterprise Architect.

Debe existir una frontera de transformación.

La validación es obligatoria durante las operaciones de intercambio.

Relación conceptual:

```text
CU8 <<include>> CU9
```

---

# 18. CU9 — VALIDACIÓN UML

Debe existir un servicio conceptual centralizado de validación.

Como mínimo debe poder verificar las reglas que realmente soporte el modelador relacionadas con:

* propiedades requeridas;
* referencias;
* relaciones;
* multiplicidades;
* construcciones no soportadas;
* restricciones necesarias para generación.

Los resultados deberán diferenciar como mínimo:

```text
ERROR
ADVERTENCIA
```

Un error bloqueante deberá impedir las operaciones que requieran un modelo válido.

CU9 será reutilizado por:

```text
CU7
CU8
CU10
```

---

# 19. CU10 — GENERACIÓN DE BACKEND

El modelo UML validado deberá transformarse en un proyecto backend Spring Boot.

Pipeline:

```text
ModeloUML
   |
   v
Validación
   |
   v
EspecificacionBackend
   |
   v
GeneradorBackend
   |
   v
Proyecto generado
```

La generación deberá contemplar conceptualmente:

```text
entidades/modelos
persistencia
servicios
controladores REST
configuración PostgreSQL
estructura de proyecto
```

El proyecto generado deberá estar suficientemente estructurado para poder ser ejecutado y probado.

### Regla crítica

El generador no debe construir directamente archivos leyendo elementos visuales del lienzo.

Debe utilizar el modelo UML estructurado.

---

# 20. ESPECIFICACIÓN INTERMEDIA DE BACKEND

Antes de producir archivos físicos deberá existir conceptualmente una representación preparada para generación.

Ejemplo:

```text
ModeloUML
   |
   v
EspecificacionBackend
   |
   +---- Entidades
   +---- Relaciones
   +---- Servicios
   +---- Endpoints
   +---- Configuración
```

Esto desacopla:

```text
modelo UML
```

de:

```text
plantillas/archivos Spring Boot
```

y permitirá modificar posteriormente el generador sin alterar el núcleo UML.

---

# 21. CU11 — POSTMAN

Los recursos de Postman deben derivarse de la misma especificación utilizada para generar los endpoints.

Nunca deberán definirse manualmente de forma independiente si pueden derivarse de la información generada.

Conceptualmente:

```text
EspecificacionBackend
        |
        v
ServiciosAPI
        |
        v
GeneradorPruebasAPI
        |
        v
Coleccion Postman
```

De esta manera:

```text
backend generado
```

y:

```text
colección Postman
```

provienen de una misma fuente de verdad.

La generación de Postman forma parte del resultado esperado de CU10.

Relación:

```text
CU10 <<include>> CU11
```

---

# 22. CU12 — APLICACIÓN MÓVIL

El dominio exacto será determinado durante la evaluación.

La arquitectura móvil no debe quedar fuertemente acoplada a un único ejemplo académico como:

```text
veterinaria
ventas
colegio
contabilidad
```

La aplicación concreta sí tendrá un dominio determinado, pero los mecanismos reutilizables de:

```text
operación
offline
sincronización
voz
```

deberán diseñarse para poder reutilizarse.

---

# 23. CU13 — OFFLINE FIRST

La aplicación debe ser capaz de continuar ejecutando determinadas operaciones cuando desaparezca Internet.

Pipeline:

```text
CON INTERNET
Backend
   |
   v
Información necesaria
   |
   v
Persistencia local
```

Posteriormente:

```text
SIN INTERNET
Usuario
   |
   v
Operación
   |
   v
Datos locales
   |
   v
Resultado local
   |
   v
OperacionPendiente
```

Cuando regrese la conectividad:

```text
OperacionPendiente
        |
        v
Sincronizador
        |
        v
Backend
        |
        v
Respuesta
        |
        v
Actualizar estado local
```

---

# 24. SINCRONIZACIÓN

El mecanismo deberá considerar como mínimo:

```text
operación pendiente
estado de sincronización
reintentos controlados
detección de conflicto
confirmación del servidor
actualización local
```

Como regla de calidad derivada del requisito offline, las operaciones deberán diseñarse procurando evitar duplicaciones cuando una sincronización sea reintentada.

La estrategia exacta de resolución de conflictos deberá definirse durante Diseño.

---

# 25. CU14 — ASISTENTE LOCAL

Éste constituye un requisito crítico.

La operación principal debe poder ejecutarse sin depender de servicios cloud para:

```text
reconocimiento de voz
interpretación de intención
```

Pipeline obligatorio:

```text
Audio
  |
  v
ReconocedorVozLocal
  |
  v
Texto
  |
  v
InterpretadorComandosLocal
  |
  v
ComandoMovil
  |
  v
ValidadorComandoMovil
  |
  v
GestorOperacionMovil
```

Nunca:

```text
Reconocedor/IA
      |
      v
Modificar directamente datos
```

---

# 26. REGLAS ARQUITECTÓNICAS NO NEGOCIABLES

1. El núcleo UML será independiente de IA, colaboración e interoperabilidad.

2. Las entradas inteligentes deberán convertirse en representaciones estructuradas antes de modificar información.

3. El resultado de imágenes será una propuesta antes de convertirse en modelo definitivo.

4. La validación deberá reutilizarse y no duplicarse entre funcionalidades.

5. La colaboración no deberá bloquear innecesariamente todo el modelo.

6. El backend y Postman deberán compartir una fuente estructurada común.

7. La aplicación móvil estará separada del editor CASE.

8. La aplicación móvil deberá poder continuar ciertas operaciones sin Internet.

9. El reconocimiento e interpretación de voz móvil deberán poder realizarse localmente.

10. Las tecnologías concretas deberán depender de las decisiones posteriores del Diseño y no al contrario.

---

# 27. CALIDAD DEL CÓDIGO

Toda implementación deberá priorizar:

```text
Alta cohesión
Bajo acoplamiento
Separación de responsabilidades
Reutilización
Testabilidad
Mantenibilidad
Trazabilidad con CU
Consistencia del dominio
```

No crear:

```text
God classes
servicios gigantes
módulos que mezclen UI + dominio + persistencia
duplicación de validaciones
IA escribiendo directamente en base de datos
dependencias circulares entre paquetes
```

---

# 28. TRAZABILIDAD

Cada modificación significativa deberá poder relacionarse con:

```text
Caso de Uso
    |
    v
Responsabilidad de análisis
    |
    v
Paquete
    |
    v
Componente de diseño
    |
    v
Código
    |
    v
Prueba
```

Ejemplo:

```text
CU5
 ↓
Colaboración
 ↓
PA2
 ↓
Componente de colaboración
 ↓
Código
 ↓
Prueba de concurrencia
```

No deberá aparecer funcionalidad en el código que no tenga una justificación dentro de los requisitos o Diseño aprobado.

---

# 29. ESTRATEGIA DE IMPLEMENTACIÓN

Antigravity deberá abordar el proyecto incrementalmente.

## Fase 0 — Auditoría

Antes de modificar código deberá:

* inspeccionar el repositorio;
* identificar tecnologías existentes;
* identificar módulos existentes;
* identificar funcionalidades implementadas;
* relacionar código actual con CU1–CU14;
* identificar deuda técnica;
* identificar contradicciones con esta SPEC;
* identificar código reutilizable;
* identificar funcionalidades faltantes.

Resultado:

```text
CURRENT_STATE.md
```

o un reporte equivalente.

No debe reescribirse código funcional sin una justificación técnica.

---

## Fase 1 — Arquitectura

Antes de implementar nuevas funcionalidades deberá proponer cómo el código existente representará:

```text
PA1
PA2
PA3
PA4
```

Debe identificar:

* límites de módulos;
* dependencias permitidas;
* contratos;
* servicios compartidos;
* modelo de dominio;
* persistencia;
* puntos de extensión.

La arquitectura propuesta deberá respetar:

```text
PA2 ---> PA1
PA3 ---> PA1
```

y nunca:

```text
PA1 ---> PA2
PA1 ---> PA3
```

---

## Fase 2 — Iteración 1

Implementar o estabilizar:

```text
CU1
CU2
CU3
CU4
```

No avanzar hasta disponer de un núcleo UML consistente.

---

## Fase 3 — Iteración 2

Implementar:

```text
CU5
CU8
CU9
```

Prioridad técnica:

```text
CU5
```

por ser uno de los mayores riesgos de concurrencia.

---

## Fase 4 — Iteración 3

Implementar:

```text
CU6
CU7
CU10
CU11
```

Todo mecanismo inteligente deberá consumir las operaciones definidas previamente por el núcleo.

---

## Fase 5 — Iteración 4

Implementar:

```text
CU12
CU13
CU14
```

La aplicación móvil deberá probarse también sin conectividad real.

---

# 30. ESTRATEGIA DE PRUEBAS

Cada CU deberá poseer pruebas relacionadas con sus riesgos.

| Caso | Prueba mínima relevante                      |
| ---- | -------------------------------------------- |
| CU1  | Crear y recuperar lienzo                     |
| CU2  | Ingreso recuperando estado existente         |
| CU3  | CRUD consistente de elementos                |
| CU4  | Relaciones y referencias                     |
| CU5  | Dos usuarios modificando simultáneamente     |
| CU6  | Texto/voz → comando → modelo                 |
| CU7  | Imagen → propuesta → validación              |
| CU8  | Importación/exportación                      |
| CU9  | Errores y advertencias                       |
| CU10 | Proyecto generado ejecutable                 |
| CU11 | Colección coherente con endpoints            |
| CU12 | Operaciones del dominio                      |
| CU13 | Operación sin Internet + sincronización      |
| CU14 | Reconocimiento e interpretación sin Internet |

Las pruebas críticas deberán priorizar invariantes del dominio y comportamiento, no exclusivamente componentes visuales.

---

# 31. CRITERIOS DE ACEPTACIÓN GLOBALES

El sistema podrá considerarse funcionalmente coherente cuando pueda demostrarse el siguiente escenario:

```text
1. Un Anfitrión crea un lienzo.

2. Construye parte de un modelo.

3. Otro usuario ingresa y observa el mismo estado.

4. Ambos modifican el modelo colaborativamente.

5. El modelo puede ampliarse utilizando:
   - interfaz gráfica;
   - texto;
   - voz;
   - imagen;
   - importación externa.

6. El modelo puede validarse.

7. El modelo puede exportarse.

8. A partir del modelo válido se genera un backend Spring Boot.

9. Se generan recursos Postman coherentes.

10. El backend puede ejecutarse y probarse.

11. Una aplicación móvil consume los servicios generados.

12. La aplicación móvil ejecuta determinadas operaciones sin Internet.

13. Los cambios offline se sincronizan posteriormente.

14. Una operación móvil puede iniciarse mediante voz local sin depender obligatoriamente de Internet.
```

---

# 32. FUERA DE ALCANCE ACTUAL

Antigravity no deberá asumir como requisito obligatorio:

```text
generación automática del frontend móvil
generación de todos los diagramas UML existentes
microservicios
Kubernetes
cloud obligatorio
autenticación empresarial
IA específica
LLM específico
framework móvil específico
framework web específico
formato concreto de interoperabilidad
estrategia concreta de resolución de conflictos
```

Estas decisiones solamente podrán incorporarse cuando hayan sido justificadas en Diseño o ya formen parte verificable del código existente.

---

# 33. DECISIONES PENDIENTES DE DISEÑO

Antes de implementación definitiva todavía será necesario definir:

| Área                 | Decisión pendiente                     |
| -------------------- | -------------------------------------- |
| Arquitectura CASE    | estilo arquitectónico concreto         |
| Frontend CASE        | framework                              |
| Backend CASE         | framework                              |
| Persistencia CASE    | tecnología y esquema                   |
| Colaboración         | protocolo y estrategia de concurrencia |
| Interoperabilidad    | formato concreto                       |
| IA CASE              | proveedor/modelo/mecanismo             |
| Voz CASE             | mecanismo                              |
| Generador            | estructura y plantillas                |
| Aplicación móvil     | framework                              |
| BD local móvil       | tecnología                             |
| Sincronización       | estrategia de conflicto                |
| Voz móvil            | motor local                            |
| Interpretación móvil | modelo/motor local                     |

Antigravity deberá marcar estas decisiones como pendientes en vez de inventarlas.

---

# 34. INSTRUCCIÓN OPERATIVA PARA ANTIGRAVITY

Antes de escribir código:

1. Lee esta SPEC completa.

2. Analiza todo el repositorio existente.

3. Construye un mapa:

```text
CU → código actual → estado → deuda → cambio requerido
```

4. Determina si la arquitectura existente cumple PA1–PA4.

5. No elimines implementaciones funcionales únicamente para hacer coincidir nombres.

6. Prioriza refactorización incremental sobre reescritura.

7. Identifica las decisiones que pertenecen a Diseño.

8. Propón primero un plan técnico.

9. Para cada cambio indica:

```text
CU relacionado
problema
causa
solución
archivos afectados
riesgo
pruebas necesarias
```

10. Implementa posteriormente por iteraciones.

La documentación y el código deberán evolucionar juntos.

Una funcionalidad no deberá considerarse terminada hasta que:

```text
requisito
+
diseño
+
implementación
+
prueba
```

sean coherentes entre sí.

---

# 35. PRINCIPIO FINAL

La prioridad del proyecto no es simplemente conseguir que una demostración funcione.

El producto deberá mantener coherencia entre:

```text
REQUISITOS
     ↓
ANÁLISIS
     ↓
DISEÑO
     ↓
IMPLEMENTACIÓN
     ↓
PRUEBAS
```

Cada decisión de implementación debe poder explicarse desde una necesidad previamente identificada.

Cuando existan varias soluciones técnicamente posibles, deberá preferirse aquella que produzca:

```text
menor acoplamiento
mayor cohesión
mayor reutilización
mayor testabilidad
mayor mantenibilidad
y mayor correspondencia con los casos de uso
```