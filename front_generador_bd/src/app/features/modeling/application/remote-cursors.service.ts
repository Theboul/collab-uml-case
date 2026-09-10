import { Injectable, inject, signal } from '@angular/core';
import { COLLABORATION_GATEWAY } from './collaboration-gateway.service';
import { RemoteCursor, pickColorForPeer } from '../domain/models/collaboration.models';

/** Si no llega una posición nueva de un peer en este lapso, se deja de renderizar su cursor. */
const STALE_CURSOR_TTL_MS = 5000;

/**
 * Mantiene el estado en vivo de los cursores remotos (ADR-0003, paso 2).
 * El backend no avisa cuando un peer se desconecta (sin broadcast de
 * "me fui" todavía), así que la limpieza es por TTL: si un peer deja de
 * mandar posición, su cursor desaparece solo — cubre desconexiones
 * normales y anormales por igual, sin depender de un evento explícito.
 */
@Injectable({
  providedIn: 'root',
})
export class RemoteCursorsService {
  private readonly gateway = inject(COLLABORATION_GATEWAY);

  private readonly cursorsByPeer = new Map<string, RemoteCursor>();
  private readonly staleTimers = new Map<string, ReturnType<typeof setTimeout>>();

  readonly cursors = signal<RemoteCursor[]>([]);

  constructor() {
    this.gateway.remoteCursor$.subscribe((event) => {
      this.cursorsByPeer.set(event.peerId, {
        ...event,
        color: pickColorForPeer(event.peerId),
      });
      this.scheduleStaleRemoval(event.peerId);
      this.publish();
    });
  }

  private scheduleStaleRemoval(peerId: string): void {
    const existing = this.staleTimers.get(peerId);
    if (existing) clearTimeout(existing);

    const timer = setTimeout(() => {
      this.cursorsByPeer.delete(peerId);
      this.staleTimers.delete(peerId);
      this.publish();
    }, STALE_CURSOR_TTL_MS);
    this.staleTimers.set(peerId, timer);
  }

  private publish(): void {
    this.cursors.set(Array.from(this.cursorsByPeer.values()));
  }

  /** Limpia todo el estado — se llama al salir de un lienzo. */
  reset(): void {
    for (const timer of this.staleTimers.values()) clearTimeout(timer);
    this.staleTimers.clear();
    this.cursorsByPeer.clear();
    this.publish();
  }
}
