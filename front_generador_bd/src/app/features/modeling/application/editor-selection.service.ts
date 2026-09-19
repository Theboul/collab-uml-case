import { Injectable, computed, inject, signal } from '@angular/core';
import { SubElementSelection, UmlClassDto } from '../domain/models/uml-editor.models';
import { EditorStateService } from './editor-state.service';
import { UmlGraphService } from '../infrastructure/x6/uml-graph.service';
import { attributeRowRect, operationRowRect } from '../infrastructure/x6/uml-class-node-layout';

@Injectable({
  providedIn: 'root',
})
export class EditorSelectionService {
  private readonly state = inject(EditorStateService);
  private readonly graphService = inject(UmlGraphService);

  readonly selectedNodes = signal<string[]>([]);
  readonly selectedEdges = signal<string[]>([]);
  readonly selectedSubElement = signal<SubElementSelection | null>(null);

  readonly selectedClass = computed<UmlClassDto | null>(() => {
    const ids = this.selectedNodes();
    if (ids.length !== 1) return null;
    return this.state.model().classes.find((c) => c.id === ids[0]) ?? null;
  });

  setSelection(selectedNodes: string[], selectedEdges: string[]): void {
    this.selectedNodes.set(selectedNodes);
    this.selectedEdges.set(selectedEdges);
    const currentSub = this.selectedSubElement();
    if (currentSub && (!selectedNodes.includes(currentSub.classId) || selectedNodes.length !== 1)) {
      this.clearSubElement();
    }
  }

  selectSubElement(sub: SubElementSelection | null): void {
    this.selectedSubElement.set(sub);
    if (!sub) {
      this.graphService.clearRowHighlight();
      return;
    }

    // Asegurar que la clase padre esté seleccionada en el grafo
    const rawGraph = this.graphService.rawGraph;
    if (rawGraph) {
      const node = rawGraph.getCellById(sub.classId);
      if (node && node.isNode()) {
        const isAlreadySelected = (rawGraph as any).isSelected(node);
        if (!isAlreadySelected || (rawGraph as any).getSelectedCellCount() !== 1) {
          rawGraph.cleanSelection();
          rawGraph.select(node);
        }
      }
    }

    // Calcular el itemRelY buscando el índice actual del elementId en el modelo
    const cls = this.state.model().classes.find((c) => c.id === sub.classId);
    if (!cls) return;

    // La fila a resaltar sale del mismo layout con el que está dibujado el nodo (alto
    // variable por envoltura de texto), así el resaltado no se desalinea de la fila.
    const layout = this.graphService.getNodeLayout(sub.classId);
    const rect = !layout
      ? null
      : sub.type === 'attribute'
        ? attributeRowRect(layout, cls.attributes.findIndex((a) => a.id === sub.elementId))
        : operationRowRect(layout, cls.operations.findIndex((o) => o.id === sub.elementId));

    if (rect) {
      this.graphService.setRowHighlight(sub.classId, rect.y, rect.height);
    } else {
      this.graphService.clearRowHighlight(sub.classId);
    }
  }

  clearSubElement(): void {
    this.selectedSubElement.set(null);
    this.graphService.clearRowHighlight();
  }

  clearSelection(): void {
    this.selectedNodes.set([]);
    this.selectedEdges.set([]);
    this.clearSubElement();
  }
}
