import { Injectable } from '@angular/core';
import {
  DiagramLayout,
  ModeloUML,
  UmlClassDto,
  UmlMultiplicity,
  UmlParameter,
  UmlRelationDto,
  UmlRelationType,
  UML_NODE_DIMENSIONS,
} from '../../domain/models/uml-editor.models';

export interface X6NodeConfig {
  id: string;
  shape: string;
  x: number;
  y: number;
  width: number;
  height: number;
  data: {
    name: string;
    isAbstract: boolean;
    attributes: Array<{ id?: string; name: string; type: string; visibility: string }>;
    operations: Array<{ id?: string; name: string; returnType: string; visibility: string; parameters?: UmlParameter[] | string }>;
  };
  attrs?: Record<string, any>;
  ports?: any;
}

export interface X6EdgeConfig {
  id: string;
  source: { cell: string; port?: string };
  target: { cell: string; port?: string };
  router?: string | { name: string; args?: any };
  connector?: string | { name: string; args?: any };
  vertices?: Array<{ x: number; y: number }>;
  attrs: Record<string, any>;
  labels?: any[];
  data: {
    relationType: UmlRelationType;
    sourceMultiplicity: string;
    targetMultiplicity: string;
    sourceRole?: string | null;
    targetRole?: string | null;
    name?: string | null;
  };
}

type PortSide = 'top' | 'right' | 'bottom' | 'left';

const PORTS_PER_SIDE = 4;

/**
 * Separación perpendicular (px, múltiplo del step del router manhattan) entre relaciones que
 * comparten el mismo par de clases, para que no se dibujen pisadas una sobre otra.
 */
const PARALLEL_OFFSET_STEP = 30;

const EMPTY_LAYOUT: DiagramLayout = {
  viewport: { zoom: 1, panX: 0, panY: 0 },
  nodes: {},
  links: {},
};

@Injectable({
  providedIn: 'root',
})
export class UmlDiagramAdapterService {
  /**
   * Traduce el modelo canónico ModeloUML + DiagramLayout a configuraciones de celdas AntV X6.
   */
  modelToCells(
    model: ModeloUML,
    layout: DiagramLayout
  ): { nodes: X6NodeConfig[]; edges: X6EdgeConfig[] } {
    const nodes: X6NodeConfig[] = (model.classes || []).map((c) => {
      const nodeLayout = layout?.nodes?.[c.id] || { x: 100, y: 100, width: 190, height: 130 };
      const titleText = c.name + (c.isAbstract ? ' {abstract}' : '');

      const attrsList = (c.attributes || []).length > 0
        ? c.attributes.map((a) => `${a.visibility} ${a.name} : ${a.type}`).join('\n')
        : '';

      const opsList = (c.operations || []).length > 0
        ? c.operations
            .map((o) => {
              let paramsStr = '';
              if (Array.isArray(o.parameters)) {
                paramsStr = o.parameters.map((p) => `${p.name}: ${p.type}`).join(', ');
              } else if (typeof o.parameters === 'string') {
                paramsStr = o.parameters;
              }
              return `${o.visibility} ${o.name}(${paramsStr}) : ${o.returnType}`;
            })
            .join('\n')
        : '';

      const attrLines = (c.attributes || []).length;
      const opLines = (c.operations || []).length;
      const attrHeight = Math.max(1, attrLines) * UML_NODE_DIMENSIONS.LINE_HEIGHT;
      const sep2Y = UML_NODE_DIMENSIONS.HEADER_HEIGHT + UML_NODE_DIMENSIONS.SEP_PADDING + attrHeight + 6;
      const opY = sep2Y + UML_NODE_DIMENSIONS.SEP_PADDING;
      const opHeight = Math.max(1, opLines) * UML_NODE_DIMENSIONS.LINE_HEIGHT;
      const calculatedMinHeight = Math.max(
        UML_NODE_DIMENSIONS.MIN_HEIGHT,
        opY + opHeight + UML_NODE_DIMENSIONS.BOTTOM_PADDING
      );
      const calculatedMinWidth = Math.max(UML_NODE_DIMENSIONS.MIN_WIDTH, nodeLayout.width || 190);

      return {
        id: c.id,
        shape: 'uml-class-node',
        x: nodeLayout.x,
        y: nodeLayout.y,
        width: Math.max(calculatedMinWidth, nodeLayout.width || 180),
        height: Math.max(calculatedMinHeight, nodeLayout.height || 120),
        data: {
          name: c.name,
          isAbstract: c.isAbstract,
          attributes: c.attributes || [],
          operations: c.operations || [],
        },
        attrs: {
          title: { text: titleText },
          attributes: { text: attrsList },
          separator2: { y1: sep2Y, y2: sep2Y },
          operations: { text: opsList, refY: opY },
        },
        ports: this.getDefaultPorts(),
      };
    });

    const edges: X6EdgeConfig[] = (model.relations || []).map((r) => {
      return this.buildEdgeConfig(r, model.relations, layout);
    });

    return { nodes, edges };
  }

