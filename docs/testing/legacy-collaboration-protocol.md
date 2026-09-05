# Protocolo de Operaciones y Colaboración Legacy

Este documento describe la especificación formal del protocolo de sincronización y colaboración multiusuario existente en el sistema legacy (Angular 20 + Django Channels + WebRTC DataChannels), establecido como línea base inmutable antes de la modernización arquitectónica.

---

## 1. Arquitectura del Flujo Colaborativo Legacy

El sistema opera bajo un esquema híbrido de señalización centralizada por WebSocket y transporte de datos P2P:

```text
[Cliente A (Peer)] <------ WebSockets (Django Channels) ------> [Cliente B (Peer)]
        |                 (Presencia, Announce, Offer/Answer)           |
        |                                                               |
        +<================ WebRTC DataChannel =========================>+
                           Canal 'canvas' (baja latencia)
                           Op: move, resize, edit_text, etc.
```

1. **Señalización (`CanvasConsumer` en Django Channels)**:
   * Canal: `ws://localhost:8000/ws/canvas/{room_name}/`
   * Eventos:
     * `presence` (`action: "join"` / `"leave"`): Informa la incorporación o retiro de un participante (`peer`).
     * `broadcast` (`payload: { type: 'announce' }`): Descubrimiento mutuo entre clientes.
     * `signal`: Intercambio de descriptores SDP (`offer`, `answer`) y candidatos ICE para la negociación de la conexión WebRTC.
2. **Canal de Datos P2P (`RTCDataChannel('canvas')`)**:
   * Una vez abierto (`dc.onopen`), el nuevo par solicita el estado actual mediante `{ t: 'request_full_state' }`.
   * Los pares sincronizan en tiempo real las operaciones gráficas y de edición.
3. **Mecanismo de Fallback de Respaldo**:
   * Si tras 3 segundos de conexión nadie responde a `request_full_state`, el cliente consulta la API REST de Django (`GET /api/get_backup_uml/{room_id}/`) para hidratar el canvas desde la base de datos PostgreSQL.

---

## 2. Catálogo Exhaustivo de Operaciones (`Op`) Legacy

Definidas en `front_generador_bd/src/services/colaboration/collaboration.service.ts`:

| Código de Operación (`t`) | Parámetros Principales | Propósito y Comportamiento |
| :--- | :--- | :--- |
| `add_class` | `id: string`, `payload: any` | Crea una nueva entidad de clase en el lienzo con coordenadas y atributos iniciales. |
| `edit_text` | `id: string`, `field: 'name' \| 'attributes' \| 'methods'`, `value: string` | Modifica el texto en línea de una caja de clase sin recrear la celda. |
| `move` | `id: string`, `x: number`, `y: number` | Actualiza la posición espacial de una clase tras arrastre en el canvas. |
| `resize` | `id: string`, `w: number`, `h: number` | Redimensiona el ancho y alto del nodo gráfico. |
| `add_link` | `id: string`, `sourceId: string`, `targetId: string`, `payload?: any` | Crea un enlace conectando dos clases existentes. |
| `edit_label` | `linkId: string`, `index: number`, `text: string` | Modifica la etiqueta de texto de una relación (ej. multiplicidades `*`, `1`). |
| `add_label` | `linkId: string`, `index: number`, `label: any` | Agrega una etiqueta visual a un conector. |
| `del_label` | `linkId: string`, `index: number` | Elimina una etiqueta de un conector. |
| `move_label` | `linkId: string`, `index: number`, `position: { distance, offset }` | Ajusta la posición de una etiqueta a lo largo de la línea del conector. |
| `move_link` | `id: string`, `sourceId: string`, `targetId: string` | Reconecta el extremo origen o destino de un enlace existente. |
| `update_vertices`| `id: string`, `vertices: { x, y }[]` | Actualiza los puntos de quiebre (waypoints) del conector. |
| `delete` | `id: string` | Elimina una celda (elemento o enlace) del lienzo. |
| `request_full_state` | *(Sin parámetros adicionales)* | Emitido por un cliente recién conectado para solicitar el grafo completo a los pares activos. |
| `full_state` | `payload: any` | Respuesta que empaqueta la totalidad de celdas del grafo JointJS serializadas para clonar el estado. |

---

## 3. Comportamientos y Limitaciones Caracterizadas

1. **Resolución de Conflictos Optimista sin Versionado**:
   * Las operaciones carecen de vector clocks, timestamps lógicos o identificadores de versión.
   * La última operación recibida sobreescribe directamente la propiedad en el grafo JointJS local (*Last-Write-Wins ciego*).
2. **Dependencia Total de JointJS Cells**:
   * `full_state` no envía un modelo UML semántico; serializa directamente las celdas SVG de JointJS (`graph.toJSON().cells`).
3. **Clasificación de Hallazgos**:
   * `EXPECTED LEGACY BEHAVIOR`: La señalización coordina conexiones P2P exitosamente entre 2 o 3 participantes en red local o con servidor STUN estándar.
   * `KNOWN LEGACY DEFECT`: Si dos usuarios editan simultáneamente atributos de la misma clase mediante `edit_text`, se produce una sobreescritura destructiva de texto sin mergeo ni lock preventivo.
