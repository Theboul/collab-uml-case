import { Injectable } from '@angular/core';
import { Graph, Node } from '@antv/x6';
import { UML_NODE_DIMENSIONS, UmlNodeSubElementEvent } from '../../domain/models/uml-editor.models';
import { buildUmlClassNodeVisual } from './uml-class-node-visual';
import { operationIndexAtY, operationRowRect } from './uml-class-node-layout';

@Injectable({
  providedIn: 'root',
})
export class UmlInteractionService {
  resolveSemanticTarget(
    graph: Graph | null,
    node: Node,
    clientX: number,
    clientY: number
  ): UmlNodeSubElementEvent | null {
    if (!graph) return null;
    const pos = node.getPosition();
    const size = node.getSize();
    const data = node.getData() || {};
    const localPoint = graph.clientToLocal(clientX, clientY);
    const relY = localPoint.y - pos.y;

    const operations: Array<{ id: string; name: string; returnType: string; visibility: string }> =
      data.operations || [];

    // Misma geometría con la que se dibujaron las filas (encabezado y filas envueltos incluidos).
    const { layout } = buildUmlClassNodeVisual(data, size.width);

    const nodeBBox = { x: pos.x, y: pos.y, width: size.width, height: size.height };

    // 1. Zona de Encabezado (Nombre de la Clase)
    if (relY <= layout.headerHeight) {
      return {
        classId: node.id,
        type: 'class',
        name: data.name || '',
        itemRelY: 4,
        nodeBBox,
        clientX,
        clientY,
      };
    }

    // 2. Zona de Atributos: filas reales con sus propios listeners nativos
    // (ver UmlAttributeRowsService) — un click que llega hasta acá es espacio en
    // blanco del compartimento, no resuelve a nada.
    if (relY < layout.sep2Y) {
      return null;
    }

    // 3. Zona de Operaciones: la fila se resuelve por geometría (una operación puede
    // ocupar varias líneas si su firma se envolvió).
    const opIndex = operationIndexAtY(layout, relY);
    const op = operations[opIndex];
    const rect = operationRowRect(layout, opIndex);
    if (!op || !rect) return null;

    return {
      classId: node.id,
      type: 'operation',
      elementId: op.id,
      name: op.name,
      typeOrReturn: op.returnType,
      visibility: op.visibility,
      itemRelY: rect.y,
      nodeBBox,
      clientX,
      clientY,
    };
  }

  setRowHighlight(
    graph: Graph | null,
    nodeId: string,
    itemRelY: number,
    height: number = UML_NODE_DIMENSIONS.LINE_HEIGHT
  ): void {
    if (!graph) return;
    const node = graph.getCellById(nodeId);
    if (!node || !node.isNode()) return;

    this.clearRowHighlight(graph);

    node.setAttrByPath('rowHighlight', {
      display: 'block',
      refX: 4,
      refY: itemRelY,
      refWidth: -8,
      height,
      fill: '#6366f1',
      fillOpacity: 0.12,
      stroke: '#818cf8',
      strokeWidth: 1,
      rx: 2,
      ry: 2,
      pointerEvents: 'none',
    });
  }

  clearRowHighlight(graph: Graph | null, nodeId?: string): void {
    if (!graph) return;
    if (nodeId) {
      const node = graph.getCellById(nodeId);
      if (node && node.isNode()) {
        node.setAttrByPath('rowHighlight/display', 'none');
      }
      return;
    }
    const nodes = graph.getNodes();
    for (const node of nodes) {
      node.setAttrByPath('rowHighlight/display', 'none');
    }
  }
}
