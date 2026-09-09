import { Injectable } from '@angular/core';
import { Graph } from '@antv/x6';

@Injectable({
  providedIn: 'root',
})
export class UmlPortService {
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

  validateConnection(sourceCell: any, targetCell: any, sourceMagnet: Element | null | undefined): boolean {
    if (!sourceCell || !targetCell || sourceCell === targetCell) {
      return false;
    }
    if (!sourceMagnet || sourceMagnet.getAttribute('magnet') !== 'true') {
      return false;
    }
    return true;
  }
}
