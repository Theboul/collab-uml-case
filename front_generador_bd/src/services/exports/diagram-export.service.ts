import { Injectable } from '@angular/core';

export interface UmlClassDTO {
  id: string;
  name: string;
  attributes: { name: string; type: string }[];
  methods: { name: string; parameters?: string; returnType?: string }[];
  position: { x: number; y: number };
  size: { width: number; height: number };
}

export interface UmlRelationshipDTO {
  id: string;
  type: string;              // association | aggregation | generalization | etc.
  sourceId: string;
  targetId: string;
  labels?: string[];
  vertices?: { x: number; y: number }[];
}

export interface UmlExportDTO {
  classes: UmlClassDTO[];
  relationships: UmlRelationshipDTO[];
}

@Injectable({ providedIn: 'root' })
export class DiagramExportService {
  /**
   * Exporta el grafo a un JSON limpio y usable para el backend
   */
  export(graph: any): UmlExportDTO {
    const classes: UmlClassDTO[] = [];
    const relationships: UmlRelationshipDTO[] = [];

    graph.getCells().forEach((cell: any) => {
      if (cell.isElement?.()) {
        const rawAttrs = cell.get('attributes');
        const rawMeths = cell.get('methods');

        const attributes = Array.isArray(rawAttrs)
          ? rawAttrs
          : this.parseAttributesFromText(rawAttrs);

        const methods = Array.isArray(rawMeths)
          ? rawMeths
          : this.parseMethodsFromText(rawMeths);

        classes.push({
          id: cell.id,
          name: cell.get('name'),
          attributes,
          methods,
          position: cell.position(),  // 👈 posición
          size: cell.size()           // 👈 tamaño
        });
      } else if (cell.isLink?.()) {
        relationships.push({
          id: cell.id,
          type: cell.get('relationType') || 'association',
          sourceId: cell.get('source')?.id,
          targetId: cell.get('target')?.id,
          labels: (cell.get('labels') || []).map((lbl: any) => lbl.attrs?.text?.text),
          vertices: cell.get('vertices') || []   
        });
      }
    });

    return { classes, relationships };
  }

  // ========= Helpers privados =========

  private parseAttributesFromText(text: string): { name: string; type: string }[] {
    if (!text) return [];
    return text.split('\n').map(line => {
      const [name, type] = line.split(':').map(s => s.trim());
      return { name: name || '', type: type || '' };
    });
  }

  private parseMethodsFromText(text: string): { name: string; parameters?: string; returnType?: string }[] {
    if (!text) return [];
    return text.split('\n').map(line => {
      const match = line.match(/^(\w+)\(([^)]*)\)(?::\s*(\w+))?/);
      if (match) {
        return {
          name: match[1],
          parameters: match[2] || '',
          returnType: match[3] || ''
        };
      }
      return { name: line.trim() };
    });
  }
}
