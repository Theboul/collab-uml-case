import { Injectable, inject } from '@angular/core';
import { COLLABORATION_GATEWAY } from './collaboration-gateway.service';
import { MAX_QUEUED_DELTAS } from './collaboration-tuning';
import { EditorCommandService } from './editor-command.service';
import { EditorStateService } from './editor-state.service';
import { UmlApiService } from './uml-api.service';
import { RemoteNodeDragService } from './remote-node-drag.service';
import { UmlGraphService } from '../infrastructure/x6/uml-graph.service';
import { applyCanvasDelta, CanvasDeltaMessage } from '../domain/canvas-delta';
import { LienzoDetailDto } from '../domain/models/uml-editor.models';

/**
 * Pone al día el lienzo local con los cambios que otros peers confirman (CU5, ADR-0003 Addendum).
 *
 * El servidor difunde un `canvas_delta` por cada versión: qué clases y relaciones cambiaron y qué
 * posiciones se movieron, no el lienzo entero. Cada delta parte de `fromVersion` y lleva a
 * `toVersion = fromVersion + 1`, así que este servicio solo lo aplica si el estado local está
 * EXACTAMENTE en `fromVersion`:
 *
 *   - `toVersion <= version`  → ya está incluido (p. ej. el propio cambio): se descarta.
 *   - `fromVersion == version` → se aplica.
 *   - cualquier otro caso      → falta al menos un delta intermedio: se pide el lienzo completo
 *                                 (`resync`) y los deltas que llegan mientras tanto esperan.
 *
 * Un snapshot completo (el de un `resync` o el de tras reconectar) entra por su propia vía y se
 * aplica si es más nuevo que el estado local; después se aplican los deltas en espera.
 *
 * Mientras hay un arrastre local en curso (`UmlGraphService.isDraggingLocally`) nada se aplica de
 * inmediato: `applyCanvasContent` re-renderiza el grafo y puede cortar el gesto del usuario a mitad
 * de camino (diagnosticado con [DIAG-MOVE-COUNT]: `node:moved` volvía a disparar decenas de veces
 * por un solo drag). Los deltas NO se pueden colapsar en el más reciente como los snapshots —
 * cada uno depende del anterior—, así que se guardan todos, en orden, y se aplican cuando el drag
 * termina (`nodeMoved$`). Si la cola se desborda se descarta y se resincroniza.
 */
@Injectable({
  providedIn: 'root',
})
export class RemoteCanvasSyncService {
  private readonly gateway = inject(COLLABORATION_GATEWAY);
  private readonly api = inject(UmlApiService);
  private readonly state = inject(EditorStateService);
  private readonly editorCommand = inject(EditorCommandService);
  private readonly remoteNodeDragService = inject(RemoteNodeDragService);
  private readonly graphService = inject(UmlGraphService);

  private pendingSnapshot: LienzoDetailDto | null = null;
  private pendingDeltas: CanvasDeltaMessage[] = [];
  private queueOverflowed = false;
  private resyncing = false;

  constructor() {
    this.gateway.remoteCanvasDelta$.subscribe((message) => this.receiveDelta(message));

    // Tras reabrir el canal (una caída de red, un reinicio del servidor) pudo perderse algún cambio
    // ajeno: se pide el estado actual y entra por la misma vía que cualquier snapshot.
    this.gateway.reconnected$.subscribe(() => this.resync());

    // Fin real de un arrastre local (contrato de X6: dispara una sola vez por gesto) — momento de
    // aplicar lo que quedó en espera.
    this.graphService.nodeMoved$.subscribe(() => this.drain());
  }

  /** Aplazar todo mientras el usuario arrastra un nodo o mientras llega el snapshot pedido. */
  private get mustWait(): boolean {
    return this.graphService.isDraggingLocally || this.resyncing;
  }

