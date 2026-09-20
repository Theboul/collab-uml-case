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

/** Reconexión del canal de colaboración (ADR-0003, Addendum §7). */
export const RECONNECT_MIN_DELAY_MS = 1_000;
export const RECONNECT_MAX_DELAY_MS = 30_000;

/**
 * Reintentos consecutivos tras una caída antes de rendirse y avisar al usuario. Con el backoff
 * (1+2+4+8+16+30+30+30 s, cada uno con jitter del 50 % al 100 %) son entre 1 y 2 minutos.
 */
export const RECONNECT_MAX_ATTEMPTS = 8;

/**
 * Una conexión que se mantiene establecida este tiempo se considera estable y el contador de
 * fallos vuelve a cero. Sin esto, una conexión que se abre y se cae enseguida reiniciaría el
 * contador en cada apertura y reintentaría cada ~1 s para siempre.
 */
export const RECONNECT_STABLE_AFTER_MS = 10_000;

/**
 * Deltas ajenos que se retienen, en orden, mientras hay un arrastre local o una resincronización
 * en curso. Si se supera (un arrastre larguísimo con mucha actividad ajena) se descarta la cola y
 * se pide el lienzo completo al terminar: es más barato que acumular sin límite.
 */
export const MAX_QUEUED_DELTAS = 200;