  /**
   * Centro geométrico de un nodo según su layout persistido (valor por defecto si aún no tiene posición).
   */
  private nodeCenter(nodeId: string, layout: DiagramLayout): { x: number; y: number } {
    const n = layout?.nodes?.[nodeId] || { x: 100, y: 100, width: 190, height: 130 };
    return { x: n.x + (n.width ?? 190) / 2, y: n.y + (n.height ?? 130) / 2 };
  }

  private resolveSide(from: { x: number; y: number }, to: { x: number; y: number }): PortSide {
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    if (Math.abs(dx) >= Math.abs(dy)) {
      return dx >= 0 ? 'right' : 'left';
    }
    return dy >= 0 ? 'bottom' : 'top';
  }

  /**
   * Determina por qué lado de `nodeId` sale la relación hacia `otherNodeId` y en qué puerto de
   * ese lado le toca (round-robin estable entre las relaciones que comparten lado y nodo), para
   * que varias relaciones no se apilen en un único punto del borde.
   */
  private resolvePort(
    nodeId: string,
    otherNodeId: string,
    relationId: string,
    allRelations: UmlRelationDto[],
    layout: DiagramLayout
  ): string {
    const center = this.nodeCenter(nodeId, layout);
    const side = this.resolveSide(center, this.nodeCenter(otherNodeId, layout));

    const siblingsOnSide = allRelations
      .filter((r) => r.sourceClassId === nodeId || r.targetClassId === nodeId)
      .filter((r) => {
        const otherId = r.sourceClassId === nodeId ? r.targetClassId : r.sourceClassId;
        return this.resolveSide(center, this.nodeCenter(otherId, layout)) === side;
      })
      .sort((a, b) => a.id.localeCompare(b.id));

    const slot = siblingsOnSide.findIndex((r) => r.id === relationId);
    const index = slot === -1 ? 0 : slot % PORTS_PER_SIDE;
    return `port-${side}-${index}`;
  }

  /**
   * Cuando dos o más relaciones conectan exactamente el mismo par de clases, el router
   * ortogonal (manhattan) de X6 sólo evita nodos, no otras aristas: si no se les inyecta un
   * vértice intermedio con offset, sus trazados terminan coincidiendo. Reparte las relaciones
   * "hermanas" (mismo par, sin importar el orden origen/destino) en abanico alrededor de la
   * línea recta entre los centros de ambas clases. Devuelve `undefined` cuando la relación no
   * comparte par con ninguna otra (caso mayoritario) para no alterar el ruteo por defecto.
   */
  private resolveParallelOffsetVertices(
    rel: UmlRelationDto,
    allRelations: UmlRelationDto[],
    layout: DiagramLayout
  ): Array<{ x: number; y: number }> | undefined {
    const pairKey = (r: UmlRelationDto) => [r.sourceClassId, r.targetClassId].sort().join('::');
    const key = pairKey(rel);

    const siblingsById = new Map<string, UmlRelationDto>([[rel.id, rel]]);
    for (const r of allRelations) {
      if (pairKey(r) === key) siblingsById.set(r.id, r);
    }
    const siblings = Array.from(siblingsById.values()).sort((a, b) => a.id.localeCompare(b.id));
    if (siblings.length <= 1) return undefined;

    const index = siblings.findIndex((r) => r.id === rel.id);
    const offsetIndex = index - (siblings.length - 1) / 2;
    if (offsetIndex === 0) return undefined; // relación central: conserva el camino directo

    const source = this.nodeCenter(rel.sourceClassId, layout);
    const target = this.nodeCenter(rel.targetClassId, layout);
    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const length = Math.hypot(dx, dy) || 1;
    const perpX = -dy / length;
    const perpY = dx / length;

    const amount = Math.round((offsetIndex * PARALLEL_OFFSET_STEP) / 10) * 10;

    return [
      {
        x: Math.round((source.x + target.x) / 2 + perpX * amount),
        y: Math.round((source.y + target.y) / 2 + perpY * amount),
      },
    ];
  }

