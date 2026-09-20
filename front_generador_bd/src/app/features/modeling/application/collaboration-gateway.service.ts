import { InjectionToken, Signal, inject, signal } from '@angular/core';
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
import { RECONNECT_STABLE_AFTER_MS } from './collaboration-tuning';
import { decideAfterClose } from './reconnect-policy';

/** Estado del canal de colaboración, para mostrárselo al usuario. */
export type CollaborationConnectionState =
  | 'idle'
  | 'connecting'
  | 'open'
  | 'reconnecting'
  /** Reintentos agotados o token no renovable: hay un botón "Reintentar". */
  | 'failed'
  /** El servidor cerró con 4403: sin permiso sobre el lienzo, no se reintenta. */
  | 'denied';

export interface CollaborationGateway {
  connect(canvasId: string): void;
  disconnect(): void;
  /** Reintento manual desde `failed`. */
  retry(): void;
  readonly connectionState: Signal<CollaborationConnectionState>;
  /** Emite cada vez que el canal se establece tras una caída: hay que resincronizar. */
  readonly reconnected$: Observable<void>;
  broadcastCommand(command: EditorCommand): void;
  sendCursorPosition(x: number, y: number): void;
  sendNodeDragPosition(nodeId: string, x: number, y: number): void;
  sendNodeDragEnd(nodeId: string): void;
  readonly peerId: string | null;
  remoteCommands$: Observable<EditorCommand>;
  presence$: Observable<any>;
  remoteCursor$: Observable<IncomingCursorEvent>;
  remoteCanvasUpdate$: Observable<unknown>;
  remoteNodeDrag$: Observable<RemoteNodeDragEvent>;
  remoteNodeDragEnd$: Observable<string>;
}

export class NoOpCollaborationGateway implements CollaborationGateway {
  readonly peerId: string | null = null;
  readonly remoteCommands$: Observable<EditorCommand> = of();
  readonly presence$: Observable<any> = of();
  readonly remoteCursor$: Observable<IncomingCursorEvent> = of();
  readonly remoteCanvasUpdate$: Observable<unknown> = of();
  readonly remoteNodeDrag$: Observable<RemoteNodeDragEvent> = of();
  readonly remoteNodeDragEnd$: Observable<string> = of();
  readonly reconnected$: Observable<void> = of();
  readonly connectionState: Signal<CollaborationConnectionState> =
    signal<CollaborationConnectionState>('idle').asReadonly();

  connect(_canvasId: string): void {
    // No-op — usado como test double cuando no hace falta un WS real.
  }

  disconnect(): void {
    // No-op
  }

