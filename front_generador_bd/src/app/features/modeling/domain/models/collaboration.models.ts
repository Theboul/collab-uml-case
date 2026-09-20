/**
 * Contrato de mensajes del canal de colaboración en tiempo real (ADR-0003).
 * El backend valida los mensajes del cliente (`cursor`, `node_drag`, `node_drag_end`) y los
 * reenvía a la Sala; `canvas_delta` solo lo emite el servidor tras confirmar un cambio
 * (contrato `contracts/canvas-delta.v1.json`). La unión de tipos vive acá para que emisor y
 * receptor se pongan de acuerdo, y para que los mensajes de pasos futuros (lock, etc.) puedan
 * sumarse sin ambigüedad.
 */

import type { CanvasDeltaMessage } from '../canvas-delta';

export interface CursorPositionMessage {
  type: 'cursor';
  x: number;
  y: number;
}

/** Posición en vivo de un nodo siendo arrastrado por un peer, efímera y sin persistir. */
export interface NodeDragMessage {
  type: 'node_drag';
  nodeId: string;
  x: number;
  y: number;
}

/** Fin del arrastre en vivo — el resultado final llega por su lado vía `canvas_delta`. */
export interface NodeDragEndMessage {
  type: 'node_drag_end';
  nodeId: string;
}

export interface LockHolder {
  sessionId: string;
  userId: string | null;
  displayName: string | null;
}

export interface LockAcquireMessage {
  type: 'lock_acquire';
  elementId: string;
}

export interface LockReleaseMessage {
  type: 'lock_release';
  elementId: string;
}

export interface LockAcquiredMessage {
  type: 'lock_acquired';
  elementId: string;
  holder: LockHolder;
  ttlMs: number;
}

export interface LockReleasedMessage {
  type: 'lock_released';
  elementId: string;
}

export interface LockDeniedMessage {
  type: 'lock_denied';
  elementId: string;
  reason: 'held' | 'limit';
  holder: LockHolder | null;
}

export interface LocksSnapshotMessage {
  type: 'locks_snapshot';
  locks: {
    elementId: string;
    holder: LockHolder;
    ttlMs: number;
  }[];
}

export interface PresenceSession {
  sessionId: string;
  userId: string | null;
  displayName: string | null;
}

export interface PresencePeer extends PresenceSession {
  color: string;
}

export interface PresenceSnapshotMessage {
  type: 'presence_snapshot';
  sessions: PresenceSession[];
}

export interface PresenceJoinedMessage {
  type: 'presence_joined';
  session: PresenceSession;
}

export interface PresenceLeftMessage {
  type: 'presence_left';
  sessionId: string;
}

export type CollaborationMessage =
  | CursorPositionMessage
  | CanvasDeltaMessage
  | NodeDragMessage
  | NodeDragEndMessage
  | LockAcquireMessage
  | LockReleaseMessage
  | LockAcquiredMessage
  | LockReleasedMessage
  | LockDeniedMessage
  | LocksSnapshotMessage
  | PresenceSnapshotMessage
  | PresenceJoinedMessage
  | PresenceLeftMessage;

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
