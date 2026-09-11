import { Injectable, inject } from '@angular/core';
import { COLLABORATION_GATEWAY } from './collaboration-gateway.service';
import { EditorCommandService } from './editor-command.service';
import { EditorStateService } from './editor-state.service';
import { UmlApiService } from './uml-api.service';
import { RemoteNodeDragService } from './remote-node-drag.service';
import { UmlGraphService } from '../infrastructure/x6/uml-graph.service';
import { LienzoDetailDto } from '../domain/models/uml-editor.models';

/**
 * Aplica en vivo los snapshots que llegan por WS tras un comando exitoso de
 * otro peer (Problema B). El backend hace broadcast a toda la sala sin
 * excluir al emisor (ver routes.py); el guard de versión de acá se encarga
 * de descartar el propio eco y cualquier snapshot ya superado — nunca
 * pierde un cambio real: al ser concurrencia optimista con un único
 * contador de versión por lienzo, `state.version() >= dto.version` implica
 * que el estado local ya incluye todo lo que existía en esa versión.
 *
 * Mientras hay un arrastre local en curso (`UmlGraphService.isDraggingLocally`)
 * el snapshot NO se aplica de inmediato: `applyCanvasSnapshot` dispara
 * clearCells()+renderCells(), que destruye y recrea el nodo que el usuario
 * tiene agarrado con el mouse, cortando el gesto físico a mitad de camino
 * (diagnosticado con [DIAG-MOVE-COUNT]: `node:moved` volvía a disparar
 * decenas de veces por un solo drag). Se guarda solo el más reciente — no
 * hace falta una cola, porque al ser versiones estrictamente crecientes de
 * un único contador por lienzo, el más nuevo ya incluye todo lo del resto —
 * y se aplica recién cuando el drag local termina (`nodeMoved$`).
 *
 * El guard de versión se re-evalúa en ese momento, no cuando se recibió el
 * mensaje: es la comparación correcta, ya que lo que importa es si sigue
 * siendo más nuevo que el estado local justo antes de mutarlo, no en qué
 * instante llegó por WS. Si mientras tanto el estado local avanzó más allá
 * de esa versión por otra vía, igual se descarta sin pérdida — misma
 * garantía que ya vale para el caso sin diferir.
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

  constructor() {
    this.gateway.remoteCanvasUpdate$.subscribe((raw) => {
      const dto = this.api.normalizeCanvas(raw);

      if (this.graphService.isDraggingLocally) {
        if (!this.pendingSnapshot || dto.version > this.pendingSnapshot.version) {
          this.pendingSnapshot = dto;
        }
        return;
      }

      this.applyIfNewer(dto);
    });

    // Fin real de un arrastre local (contrato de X6: dispara una sola vez
    // por gesto) — momento de aplicar el snapshot que quedó diferido, si hay.
    this.graphService.nodeMoved$.subscribe(() => {
      if (!this.pendingSnapshot) return;
      const dto = this.pendingSnapshot;
      this.pendingSnapshot = null;
      this.applyIfNewer(dto);
    });
  }

  private applyIfNewer(dto: LienzoDetailDto): void {
    if (dto.version <= this.state.version()) return;
    this.editorCommand.applyCanvasSnapshot(dto);
    // El re-render completo que acaba de correr ya deja todos los nodos en
    // su posición autoritativa — cualquier arrastre remoto en vuelo queda
    // obsoleto; el próximo `node_drag` legítimo (si sigue en curso) se
    // vuelve a aplicar solo, sin efecto perceptible.
    this.remoteNodeDragService.clearAll();
  }
}
