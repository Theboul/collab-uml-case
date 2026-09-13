import { Injectable } from '@angular/core';
import { Edge, Graph, Node } from '@antv/x6';
import { X6EdgeConfig, X6NodeConfig } from './uml-diagram-adapter.service';
import { buildUmlClassNodeVisual } from './uml-class-node-visual';

/**
 * Callbacks hacia `UmlGraphService` para las mutaciones que ya tienen dueño ahí
 * (clamps de tamaño mínimo, guard de reentrancia de posición remota, etc.) — este
 * servicio no inyecta `UmlGraphService` a propósito, para no crear una dependencia
 * circular (UmlGraphService ya inyecta este servicio para delegar `renderCells`).
 */
export interface GraphReconciliationPorts {
  addNode(config: X6NodeConfig): void;
  addEdge(config: X6EdgeConfig): void;
  setNodePosition(nodeId: string, x: number, y: number): void;
  renderAttributeRows(node: Node, attributes: X6NodeConfig['data']['attributes'], attrBlockHeight: number): void;
}

/**
 * Diff puro por id, sin tocar X6 — separado para poder testearlo sin instanciar un
 * `Graph` real (pesado de montar en jsdom/Karma).
 */
export function computeIdDiff(
  existingIds: string[],
  incomingIds: string[],
): { toAdd: string[]; toRemove: string[]; toKeep: string[] } {
  const existingSet = new Set(existingIds);
  const incomingSet = new Set(incomingIds);
  return {
    toAdd: incomingIds.filter((id) => !existingSet.has(id)),
    toRemove: existingIds.filter((id) => !incomingSet.has(id)),
    toKeep: incomingIds.filter((id) => existingSet.has(id)),
  };
}

/**
 * Reconcilia el grafo X6 contra un modelo nuevo por id, en vez de destruirlo y
 * reconstruirlo (`clearCells()+addNode()×N`). Ese enfoque anterior era la causa raíz
 * de dos bugs: tools de edición (vértices de arista) huérfanos tras un
 * `canvas_update` ajeno, y duplicados visuales al restaurar una pestaña minimizada
 * — `clearCells()` programa la remoción de vistas a través del scheduler interno de
 * X6, y volver a crear celdas con el mismo id en el mismo tick podía adelantarse a
 * esa remoción. Al mutar in-place las celdas que sobreviven, además se preserva
 * gratis la selección actual (antes se perdía en cada snapshot ajeno, porque las
 * celdas eran objetos nuevos aunque compartieran id).
 *
 * Orden: nodos primero, aristas después. `graph.removeCell(node)` ya dispara la
 * remoción en cascada de las aristas conectadas a ese nodo (comportamiento nativo
 * de X6, ver `model.js`), así que no hace falta un paso separado de poda de
 * aristas por classId eliminado — solo se poda lo que sigue vivo tras esa cascada.
 */
@Injectable({
  providedIn: 'root',
})
export class UmlGraphReconciliationService {
  reconcile(
    graph: Graph,
    nodes: X6NodeConfig[],
    edges: X6EdgeConfig[],
    ports: GraphReconciliationPorts,
  ): void {
    this.reconcileNodes(graph, nodes, ports);
    this.reconcileEdges(graph, edges, ports);
  }

  private reconcileNodes(
    graph: Graph,
    nodes: X6NodeConfig[],
    ports: GraphReconciliationPorts,
  ): void {
    const existingById = new Map(graph.getNodes().map((n) => [n.id, n]));
    const diff = computeIdDiff(
      Array.from(existingById.keys()),
      nodes.map((n) => n.id),
    );

    for (const id of diff.toRemove) {
      const node = existingById.get(id);
      if (node) graph.removeCell(node);
    }

    const nodesById = new Map(nodes.map((n) => [n.id, n]));
    for (const id of diff.toAdd) {
      const config = nodesById.get(id);
      if (config) ports.addNode(config);
    }

    for (const id of diff.toKeep) {
      const node = existingById.get(id);
      const config = nodesById.get(id);
      if (node && config) this.reconcileExistingNode(node, config, ports);
    }
  }

  private reconcileExistingNode(
    node: Node,
    config: X6NodeConfig,
    ports: GraphReconciliationPorts,
  ): void {
    const currentData = node.getData() ?? {};
    if (JSON.stringify(currentData) !== JSON.stringify(config.data)) {
      node.setData(config.data);
      const visual = buildUmlClassNodeVisual(config.data);
      node.setAttrByPath('title/text', visual.attrs.title.text);
      node.setAttrByPath('separator2/y1', visual.attrs.separator2.y1);
      node.setAttrByPath('separator2/y2', visual.attrs.separator2.y2);
      node.setAttrByPath('operations/text', visual.attrs.operations.text);
      node.setAttrByPath('operations/refY', visual.attrs.operations.refY);
      ports.renderAttributeRows(node, config.data.attributes, visual.attrBlockHeight);
    }

    const currentSize = node.getSize();
    if (currentSize.width !== config.width || currentSize.height !== config.height) {
      node.resize(config.width, config.height);
    }

    const currentPos = node.getPosition();
    if (currentPos.x !== config.x || currentPos.y !== config.y) {
      ports.setNodePosition(node.id, config.x, config.y);
    }
  }

  private reconcileEdges(
    graph: Graph,
    edges: X6EdgeConfig[],
    ports: GraphReconciliationPorts,
  ): void {
    const existingById = new Map(graph.getEdges().map((e) => [e.id, e]));
    const diff = computeIdDiff(
      Array.from(existingById.keys()),
      edges.map((e) => e.id),
    );

    for (const id of diff.toRemove) {
      const edge = existingById.get(id);
      if (edge) graph.removeCell(edge);
    }

    const edgesById = new Map(edges.map((e) => [e.id, e]));
    for (const id of diff.toAdd) {
      const config = edgesById.get(id);
      if (config) ports.addEdge(config);
    }

    for (const id of diff.toKeep) {
      const edge = existingById.get(id);
      const config = edgesById.get(id);
      if (edge && config) this.reconcileExistingEdge(edge, config);
    }
  }

  private reconcileExistingEdge(edge: Edge, config: X6EdgeConfig): void {
    const currentSource = edge.getSource() as { cell?: string; port?: string };
    if (currentSource?.cell !== config.source.cell || currentSource?.port !== config.source.port) {
      edge.setSource(config.source);
    }

    const currentTarget = edge.getTarget() as { cell?: string; port?: string };
    if (currentTarget?.cell !== config.target.cell || currentTarget?.port !== config.target.port) {
      edge.setTarget(config.target);
    }

    const wantVertices = config.vertices ?? [];
    if (JSON.stringify(edge.getVertices()) !== JSON.stringify(wantVertices)) {
      edge.setVertices(wantVertices);
    }

    const wantLabels = config.labels ?? [];
    if (JSON.stringify(edge.getLabels()) !== JSON.stringify(wantLabels)) {
      edge.setLabels(wantLabels);
    }

    if (JSON.stringify(edge.getAttrs()) !== JSON.stringify(config.attrs)) {
      edge.setAttrs(config.attrs);
    }
  }
}
