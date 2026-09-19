/**
 * Constantes de sintonía fina del streaming de arrastre remoto de nodos
 * (CU5, complemento en vivo al cursor). Único lugar donde ajustarlas tras la
 * prueba manual en el navegador — no repetir estos valores en otros archivos.
 */

/**
 * Cadencia de emisión de la posición del propio nodo mientras se arrastra (~30 msg/s).
 * El editor legacy emitía uno por frame (~60/s), pero por WebRTC P2P; acá cada mensaje
 * pasa por el servidor y se retransmite a todos los peers, así que se acota a uno cada 33 ms.
 */
export const NODE_DRAG_BROADCAST_THROTTLE_MS = 33;

/**
 * Si un nodo arrastrado por un peer remoto deja de recibir `node_drag` por
 * este lapso (desconexión abrupta, red perdida, pestaña cerrada a mitad de
 * arrastre), se lo devuelve activamente a su posición autoritativa conocida
 * en vez de dejarlo "pegado" a mitad de camino para siempre.
 */
export const NODE_DRAG_STALE_TTL_MS = 700;
