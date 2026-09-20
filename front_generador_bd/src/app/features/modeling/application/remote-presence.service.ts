import { Injectable, computed, inject, signal } from '@angular/core';
import { COLLABORATION_GATEWAY } from './collaboration-gateway.service';
import {
  PresencePeer,
  PresenceSession,
  pickColorForPeer,
} from '../domain/models/collaboration.models';

@Injectable({
  providedIn: 'root',
})
export class RemotePresenceService {
  private readonly gateway = inject(COLLABORATION_GATEWAY);

  /** Todas las sesiones activas en la sala */
  private readonly _sessions = signal<PresencePeer[]>([]);
  readonly sessions = this._sessions.asReadonly();

  /**
   * Sesiones remotas activas (excluye la propia sesión según gateway.peerId).
   * Estos son los colaboradores que se renderizan como chips en el header.
   */
  readonly remotePeers = computed(() => {
    const myPeerId = this.gateway.peerId;
    const all = this._sessions();
    if (!myPeerId) return all;
    return all.filter((s) => s.sessionId !== myPeerId);
  });

  constructor() {
    this.setupGatewaySubscriptions();
  }

  private setupGatewaySubscriptions(): void {
    this.gateway.presenceSnapshot$.subscribe((snapshot) => {
      this.applySnapshot(snapshot.sessions);
    });

    this.gateway.presenceJoined$.subscribe((message) => {
      this.handleJoined(message.session);
    });

    this.gateway.presenceLeft$.subscribe((message) => {
      this.handleLeft(message.sessionId);
    });

    this.gateway.reconnected$.subscribe(() => {
      // Al reconectar, limpiar presencia para recibir snapshot fresco del servidor
      this._sessions.set([]);
    });
  }

  private applySnapshot(sessions: PresenceSession[]): void {
    const peers: PresencePeer[] = sessions.map((s) => ({
      ...s,
      color: pickColorForPeer(s.sessionId),
    }));
    this._sessions.set(peers);
  }

  private handleJoined(session: PresenceSession): void {
    const newPeer: PresencePeer = {
      ...session,
      color: pickColorForPeer(session.sessionId),
    };
    this._sessions.update((current) => {
      const filtered = current.filter((s) => s.sessionId !== session.sessionId);
      return [...filtered, newPeer];
    });
  }

  private handleLeft(sessionId: string): void {
    this._sessions.update((current) => current.filter((s) => s.sessionId !== sessionId));
  }

  reset(): void {
    this._sessions.set([]);
  }
}
