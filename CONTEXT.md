# CONTEXT.md

Lenguaje del dominio de SchemaCraft / Diagramador UML. Solo terminología: qué significa cada
palabra y cuáles se evitan. Nada de detalles de implementación.

## Lenguaje

**Lienzo**:
El espacio de trabajo persistente que se crea, abre, comparte y versiona. Contiene un Modelo y su
Diseño visual.
_Evitar_: Canvas, Diagrama, Workspace, espacio de trabajo

**Modelo**:
La parte semántica de un Lienzo: las Clases (con sus Atributos y Operaciones) y las Relaciones
entre ellas. No depende de cómo se dibuje.
_Evitar_: esquema, ModeloUML

**Diseño visual**:
La parte gráfica de un Lienzo: posiciones, tamaños, vértices de las Relaciones y encuadre.
Cambiarlo nunca cambia el Modelo.
_Evitar_: layout

**Sala**:
El grupo de Sesiones conectadas en vivo sobre un mismo Lienzo.
_Evitar_: room, usar `room_name` o `canvas_id` como sinónimo de Sala

**Sesión**:
Una conexión individual dentro de una Sala. Un mismo Colaborador con dos pestañas abiertas tiene
dos Sesiones.
_Evitar_: peer, peerId, conexión

**Anfitrión**:
La persona dueña de un Lienzo. Puede editarlo.

**Colaborador**:
Una persona que se unió a un Lienzo ajeno y puede editarlo. Es una persona, no una conexión: no se
confunde con la Sesión.
_Evitar_: peer, usuario (cuando se habla del rol)

**Invitado**:
Quien accede a un Lienzo sin haberse unido. Solo puede leerlo.

**Clase**:
Elemento del Modelo con Atributos y Operaciones. Puede ser abstracta.

**Interfaz**:
Elemento formal del Modelo que declara Operaciones que otras Clases realizan. No es una Clase
marcada como interfaz.
_Evitar_: Clase con bandera de interfaz

**Atributo**:
Propiedad estructural de una Clase.

**Operación**:
Comportamiento declarado por una Clase o una Interfaz. Es el único término para este concepto.
_Evitar_: método, methods

**Relación**:
Término paraguas para Asociación, Generalización, Realización y Dependencia. Se usa así en
documentos, API y eventos.
_Evitar_: Relationship, usar "asociación" para referirse a cualquier Relación

**Asociación**:
Relación estructural entre dos Clases (o Interfaces), con un extremo y una multiplicidad en cada
lado. Puede ser una agregación o una composición.

**Generalización**:
Relación de herencia entre una Clase específica y una general.

**Realización**:
Relación por la que una Clase implementa una Interfaz.

**Dependencia**:
Relación de uso débil entre dos Clases.

**Elemento**:
Término paraguas para Clase, Atributo, Operación y Relación, cuando un evento o una regla se
aplica a cualquiera de los cuatro.

**Bloqueo**:
Reserva temporal y exclusiva de un Elemento (Clase o Relación) adquirida por una Sesión para
su edición interactiva. Expira automáticamente por tiempo (TTL) si la Sesión no envía una
renovación periódica (heartbeat), y se libera al concluir la edición, al borrarse el Elemento
o al salir la Sesión de la Sala. Es advisory en el servidor pero restrictivo en la interfaz de
usuario.
_Evitar_: lock, cerrojo, mutex, reserva permanente

## Relaciones entre términos

- Un **Lienzo** tiene exactamente un **Modelo** y un **Diseño visual**.
- Un **Lienzo** tiene un **Anfitrión** y cero o más **Colaboradores**.
- Una **Sala** agrupa las **Sesiones** de un único **Lienzo**.
- Un **Colaborador** o un **Anfitrión** puede tener varias **Sesiones** a la vez.
- Un **Bloqueo** pertenece a una única **Sesión** sobre un **Elemento** de un **Lienzo**.
- Una **Relación** conecta Clases o Interfaces; una **Realización** conecta una Clase con una
  Interfaz.