  private receiveDelta(message: CanvasDeltaMessage, canResync = true): void {
    if (this.mustWait) {
      this.enqueue(message);
      return;
    }
    this.applyDelta(message, canResync);
  }

  private enqueue(message: CanvasDeltaMessage): void {
    if (this.pendingDeltas.length >= MAX_QUEUED_DELTAS) {
      this.pendingDeltas = [];
      this.queueOverflowed = true;
      return;
    }
    this.pendingDeltas.push(message);
  }

  private applyDelta(message: CanvasDeltaMessage, canResync: boolean): void {
    const version = this.state.version();
    if (message.toVersion <= version) return;

    if (message.fromVersion !== version) {
      // Hueco: falta al menos un delta. Se conserva este por si, tras el snapshot, encadena.
      // Si el hueco persiste justo después de un resync (una réplica atrasada, un servidor
      // incoherente) no se vuelve a pedir en bucle: se descarta y el siguiente delta reintenta.
      if (!canResync) {
        console.warn('[Collaboration] Hueco de versión tras resincronizar; se descarta el delta.');
        return;
      }
      this.enqueue(message);
      this.resync();
      return;
    }

    try {
      const next = applyCanvasDelta(
        { model: this.state.model(), layout: this.state.layout() },
        message.delta,
        (wire) => this.api.normalizeRelationsPart(wire),
      );
      this.editorCommand.applyCanvasContent(next.model, next.layout, message.toVersion);
    } catch (err) {
      // Un delta que no se deja aplicar (forma inesperada) no debe dejar el lienzo a medias.
      console.error('[Collaboration] No se pudo aplicar un canvas_delta; se resincroniza.', err);
      this.resync();
      return;
    }
    // Tras el re-render los nodos ya están en su posición autoritativa: cualquier arrastre remoto
    // en vuelo queda obsoleto; el próximo `node_drag` legítimo se vuelve a aplicar solo.
    this.remoteNodeDragService.clearAll();
  }

  private resync(): void {
    const canvasId = this.state.canvasId();
    if (!canvasId || this.resyncing) return;
    this.resyncing = true;
    this.api.getCanvas(canvasId).subscribe({
      next: (dto) => {
        this.resyncing = false;
        this.receiveSnapshot(dto);
      },
      error: (err) => {
        this.resyncing = false;
        console.error('[Collaboration] No se pudo resincronizar tras reconectar.', err);
        this.drain(true);
      },
    });
  }

  /** Un snapshot completo: se difiere durante un arrastre local; si no, se aplica y se sigue con la cola. */
  private receiveSnapshot(dto: LienzoDetailDto): void {
    if (this.graphService.isDraggingLocally) {
      if (!this.pendingSnapshot || dto.version > this.pendingSnapshot.version) {
        this.pendingSnapshot = dto;
      }
      return;
    }
    this.applySnapshotIfNewer(dto);
    this.drain(true);
  }

  /**
   * Aplica lo que esperaba (primero el snapshot, luego los deltas en orden) si ya no hay que esperar.
   * `afterResync`: viene de un intento de resync, así que un hueco que quede no lanza otro.
   */
  private drain(afterResync = false): void {
    if (this.mustWait) return;

    if (this.pendingSnapshot) {
      const dto = this.pendingSnapshot;
      this.pendingSnapshot = null;
      this.applySnapshotIfNewer(dto);
    }

    if (this.queueOverflowed) {
      this.queueOverflowed = false;
      this.resync();
      return;
    }

    // `receiveDelta` vuelve a encolar si a mitad de la cola aparece un hueco y arranca un resync.
    const queued = this.pendingDeltas;
    this.pendingDeltas = [];
    for (const message of queued) this.receiveDelta(message, !afterResync);
  }

  private applySnapshotIfNewer(dto: LienzoDetailDto): void {
    if (dto.version <= this.state.version()) return;
    this.editorCommand.applyCanvasSnapshot(dto);
    this.remoteNodeDragService.clearAll();
  }
}
