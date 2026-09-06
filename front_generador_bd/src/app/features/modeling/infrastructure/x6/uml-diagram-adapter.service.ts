import { Injectable } from '@angular/core';
import {
  DiagramLayout,
  ModeloUML,
  UmlClassDto,
  UmlMultiplicity,
  UmlRelationDto,
  UmlRelationType,
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
    operations: Array<{ id?: string; name: string; returnType: string; visibility: string; parameters?: string }>;
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
        : '- id : UUID';
      const opsList = (c.operations || []).length > 0
        ? c.operations.map((o) => `${o.visibility} ${o.name}() : ${o.returnType}`).join('\n')
        : '+ ejecutar() : void';

      return {
        id: c.id,
        shape: 'uml-class-node',
        x: nodeLayout.x,
        y: nodeLayout.y,
        width: Math.max(160, nodeLayout.width),
        height: Math.max(90, nodeLayout.height),
        data: {
          name: c.name,
          isAbstract: c.isAbstract,
          attributes: c.attributes || [],
          operations: c.operations || [],
        },
        attrs: {
          title: { text: titleText },
          attributes: { text: attrsList },
          operations: { text: opsList },
        },
        ports: this.getDefaultPorts(),
      };
    });

    const edges: X6EdgeConfig[] = (model.relations || []).map((r) => {
      return this.buildEdgeConfig(r);
    });

    return { nodes, edges };
  }

  /**
   * Construye la configuración gráfica de una arista según su semántica UML.
   */
  buildEdgeConfig(rel: UmlRelationDto): X6EdgeConfig {
    const sourceMarker = this.getSourceMarker(rel.type);
    const targetMarker = this.getTargetMarker(rel.type);
    const isDashed = rel.type === 'DEPENDENCY';

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
      source: { cell: rel.sourceClassId },
      target: { cell: rel.targetClassId },
      router: { name: 'manhattan' },
      connector: { name: 'rounded' },
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

  getDefaultPorts(): any {
    return {
      groups: {
        top: {
          position: 'top',
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
        },
        right: {
          position: 'right',
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
        },
        bottom: {
          position: 'bottom',
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
        },
        left: {
          position: 'left',
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
        },
      },
      items: [
        { id: 'port-top', group: 'top' },
        { id: 'port-right', group: 'right' },
        { id: 'port-bottom', group: 'bottom' },
        { id: 'port-left', group: 'left' },
      ],
    };
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
        d: 'M 0 -8 L 14 0 L 0 8 Z',
        fill: '#ffffff',
        stroke: '#334155',
        strokeWidth: 1.5,
      };
    }
    if (type === 'DEPENDENCY') {
      return {
        name: 'path',
        d: 'M 0 -6 L 10 0 L 0 6',
        fill: 'none',
        stroke: '#334155',
        strokeWidth: 1.5,
      };
    }
    return null;
  }
}
