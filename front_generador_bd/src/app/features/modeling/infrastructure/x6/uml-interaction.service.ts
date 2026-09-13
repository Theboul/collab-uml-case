import { Injectable } from '@angular/core';
import { Graph, Node } from '@antv/x6';
import { UML_NODE_DIMENSIONS, UmlNodeSubElementEvent } from '../../domain/models/uml-editor.models';
import { visibleAttributeRowCount } from './uml-class-node-visual';

@Injectable({
  providedIn: 'root',
})
export class UmlInteractionService {
  resolveSemanticTarget(
    graph: Graph | null,
    node: Node,
    clientX: number,
    clientY: number,
    targetElem?: SVGElement | null
  ): UmlNodeSubElementEvent | null {
    if (!graph) return null;
    const pos = node.getPosition();
    const size = node.getSize();
    const data = node.getData() || {};
    const localPoint = graph.clientToLocal(clientX, clientY);
    const relY = localPoint.y - pos.y;

    const attributes: Array<{ id: string; name: string; type: string; visibility: string }> =
      data.attributes || [];
    const operations: Array<{ id: string; name: string; returnType: string; visibility: string }> =
      data.operations || [];

    const attrBlockHeight = visibleAttributeRowCount(attributes.length) * UML_NODE_DIMENSIONS.ATTR_ROW_HEIGHT;
    const sep2Y = UML_NODE_DIMENSIONS.HEADER_HEIGHT + UML_NODE_DIMENSIONS.SEP_PADDING + attrBlockHeight + 6;
    const opStartY = sep2Y + UML_NODE_DIMENSIONS.SEP_PADDING;

    const nodeBBox = { x: pos.x, y: pos.y, width: size.width, height: size.height };

    // 1. Zona de Encabezado (Nombre de la Clase)
    if (relY <= UML_NODE_DIMENSIONS.HEADER_HEIGHT) {
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

    // 2. Resolver por elemento SVG específico (tspan / text)
    const isTspan = targetElem?.tagName?.toLowerCase() === 'tspan';

    // 3. Zona de Atributos: filas reales con sus propios listeners nativos
    // (ver UmlAttributeRowsService) — un click que llega hasta acá es espacio en
    // blanco del compartimento (menos atributos que ATTR_MAX_VISIBLE_ROWS), no
    // resuelve a nada.
    if (relY < sep2Y) {
      return null;
    }

    // 4. Zona de Operaciones
    if (operations.length === 0) return null;

    let opIndex = -1;
    if (isTspan && targetElem?.parentElement) {
      const tspans = Array.from(targetElem.parentElement.children);
      opIndex = tspans.indexOf(targetElem);
    }
    if (opIndex < 0 || opIndex >= operations.length) {
      opIndex = Math.max(
        0,
        Math.min(
          operations.length - 1,
          Math.floor((relY - opStartY + 2) / UML_NODE_DIMENSIONS.LINE_HEIGHT)
        )
      );
    }

    const op = operations[opIndex];
    if (!op) return null;

    return {
      classId: node.id,
      type: 'operation',
      elementId: op.id,
      name: op.name,
      typeOrReturn: op.returnType,
      visibility: op.visibility,
      itemRelY: opStartY - 4 + opIndex * UML_NODE_DIMENSIONS.LINE_HEIGHT,
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
