import { Injectable, inject } from '@angular/core';
import { EditorStateService } from './editor-state.service';
import { UmlGraphService } from '../infrastructure/x6/uml-graph.service';
import { UmlRelationDto } from '../domain/models/uml-editor.models';

@Injectable({
  providedIn: 'root',
})
export class UmlAssociationClassService {
  private readonly state = inject(EditorStateService);
  private readonly graphService = inject(UmlGraphService);

  /**
   * Determina si una relación es Muchos a Muchos (*..*, 0..* 1..*, 0..* 0..*, 1..* 1..*, 1..* 0..*).
   */
  isManyToMany(sourceMultiplicity?: string, targetMultiplicity?: string): boolean {
    const isMany = (m?: string) => Boolean(m && m.includes('*'));
    return isMany(sourceMultiplicity) && isMany(targetMultiplicity);
  }

  /**
   * Verifica si la relación es N:M. Si lo es, genera automáticamente la clase intermedia
   * NombreA_NombreB y dibuja la conexión perpendicular punteada hacia ella.
   */
  checkAndCreateIntermediateTable(
    relation: UmlRelationDto,
    createClassFn: (name: string, x: number, y: number) => void,
  ): void {
    if (!this.isManyToMany(relation.sourceMultiplicity, relation.targetMultiplicity)) {
      return;
    }

    const currentModel = this.state.model();
    const sourceClass = currentModel.classes.find((c) => c.id === relation.sourceClassId);
    const targetClass = currentModel.classes.find((c) => c.id === relation.targetClassId);
    if (!sourceClass || !targetClass) return;

    const nameA = sourceClass.name;
    const nameB = targetClass.name;
    const isSelf = sourceClass.id === targetClass.id;

    const intermediateName = isSelf ? `${nameA}_${nameA}` : `${nameA}_${nameB}`;
    const altName = isSelf ? `${nameA}_${nameA}` : `${nameB}_${nameA}`;
    const joinedName = `${nameA}${nameB}`;

    let intermediateClass = currentModel.classes.find((c) => {
      const lower = c.name.toLowerCase();
      return (
        lower === intermediateName.toLowerCase() ||
        lower === altName.toLowerCase() ||
        lower === joinedName.toLowerCase()
      );
    });

    if (!intermediateClass) {
      // Calcular posición perpendicular
      const layout = this.state.layout();
      const nodeA = layout.nodes[sourceClass.id] || { x: 100, y: 100, width: 190, height: 130 };
      const nodeB = layout.nodes[targetClass.id] || { x: 340, y: 100, width: 190, height: 130 };

      const midX = Math.round((nodeA.x + nodeB.x) / 2);
      const midY = Math.round((nodeA.y + nodeB.y) / 2);

      const targetX = isSelf ? nodeA.x + 240 : midX;
      const targetY = isSelf ? nodeA.y + 180 : midY + 180;

      // Crear la clase intermedia a través del callback
      createClassFn(intermediateName, targetX, targetY);

      // Obtener la clase recién creada
      intermediateClass = this.state
        .model()
        .classes.find((c) => c.name.toLowerCase() === intermediateName.toLowerCase());
    }

    if (intermediateClass && this.graphService.isInitialized) {
      this.renderConnector(relation.id, intermediateClass.id);
    }
  }

  /**
   * Dibuja el conector perpendicular punteado entre la arista de relación y la tabla intermedia.
   */
  renderConnector(relationId: string, intermediateClassId: string): void {
    if (!this.graphService.isInitialized) return;

    const connectorId = `assoc_connector_${relationId}`;
    try {
      this.graphService.deleteCell(connectorId);
    } catch {
      // Ignorar si no existía previamente
    }

    try {
      this.graphService.addEdge({
        id: connectorId,
        source: { cell: relationId },
        target: { cell: intermediateClassId, port: 'port-top-2' },
        attrs: {
          line: {
            stroke: '#64748b',
            strokeWidth: 1.5,
            strokeDasharray: '4,4',
            targetMarker: null,
            sourceMarker: null,
          },
        },
        data: {
          relationType: 'ASSOCIATION',
          sourceMultiplicity: '',
          targetMultiplicity: '',
        },
      });
    } catch (err) {
      console.warn('No se pudo renderizar conector de clase asociativa:', err);
    }
  }
}