  /**
   * Construye la configuración gráfica de una arista según su semántica UML.
   */
  buildEdgeConfig(
    rel: UmlRelationDto,
    allRelations: UmlRelationDto[] = [],
    layout: DiagramLayout = EMPTY_LAYOUT
  ): X6EdgeConfig {
    const sourceMarker = this.getSourceMarker(rel.type);
    const targetMarker = this.getTargetMarker(rel.type);
    const isDashed = rel.type === 'DEPENDENCY';

    // Un puerto elegido manualmente (arrastrando el extremo de la relación) persiste en el
    // layout y tiene prioridad sobre el cálculo automático de distribución por lado.
    const linkOverride = layout.links?.[rel.id];
    const sourcePort =
      linkOverride?.sourcePort ??
      this.resolvePort(rel.sourceClassId, rel.targetClassId, rel.id, allRelations, layout);
    const targetPort =
      linkOverride?.targetPort ??
      this.resolvePort(rel.targetClassId, rel.sourceClassId, rel.id, allRelations, layout);

    // Los vértices intermedios que el usuario arrastró a mano (persistidos en el layout) tienen
    // prioridad sobre el offset automático anti-superposición entre relaciones del mismo par.
    const vertices =
      linkOverride?.vertices ?? this.resolveParallelOffsetVertices(rel, allRelations, layout) ?? [];

    const labels: any[] = [];
    if (rel.sourceMultiplicity) {
      labels.push({
        attrs: {
          text: {
            text: rel.sourceMultiplicity,
            fontSize: 11,
            fontWeight: '600',
            fill: '#334155',
            fontFamily: 'JetBrains Mono, monospace',
          },
          rect: {
            fill: '#ffffff',
            rx: 2,
            ry: 2,
          },
        },
        position: {
          distance: 0.15,
          offset: { x: 0, y: -12 },
        },
      });
    }

    if (rel.targetMultiplicity) {
      labels.push({
        attrs: {
          text: {
            text: rel.targetMultiplicity,
            fontSize: 11,
            fontWeight: '600',
            fill: '#334155',
            fontFamily: 'JetBrains Mono, monospace',
          },
          rect: {
            fill: '#ffffff',
            rx: 2,
            ry: 2,
          },
        },
        position: {
          distance: 0.85,
          offset: { x: 0, y: -12 },
        },
      });
    }

    if (rel.name) {
      labels.push({
        attrs: {
          text: {
            text: rel.name,
            fontSize: 11,
            fill: '#0f172a',
            fontWeight: 'bold',
            fontFamily: 'Inter, sans-serif',
          },
          rect: {
            fill: '#ffffff',
            stroke: '#cbd5e1',
            strokeWidth: 1,
            rx: 3,
            ry: 3,
          },
        },
        position: {
          distance: 0.5,
          offset: { x: 0, y: -10 },
        },
      });
    }

    return {
      id: rel.id,
      source: { cell: rel.sourceClassId, port: sourcePort },
      target: { cell: rel.targetClassId, port: targetPort },
      router: { name: 'manhattan' },
      connector: { name: 'rounded' },
      vertices,
      attrs: {
        line: {
          stroke: '#334155',
          strokeWidth: 1.75,
          strokeDasharray: isDashed ? '5,5' : '0',
          sourceMarker,
          targetMarker,
        },
      },
      labels,
      data: {
        relationType: rel.type,
        sourceMultiplicity: rel.sourceMultiplicity,
        targetMultiplicity: rel.targetMultiplicity,
        sourceRole: rel.sourceRole,
        targetRole: rel.targetRole,
        name: rel.name,
      },
    };
  }

  /**
   * 4 puertos por lado (16 en total), distribuidos automáticamente por X6 a lo largo de cada
   * lado, para que varias relaciones conectadas al mismo lado de una clase no se apilen en un
   * único punto del borde.
   */
  getDefaultPorts(): any {
    const sides: PortSide[] = ['top', 'right', 'bottom', 'left'];
    const groups: Record<string, any> = {};
    const items: Array<{ id: string; group: PortSide }> = [];

    for (const side of sides) {
      groups[side] = {
        position: side,
        attrs: {
          circle: {
            r: 5,
            magnet: true,
            stroke: '#6366f1',
            strokeWidth: 2,
            fill: '#ffffff',
            cursor: 'crosshair',
          },
        },
      };
      for (let i = 0; i < PORTS_PER_SIDE; i++) {
        items.push({ id: `port-${side}-${i}`, group: side });
      }
    }

    return { groups, items };
  }

  private getSourceMarker(type: UmlRelationType): any {
    if (type === 'AGGREGATION') {
      return {
        name: 'path',
        d: 'M 0 0 L 10 -5 L 20 0 L 10 5 Z',
        fill: '#ffffff',
        stroke: '#334155',
        strokeWidth: 1.5,
      };
    }
    if (type === 'COMPOSITION') {
      return {
        name: 'path',
        d: 'M 0 0 L 10 -5 L 20 0 L 10 5 Z',
        fill: '#1e293b',
        stroke: '#1e293b',
        strokeWidth: 1.5,
      };
    }
    return null;
  }

  private getTargetMarker(type: UmlRelationType): any {
    if (type === 'GENERALIZATION') {
      return {
        name: 'path',
        // Punta (vértice único) en x=0, apoyada justo en el borde de la clase; la base
        // ancha se extiende hacia x positivo, que es la dirección "hacia afuera" del nodo.
        d: 'M 14 -8 L 0 0 L 14 8 Z',
        fill: '#ffffff',
        stroke: '#334155',
        strokeWidth: 1.5,
      };
    }
    if (type === 'DEPENDENCY') {
      return {
        name: 'path',
        d: 'M 10 -6 L 0 0 L 10 6',
        fill: 'none',
        stroke: '#334155',
        strokeWidth: 1.5,
      };
    }
    return null;
  }
}
