import { Injectable, inject, signal } from '@angular/core';
import { COLLABORATION_GATEWAY } from './collaboration-gateway.service';
import { LockHolder } from '../domain/models/collaboration.models';
import { ToastService } from '../../../shared/ui/toast/toast.service';

export const LOCK_HEARTBEAT_INTERVAL_MS = 5000;
export const LOCK_INACTIVITY_TIMEOUT_MS = 60000;

export interface ActiveLocalLock {
  elementId: string;
  elementName: string;
  source: 'panel' | 'drag';
}

@Injectable({
  providedIn: 'root',
})
export class RemoteLocksService {
  private readonly gateway = inject(COLLABORATION_GATEWAY);
  private readonly toast = inject(ToastService);

  /** Locks vigentes en la sala sostenidos por otros peers: elementId -> LockHolder */
  private readonly _remoteLocks = signal<Record<string, LockHolder>>({});
  readonly remoteLocks = this._remoteLocks.asReadonly();

  /** Lock local activo que este cliente está sosteniendo y renovando */
  private readonly _localLock = signal<ActiveLocalLock | null>(null);
  readonly localLock = this._localLock.asReadonly();

  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private inactivityTimer: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    this.setupGatewaySubscriptions();
  }

  private setupGatewaySubscriptions(): void {
    this.gateway.locksSnapshot$.subscribe((snapshot) => {
      this.applyLocksSnapshot(snapshot.locks);
    });

    this.gateway.lockAcquired$.subscribe((message) => {
      this.handleLockAcquired(message.elementId, message.holder);
    });

    this.gateway.lockReleased$.subscribe((message) => {
      this.handleLockReleased(message.elementId);
    });

    this.gateway.lockDenied$.subscribe((message) => {
      this.handleLockDenied(message.elementId, message.reason, message.holder);
    });

    this.gateway.reconnected$.subscribe(() => {
      // Al reconectar, la sesión vieja en el servidor murió y sus locks expiraron o se liberaron.
      // El servidor enviará inmediatamente locks_snapshot fresco.
      this.stopHeartbeat();
      this.stopInactivityTimer();
      this._localLock.set(null);
      this._remoteLocks.set({});
    });
  }

  isLockedByOther(elementId: string): boolean {
    const current = this._remoteLocks();
    const holder = current[elementId];
    if (!holder) return false;
    // Ajuste B: si por cualquier razón llegara el propio peerId en remoteLocks, nunca auto-bloquearse
    const myPeerId = this.gateway.peerId;
    if (myPeerId && holder.sessionId === myPeerId) return false;
    return true;
  }

  getLockHolder(elementId: string): LockHolder | null {
    if (!this.isLockedByOther(elementId)) return null;
    return this._remoteLocks()[elementId] ?? null;
  }

  getLockHolderName(elementId: string): string | null {
    const holder = this.getLockHolder(elementId);
    if (!holder) return null;
    return holder.displayName || 'otro usuario';
  }

  isHeldLocally(elementId: string): boolean {
    return this._localLock()?.elementId === elementId;
  }

  /**
   * Adquiere el lock de un elemento al abrir su panel o empezar un arrastre.
   * Si ya tenía un lock en otro elemento, lo libera primero.
   */
  acquireLock(elementId: string, elementName: string, source: 'panel' | 'drag'): void {
    const current = this._localLock();
    if (current && current.elementId === elementId) {
      // Mismo elemento: registrar actividad y asegurarse de que los timers sigan activos
      this.recordActivity();
      return;
    }

    if (current && current.elementId !== elementId) {
      this.releaseLock(current.elementId);
    }

    this._localLock.set({ elementId, elementName, source });
    this.gateway.sendLockAcquire(elementId);

    this.startHeartbeat(elementId);
    this.resetInactivityTimer();
  }

  /**
   * Registra actividad del usuario (tecleo, cambio de propiedades, arrastre).
   * Reinicia el temporizador de inactividad de 60s.
   * Si el lock se había liberado por inactividad previa mientras el panel seguía abierto,
   * retoma la edición adquiriendo desde cero.
   */
  recordActivity(elementId?: string, elementName?: string): void {
    const current = this._localLock();
    if (current) {
      this.resetInactivityTimer();
    } else if (elementId) {
      // Reanuda adquisición desde cero tras inactividad
      this.acquireLock(elementId, elementName || 'elemento', 'panel');
    }
  }

  /**
   * Libera voluntariamente el lock al cerrar el panel o finalizar el arrastre normalmente.
   */
  releaseLock(elementId: string): void {
    const current = this._localLock();
    if (current && current.elementId === elementId) {
      this.stopHeartbeat();
      this.stopInactivityTimer();
      this._localLock.set(null);
      this.gateway.sendLockRelease(elementId);
    }
  }

  /**
   * Cierre de panel de edición de clase/relación.
   */
  onPanelClosed(elementId: string): void {
    this.releaseLock(elementId);
  }

  /**
   * Fin de arrastre de nodo: si el panel no sigue abierto para ese mismo nodo, liberar lock.
   */
  onNodeDragEnded(nodeId: string, isPanelOpenForNode: boolean): void {
    if (!isPanelOpenForNode) {
      this.releaseLock(nodeId);
    }
  }

  private startHeartbeat(elementId: string): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this._localLock()?.elementId === elementId) {
        this.gateway.sendLockAcquire(elementId);
      }
    }, LOCK_HEARTBEAT_INTERVAL_MS);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private resetInactivityTimer(): void {
    this.stopInactivityTimer();
    this.inactivityTimer = setTimeout(() => {
      this.handleInactivityTimeout();
    }, LOCK_INACTIVITY_TIMEOUT_MS);
  }

  private stopInactivityTimer(): void {
    if (this.inactivityTimer) {
      clearTimeout(this.inactivityTimer);
      this.inactivityTimer = null;
    }
  }

  private handleInactivityTimeout(): void {
    const current = this._localLock();
    if (!current) return;

    this.stopHeartbeat();
    this.stopInactivityTimer();
    this._localLock.set(null);
    this.gateway.sendLockRelease(current.elementId);

    const name = current.elementName || 'elemento';
    this.toast.show(`liberaste ${name} por inactividad`, 'info');
  }

  private applyLocksSnapshot(
    locks: { elementId: string; holder: LockHolder; ttlMs: number }[],
  ): void {
    const myPeerId = this.gateway.peerId;
    const nextLocks: Record<string, LockHolder> = {};

    for (const lock of locks) {
      // Ajuste B: no registrar como bloqueo remoto si el titular es nuestra propia sesión
      if (myPeerId && lock.holder.sessionId === myPeerId) {
        continue;
      }
      nextLocks[lock.elementId] = lock.holder;
    }

    this._remoteLocks.set(nextLocks);
  }

  private handleLockAcquired(elementId: string, holder: LockHolder): void {
    const myPeerId = this.gateway.peerId;
    // Ajuste B: Si es el eco de nuestra propia adquisición, no auto-bloquearse
    if (myPeerId && holder.sessionId === myPeerId) {
      return;
    }

    this._remoteLocks.update((current) => ({
      ...current,
      [elementId]: holder,
    }));

    // Si otro peer adquirió el elemento que creíamos tener, cancelar localmente
    const currentLocal = this._localLock();
    if (currentLocal && currentLocal.elementId === elementId) {
      this.stopHeartbeat();
      this.stopInactivityTimer();
      this._localLock.set(null);
    }
  }

  private handleLockReleased(elementId: string): void {
    this._remoteLocks.update((current) => {
      if (!current[elementId]) return current;
      const copy = { ...current };
      delete copy[elementId];
      return copy;
    });
  }

  private handleLockDenied(
    elementId: string,
    reason: 'held' | 'limit',
    holder: LockHolder | null,
  ): void {
    const currentLocal = this._localLock();
    if (currentLocal && currentLocal.elementId === elementId) {
      this.stopHeartbeat();
      this.stopInactivityTimer();
      this._localLock.set(null);
    }

    if (reason === 'held' && holder) {
      this._remoteLocks.update((current) => ({
        ...current,
        [elementId]: holder,
      }));
    } else if (reason === 'limit') {
      this.toast.show('demasiados elementos en edición a la vez', 'warning');
    }
  }

  /**
   * Limpia todo el estado de locks y temporizadores.
   */
  reset(): void {
    this.stopHeartbeat();
    this.stopInactivityTimer();
    this._localLock.set(null);
    this._remoteLocks.set({});
  }
}
