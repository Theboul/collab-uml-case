import { InjectionToken, inject } from '@angular/core';
import { Observable, Subject, of } from 'rxjs';
import { EditorCommand } from '../domain/commands/editor-commands';
import {
  CollaborationMessage,
  CursorPositionMessage,
  IncomingCursorEvent,
  NodeDragEndMessage,
  NodeDragMessage,
  RemoteNodeDragEvent,
} from '../domain/models/collaboration.models';
import { AuthService } from '../../../core/auth';

export interface CollaborationGateway {
  connect(canvasId: string): void;
  disconnect(): void;
  broadcastCommand(command: EditorCommand): void;
  sendCursorPosition(x: number, y: number): void;
  sendNodeDragPosition(nodeId: string, x: number, y: number): void;
  sendNodeDragEnd(nodeId: string): void;
  remoteCommands$: Observable<EditorCommand>;
  presence$: Observable<any>;
  remoteCursor$: Observable<IncomingCursorEvent>;
  remoteCanvasUpdate$: Observable<unknown>;
  remoteNodeDrag$: Observable<RemoteNodeDragEvent>;
  remoteNodeDragEnd$: Observable<string>;
}

export class NoOpCollaborationGateway implements CollaborationGateway {
  readonly remoteCommands$: Observable<EditorCommand> = of();
  readonly presence$: Observable<any> = of();
  readonly remoteCursor$: Observable<IncomingCursorEvent> = of();
  readonly remoteCanvasUpdate$: Observable<unknown> = of();
  readonly remoteNodeDrag$: Observable<RemoteNodeDragEvent> = of();
  readonly remoteNodeDragEnd$: Observable<string> = of();

  connect(_canvasId: string): void {
    // No-op — usado como test double cuando no hace falta un WS real.
  }

  disconnect(): void {
    // No-op
  }

  broadcastCommand(_command: EditorCommand): void {
    // No-op
  }

  sendCursorPosition(_x: number, _y: number): void {
    // No-op
  }

  sendNodeDragPosition(_nodeId: string, _x: number, _y: number): void {
    // No-op
  }

  sendNodeDragEnd(_nodeId: string): void {
    // No-op
  }
}

/**
 * Implementación real del canal de colaboración (ADR-0003). Paso 2: sólo
 * transporta cursores. `broadcastCommand`/`remoteCommands$`/`presence$`
 * quedan como no-ops deliberados todavía — aplicar comandos remotos es un
 * paso posterior del roadmap, no de este.
 */
export class WebSocketCollaborationGateway implements CollaborationGateway {
  constructor(private readonly authService: AuthService) {}

  private socket: WebSocket | null = null;
  private connectedCanvasId: string | null = null;

  private readonly remoteCursorSubject = new Subject<IncomingCursorEvent>();
  readonly remoteCursor$: Observable<IncomingCursorEvent> = this.remoteCursorSubject.asObservable();

  private readonly remoteCanvasUpdateSubject = new Subject<unknown>();
  readonly remoteCanvasUpdate$: Observable<unknown> = this.remoteCanvasUpdateSubject.asObservable();

  private readonly remoteNodeDragSubject = new Subject<RemoteNodeDragEvent>();
  readonly remoteNodeDrag$: Observable<RemoteNodeDragEvent> = this.remoteNodeDragSubject.asObservable();

  private readonly remoteNodeDragEndSubject = new Subject<string>();
  readonly remoteNodeDragEnd$: Observable<string> = this.remoteNodeDragEndSubject.asObservable();

  readonly remoteCommands$: Observable<EditorCommand> = of();
  readonly presence$: Observable<any> = of();

  connect(canvasId: string): void {
    if (this.connectedCanvasId === canvasId && this.socket) {
      return;
    }
    this.disconnect();

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const displayName = this.authService.currentUser()?.fullName ?? '';
    const url =
      `${protocol}://${window.location.host}/ws/canvas/${encodeURIComponent(canvasId)}/collaboration` +
      (displayName ? `?display_name=${encodeURIComponent(displayName)}` : '');

    this.connectedCanvasId = canvasId;
    this.socket = new WebSocket(url);
    this.socket.onmessage = (event) => {
      this.handleMessage(event);
    };
    this.socket.onerror = (err) => {
      console.warn('[Collaboration] Error en la conexión WebSocket de colaboración.', err);
    };
  }

  disconnect(): void {
    this.socket?.close();
    this.socket = null;
    this.connectedCanvasId = null;
  }

  broadcastCommand(_command: EditorCommand): void {
    // No-op deliberado en este paso — ver docstring de la clase.
  }

  sendCursorPosition(x: number, y: number): void {
    if (this.socket?.readyState !== WebSocket.OPEN) return;
    const message: CursorPositionMessage = { type: 'cursor', x, y };
    this.socket.send(JSON.stringify(message));
  }

  sendNodeDragPosition(nodeId: string, x: number, y: number): void {
    console.log('[DIAG] gateway.sendNodeDragPosition() called', {
      nodeId,
      x,
      y,
      socketState: this.socket?.readyState,
    });
    if (this.socket?.readyState !== WebSocket.OPEN) return;
    const message: NodeDragMessage = { type: 'node_drag', nodeId, x, y };
    console.log('[DIAG] gateway about to socket.send node_drag', message);
    this.socket.send(JSON.stringify(message));
  }

  sendNodeDragEnd(nodeId: string): void {
    if (this.socket?.readyState !== WebSocket.OPEN) return;
    const message: NodeDragEndMessage = { type: 'node_drag_end', nodeId };
    this.socket.send(JSON.stringify(message));
  }

  private handleMessage(event: MessageEvent<string>): void {
    let envelope: { from: string; fromDisplayName: string | null; payload: CollaborationMessage };
    try {
      envelope = JSON.parse(event.data);
    } catch {
      return;
    }

    if (envelope.payload?.type === 'cursor') {
      this.remoteCursorSubject.next({
        peerId: envelope.from,
        displayName: envelope.fromDisplayName,
        x: envelope.payload.x,
        y: envelope.payload.y,
      });
    } else if (envelope.payload?.type === 'canvas_update') {
      this.remoteCanvasUpdateSubject.next(envelope.payload.canvas);
    } else if (envelope.payload?.type === 'node_drag') {
      console.log('[DIAG] handleMessage received node_drag', envelope.payload);
      this.remoteNodeDragSubject.next({
        nodeId: envelope.payload.nodeId,
        x: envelope.payload.x,
        y: envelope.payload.y,
      });
    } else if (envelope.payload?.type === 'node_drag_end') {
      this.remoteNodeDragEndSubject.next(envelope.payload.nodeId);
    }
  }
}

export const COLLABORATION_GATEWAY = new InjectionToken<CollaborationGateway>(
  'COLLABORATION_GATEWAY',
  {
    providedIn: 'root',
    factory: () => new WebSocketCollaborationGateway(inject(AuthService)),
  }
);
