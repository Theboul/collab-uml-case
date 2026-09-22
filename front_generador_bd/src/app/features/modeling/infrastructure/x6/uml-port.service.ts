import { Injectable, inject } from '@angular/core';
import { Graph } from '@antv/x6';
import { EditorStateService } from '../../application/editor-state.service';

@Injectable({
  providedIn: 'root',
})
export class UmlPortService {
  private readonly editorState = inject(EditorStateService);

  showPorts(graph: Graph | null, nodeId: string): void {
    if (!graph) return;
    const node = graph.getCellById(nodeId);
    if (!node || !node.isNode()) return;
    const view = graph.findViewByCell(node);
    if (view) {
      view.addClass('uml-ports-visible');
    }
  }

  hidePorts(graph: Graph | null, nodeId: string): void {
    if (!graph) return;
    const node = graph.getCellById(nodeId);
    if (!node || !node.isNode()) return;
    const view = graph.findViewByCell(node);
    if (view) {
      view.removeClass('uml-ports-visible');
    }
  }

  hideAllPorts(graph: Graph | null): void {
    if (!graph) return;
    const nodes = graph.getNodes();
    for (const node of nodes) {
      const view = graph.findViewByCell(node);
      if (view) {
        view.removeClass('uml-ports-visible');
      }
    }
  }

  updatePortsVisibility(graph: Graph | null, selectedNodeIds: string[]): void {
    if (!graph) return;
    if (selectedNodeIds.length === 1) {
      const targetId = selectedNodeIds[0];
      const nodes = graph.getNodes();
      for (const node of nodes) {
        if (node.id === targetId) {
          this.showPorts(graph, node.id);
        } else {
          this.hidePorts(graph, node.id);
        }
      }
    } else {
      this.hideAllPorts(graph);
    }
  }

  validateMagnet(magnet: Element | null | undefined): boolean {
    return Boolean(magnet && magnet.getAttribute('magnet') === 'true');
  }

  validateConnection(
    arg1: unknown,
    arg2?: unknown,
    arg3?: Element | null,
    arg4?: Element | null,
    arg5?: string | null,
    arg6?: string | null,
  ): boolean {
    let sourceCell: { id?: string } | null | undefined;
    let targetCell: { id?: string } | null | undefined;
    let sourceMagnet: Element | null | undefined;
    let targetMagnet: Element | null | undefined;
    let sourcePort: string | null | undefined;
    let targetPort: string | null | undefined;

    if (arg1 && typeof arg1 === 'object' && 'sourceCell' in arg1) {
      const args = arg1 as {
        sourceCell?: { id?: string };
        targetCell?: { id?: string };
        sourceMagnet?: Element | null;
        targetMagnet?: Element | null;
        sourcePort?: string | null;
        targetPort?: string | null;
      };
      sourceCell = args.sourceCell;
      targetCell = args.targetCell;
      sourceMagnet = args.sourceMagnet;
      targetMagnet = args.targetMagnet;
      sourcePort = args.sourcePort;
      targetPort = args.targetPort;
    } else {
      sourceCell = arg1 as { id?: string } | null | undefined;
      targetCell = arg2 as { id?: string } | null | undefined;
      sourceMagnet = arg3;
      targetMagnet = arg4;
      sourcePort = arg5;
      targetPort = arg6;
    }

    if (!sourceCell || !targetCell) {
      return false;
    }
    if (!sourceMagnet || sourceMagnet.getAttribute('magnet') !== 'true') {
      return false;
    }
    if (targetMagnet && targetMagnet.getAttribute('magnet') !== 'true') {
      return false;
    }

    const sourceId = String(sourceCell.id);
    const targetId = String(targetCell.id);

    // Conexión reflexiva
    if (sourceCell === targetCell) {
      if (sourceMagnet && targetMagnet && sourceMagnet === targetMagnet) {
        return false;
      }
      if (sourcePort && targetPort && sourcePort === targetPort) {
        return false;
      }
      // No permitir doble relación reflexiva si ya existe
      if (this.editorState.hasRelationBetween(sourceId, targetId)) {
        return false;
      }
      return true;
    }

    // No permitir doble relación entre el mismo par de clases distintas
    if (this.editorState.hasRelationBetween(sourceId, targetId)) {
      return false;
    }

    return true;
  }
}
