import { Injectable } from '@angular/core';
import { Graph, Node } from '@antv/x6';
import { UML_NODE_DIMENSIONS, UmlNodeSubElementEvent } from '../../domain/models/uml-editor.models';

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

    const attrCount = Math.max(1, attributes.length);
    const attrHeight = attrCount * UML_NODE_DIMENSIONS.LINE_HEIGHT;
    const sep2Y = UML_NODE_DIMENSIONS.HEADER_HEIGHT + UML_NODE_DIMENSIONS.SEP_PADDING + attrHeight + 6;
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

    // 3. Zona de Atributos
    if (relY < sep2Y) {
      if (attributes.length === 0) return null;

      let attrIndex = -1;
      if (isTspan && targetElem?.parentElement) {
        const tspans = Array.from(targetElem.parentElement.children);
        attrIndex = tspans.indexOf(targetElem);
      }
      if (attrIndex < 0 || attrIndex >= attributes.length) {
        attrIndex = Math.max(
          0,
          Math.min(
            attributes.length - 1,
            Math.floor((relY - UML_NODE_DIMENSIONS.ATTR_START_Y + 2) / UML_NODE_DIMENSIONS.LINE_HEIGHT)
          )
        );
      }

      const attr = attributes[attrIndex];
      if (!attr) return null;

      return {
        classId: node.id,
        type: 'attribute',
        elementId: attr.id,
        name: attr.name,
        typeOrReturn: attr.type,
        visibility: attr.visibility,
        itemRelY: UML_NODE_DIMENSIONS.ATTR_START_Y - 4 + attrIndex * UML_NODE_DIMENSIONS.LINE_HEIGHT,
        nodeBBox,
        clientX,
        clientY,
      };
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

  setRowHighlight(graph: Graph | null, nodeId: string, itemRelY: number): void {
    if (!graph) return;
    const node = graph.getCellById(nodeId);
    if (!node || !node.isNode()) return;

    this.clearRowHighlight(graph);

    node.setAttrByPath('rowHighlight', {
      display: 'block',
      refX: 4,
      refY: itemRelY,
      refWidth: -8,
      height: UML_NODE_DIMENSIONS.LINE_HEIGHT,
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
