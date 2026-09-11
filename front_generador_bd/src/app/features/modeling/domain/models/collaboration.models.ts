/**
 * Contrato de mensajes del canal de colaboración en tiempo real (ADR-0003).
 * El backend (`collaboration/room_registry.py`) es un relay opaco: no conoce
 * `type`, sólo reenvía el JSON tal cual. La unión de tipos vive acá para que
 * emisor y receptor (ambos en el frontend) se pongan de acuerdo, y para que
 * los mensajes de pasos futuros (lock, etc.) puedan sumarse sin ambigüedad.
 */

export interface CursorPositionMessage {
  type: 'cursor';
  x: number;
  y: number;
}

/** Snapshot completo del lienzo tras un comando exitoso de otro peer (Problema B). */
export interface CanvasUpdateMessage {
  type: 'canvas_update';
  canvas: unknown;
}

/** Posición en vivo de un nodo siendo arrastrado por un peer, efímera y sin persistir. */
export interface NodeDragMessage {
  type: 'node_drag';
  nodeId: string;
  x: number;
  y: number;
}

/** Fin del arrastre en vivo — el resultado final llega por su lado vía `canvas_update`. */
export interface NodeDragEndMessage {
  type: 'node_drag_end';
  nodeId: string;
}

export type CollaborationMessage =
  | CursorPositionMessage
  | CanvasUpdateMessage
  | NodeDragMessage
  | NodeDragEndMessage;

/** Evento crudo de arrastre remoto tal como lo entrega el gateway. */
export interface RemoteNodeDragEvent {
  nodeId: string;
  x: number;
  y: number;
}

/** Evento crudo tal como lo entrega el gateway (sin color asignado todavía). */
export interface IncomingCursorEvent {
  peerId: string;
  displayName: string | null;
  x: number;
  y: number;
}

/** View-model listo para renderizar, con color determinístico ya asignado. */
export interface RemoteCursor extends IncomingCursorEvent {
  color: string;
}

/**
 * Paleta fija de colores distintivos por peer. Asignación determinística por
 * `peerId` (mismo peer, mismo color durante toda la sesión, sin coordinación
 * con el servidor).
 */
const CURSOR_COLOR_PALETTE: readonly string[] = [
  '#ef4444',
  '#f97316',
  '#eab308',
  '#22c55e',
  '#06b6d4',
  '#3b82f6',
  '#8b5cf6',
  '#ec4899',
];

export function pickColorForPeer(peerId: string): string {
  let hash = 0;
  for (let i = 0; i < peerId.length; i++) {
    hash = (hash * 31 + peerId.charCodeAt(i)) >>> 0;
  }
  return CURSOR_COLOR_PALETTE[hash % CURSOR_COLOR_PALETTE.length];
}
