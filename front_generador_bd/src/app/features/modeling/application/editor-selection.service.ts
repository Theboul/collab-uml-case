import { Injectable, computed, inject, signal } from '@angular/core';
import {
  SubElementSelection,
  UML_NODE_DIMENSIONS,
  UmlClassDto,
} from '../domain/models/uml-editor.models';
import { EditorStateService } from './editor-state.service';
import { UmlGraphService } from '../infrastructure/x6/uml-graph.service';
import { visibleAttributeRowCount } from '../infrastructure/x6/uml-class-node-visual';

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

    if (sub.type === 'attribute') {
      const idx = cls.attributes.findIndex((a) => a.id === sub.elementId);
      const scrollRow = this.graphService.getAttributeScrollRow(sub.classId);
      const visibleRows = visibleAttributeRowCount(cls.attributes.length);
      if (idx !== -1 && idx >= scrollRow && idx < scrollRow + visibleRows) {
        const itemRelY =
          UML_NODE_DIMENSIONS.HEADER_HEIGHT +
          UML_NODE_DIMENSIONS.SEP_PADDING +
          (idx - scrollRow) * UML_NODE_DIMENSIONS.ATTR_ROW_HEIGHT;
        this.graphService.setRowHighlight(sub.classId, itemRelY, UML_NODE_DIMENSIONS.ATTR_ROW_HEIGHT);
      } else {
        // Sin índice válido, o la fila está scrolleada fuera de la ventana visible
        // del compartimento — no hay nada que resaltar en pantalla.
        this.graphService.clearRowHighlight(sub.classId);
      }
    } else if (sub.type === 'operation') {
      const idx = cls.operations.findIndex((o) => o.id === sub.elementId);
      if (idx !== -1) {
        const attrBlockHeight = visibleAttributeRowCount(cls.attributes.length) * UML_NODE_DIMENSIONS.ATTR_ROW_HEIGHT;
        const sep2Y = UML_NODE_DIMENSIONS.HEADER_HEIGHT + UML_NODE_DIMENSIONS.SEP_PADDING + attrBlockHeight + 6;
        const opStartY = sep2Y + UML_NODE_DIMENSIONS.SEP_PADDING;
        const itemRelY = opStartY - 4 + idx * UML_NODE_DIMENSIONS.LINE_HEIGHT;
        this.graphService.setRowHighlight(sub.classId, itemRelY);
      } else {
        this.graphService.clearRowHighlight(sub.classId);
      }
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
