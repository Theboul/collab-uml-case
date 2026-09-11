import { Injectable, inject } from '@angular/core';
import { COLLABORATION_GATEWAY } from './collaboration-gateway.service';
import { EditorStateService } from './editor-state.service';
import { UmlGraphService } from '../infrastructure/x6/uml-graph.service';
import { NODE_DRAG_STALE_TTL_MS } from './collaboration-tuning';

/**
 * Aplica en vivo la posición de un nodo que un peer remoto está arrastrando
 * (streaming efímero, sin persistencia — el resultado final llega por su
 * lado vía `canvas_update`, ya con guard de versión en RemoteCanvasSyncService).
 *
 * Solo toca el grafo X6 (vía UmlGraphService.setNodePositionSilent) — nunca
 * el modelo de dominio, ni dispara comando ni historial local.
 *
 * Protección contra el nodo "pegado" a mitad de camino: cada posición
 * recibida resetea un TTL por nodeId; si expira sin un nuevo `node_drag` ni
 * un `node_drag_end` explícito (peer desconectado a mitad de arrastre), el
 * nodo se devuelve activamente a su última posición autoritativa conocida
 * (`EditorStateService.layout()`), en vez de quedar congelado para siempre.
 */
@Injectable({
  providedIn: 'root',
})
export class RemoteNodeDragService {
  private readonly gateway = inject(COLLABORATION_GATEWAY);
  private readonly state = inject(EditorStateService);
  private readonly graphService = inject(UmlGraphService);

  private readonly staleTimers = new Map<string, ReturnType<typeof setTimeout>>();

  constructor() {
    this.gateway.remoteNodeDrag$.subscribe(({ nodeId, x, y }) => {
      const cell = this.graphService.rawGraph?.getCellById(nodeId);
      console.log('[DIAG] RemoteNodeDragService received remoteNodeDrag$', {
        nodeId,
        x,
        y,
        cellFound: !!cell,
        isNode: cell?.isNode?.() ?? null,
      });
      this.graphService.setNodePositionSilent(nodeId, x, y);
      this.scheduleStaleSnapBack(nodeId);
    });

    this.gateway.remoteNodeDragEnd$.subscribe((nodeId) => {
      this.clearNode(nodeId);
    });
  }

  private scheduleStaleSnapBack(nodeId: string): void {
    const existing = this.staleTimers.get(nodeId);
    if (existing) clearTimeout(existing);

    const timer = setTimeout(() => {
      this.snapToAuthoritativePosition(nodeId);
      this.staleTimers.delete(nodeId);
    }, NODE_DRAG_STALE_TTL_MS);
    this.staleTimers.set(nodeId, timer);
  }

  private snapToAuthoritativePosition(nodeId: string): void {
    const nodeLayout = this.state.layout().nodes[nodeId];
    if (!nodeLayout) return;
    this.graphService.setNodePositionSilent(nodeId, nodeLayout.x, nodeLayout.y);
  }

  private clearNode(nodeId: string): void {
    const timer = this.staleTimers.get(nodeId);
    if (timer) clearTimeout(timer);
    this.staleTimers.delete(nodeId);
  }

  /** Cancela todo el tracking en curso — se llama tras aplicar cada `canvas_update` (ver RemoteCanvasSyncService) y al salir del lienzo. */
  clearAll(): void {
    for (const timer of this.staleTimers.values()) clearTimeout(timer);
    this.staleTimers.clear();
  }

  /** Alias semántico de `clearAll()` para el cleanup al salir del lienzo (mismo patrón que RemoteCursorsService.reset()). */
  reset(): void {
    this.clearAll();
  }
}