  retry(): void {
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
  constructor(
    private readonly authService: AuthService,
    private readonly wsBaseUrl: string = defaultWsBaseUrl(),
  ) {}

  private socket: WebSocket | null = null;
  private connectedCanvasId: string | null = null;
  private _peerId: string | null = null;

  get peerId(): string | null {
    return this._peerId;
  }

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

  private readonly state = signal<CollaborationConnectionState>('idle');
  readonly connectionState: Signal<CollaborationConnectionState> = this.state.asReadonly();

  private readonly reconnectedSubject = new Subject<void>();
  readonly reconnected$: Observable<void> = this.reconnectedSubject.asObservable();

  private failedAttempts = 0; // reintentos consecutivos ya fallidos
  private tokenRefreshed = false; // el 4401 solo se intenta una vez por ciclo
  private hadDrop = false; // hubo una caída: la próxima vez que se establezca hay que resincronizar
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private stableTimer: ReturnType<typeof setTimeout> | null = null;

  connect(canvasId: string): void {
    if (this.connectedCanvasId === canvasId && (this.socket || this.retryTimer)) {
      return;
    }
    this.disconnect();

    this.connectedCanvasId = canvasId;
    this.state.set('connecting');
    this.openSocket(canvasId);
  }

  disconnect(): void {
    this.clearTimers();
    const socket = this.socket;
    this.socket = null; // su onclose se ignora: ya no es `this.socket`
    this.connectedCanvasId = null;
    this._peerId = null;
    this.failedAttempts = 0;
    this.tokenRefreshed = false;
    this.hadDrop = false;
    this.state.set('idle');
    socket?.close();
  }

  retry(): void {
    const canvasId = this.connectedCanvasId;
    if (!canvasId || this.state() !== 'failed') return;
    this.failedAttempts = 0;
    this.tokenRefreshed = false;
    this.state.set('connecting');
    this.openSocket(canvasId);
  }

  private openSocket(canvasId: string): void {
    const displayName = this.authService.currentUser()?.fullName ?? '';
    // El token se lee en cada intento: tras un 4401 es el recién renovado.
    const token = this.authService.accessToken();
    const params = new URLSearchParams();
    if (displayName) params.set('display_name', displayName);
    const queryString = params.toString();
    const url =
      `${this.wsBaseUrl}/ws/canvas/${encodeURIComponent(canvasId)}/collaboration` +
      (queryString ? `?${queryString}` : '');

    // El JWT viaja como subprotocolo (`Sec-WebSocket-Protocol: bearer, <jwt>`), no en la URL.
    const socket = new WebSocket(url, token ? ['bearer', token] : undefined);
    this.socket = socket;
    socket.onmessage = (event) => {
      this.handleMessage(event);
    };
    socket.onerror = (err) => {
      console.warn('[Collaboration] Error en la conexión WebSocket de colaboración.', err);
    };
    socket.onclose = (event) => {
      this.handleClose(socket, event);
    };
  }

  /**
   * El canal se da por establecido cuando llega `connected` (la Sesión ya entró a la Sala), no con
   * `onopen`: el servidor acepta siempre y puede cerrar enseguida con 4401/4403.
   */
  private handleEstablished(): void {
    this.state.set('open');
    this.clearStableTimer();
    this.stableTimer = setTimeout(() => {
      this.failedAttempts = 0;
      this.tokenRefreshed = false;
    }, RECONNECT_STABLE_AFTER_MS);
    if (this.hadDrop) {
      this.hadDrop = false;
      this.reconnectedSubject.next();
    }
  }

  private handleClose(socket: WebSocket, event: CloseEvent): void {
    if (socket !== this.socket) return; // socket viejo o cierre intencional
    this.socket = null;
    this._peerId = null;
    this.clearStableTimer();
    this.hadDrop = true;
    const canvasId = this.connectedCanvasId;
    if (!canvasId) return;

    const decision = decideAfterClose(event.code, this.failedAttempts, this.tokenRefreshed);
    switch (decision.action) {
      case 'give-up':
        this.state.set(decision.reason === 'forbidden' ? 'denied' : 'failed');
        return;
      case 'refresh-token':
        this.state.set('reconnecting');
        this.authService.refreshSession().subscribe({
          next: () => {
            if (this.connectedCanvasId !== canvasId) return; // hubo un disconnect() mientras tanto
            this.tokenRefreshed = true;
            this.openSocket(canvasId);
          },
          error: () => this.state.set('failed'),
        });
        return;
      case 'retry':
        this.failedAttempts += 1;
        this.state.set('reconnecting');
        this.retryTimer = setTimeout(() => {
          this.retryTimer = null;
          this.openSocket(canvasId);
        }, decision.delayMs);
        return;
    }
  }

  private clearStableTimer(): void {
    if (this.stableTimer) clearTimeout(this.stableTimer);
    this.stableTimer = null;
  }

  private clearTimers(): void {
    this.clearStableTimer();
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = null;
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
    if (this.socket?.readyState !== WebSocket.OPEN) return;
    const message: NodeDragMessage = { type: 'node_drag', nodeId, x, y };
    this.socket.send(JSON.stringify(message));
  }

  sendNodeDragEnd(nodeId: string): void {
    if (this.socket?.readyState !== WebSocket.OPEN) return;
    const message: NodeDragEndMessage = { type: 'node_drag_end', nodeId };
    this.socket.send(JSON.stringify(message));
  }

  private handleMessage(event: MessageEvent<string>): void {
    let parsed: unknown;
    try {
      parsed = JSON.parse(event.data);
    } catch {
      return;
    }

    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      (parsed as { type?: string }).type === 'connected'
    ) {
      this._peerId = (parsed as { peerId?: string }).peerId ?? null;
      this.handleEstablished();
      return;
    }

    const envelope = parsed as {
      from: string;
      fromDisplayName: string | null;
      payload: CollaborationMessage;
    };

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

function defaultWsBaseUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${protocol}://${window.location.host}`;
}

export const COLLABORATION_GATEWAY = new InjectionToken<CollaborationGateway>(
  'COLLABORATION_GATEWAY',
  {
    providedIn: 'root',
    factory: () => new WebSocketCollaborationGateway(inject(AuthService)),
  }
);
