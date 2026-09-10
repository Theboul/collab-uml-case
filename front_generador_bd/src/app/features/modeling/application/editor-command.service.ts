import { Injectable, inject } from '@angular/core';
import {
  CreateClassPayload,
  CreateRelationPayload,
  DeleteElementPayload,
  DeleteRelationPayload,
  EditorCommand,
  MoveElementPayload,
  ResizeElementPayload,
  UpdateMultiplicityPayload,
  UpdateRelationLayoutPayload,
  UpdateRelationPayload,
  UpdateRelationVerticesPayload,
} from '../domain/commands/editor-commands';
import {
  DiagramLayout,
  LienzoDetailDto,
  ModeloUML,
  UmlClassDto,
  UmlRelationDto,
  UmlRelationType,
} from '../domain/models/uml-editor.models';
import { UmlApiService } from './uml-api.service';
import { COLLABORATION_GATEWAY } from './collaboration-gateway.service';
import { EditorStateService } from './editor-state.service';
import { EditorHistoryService } from './editor-history.service';
import { EditorSelectionService } from './editor-selection.service';
import { UmlGraphService } from '../infrastructure/x6/uml-graph.service';
import { UmlDiagramAdapterService } from '../infrastructure/x6/uml-diagram-adapter.service';

@Injectable({
  providedIn: 'root',
})
export class EditorCommandService {
  private readonly api = inject(UmlApiService);
  private readonly collabGateway = inject(COLLABORATION_GATEWAY);
  private readonly state = inject(EditorStateService);
  private readonly history = inject(EditorHistoryService);
  private readonly selection = inject(EditorSelectionService);
  private readonly graphService = inject(UmlGraphService);
  private readonly adapter = inject(UmlDiagramAdapterService);

  executeCommandWithHistory<T>(
    forward: { type: string; payload: T },
    inverse: { type: string; payload: any },
    description: string,
    onSuccessLocal?: () => void
  ): void {
    const canvasId = this.state.canvasId();
    if (!canvasId) return;

    const command: EditorCommand<T> = {
      operationId: crypto.randomUUID(),
      expectedVersion: this.state.version(),
      type: forward.type as any,
      payload: forward.payload,
    };

    if (onSuccessLocal) {
      onSuccessLocal();
    }

    this.state.setSaving(true);
    this.api.sendCommand(canvasId, command).subscribe({
      next: (res) => {
        this.state.setVersion(res.version);
        this.state.setSaving(false);

        let actualInverse = inverse;
        if (res.undoPayload) {
          if (forward.type === 'CREATE_CLASS' && res.undoPayload.classId) {
            actualInverse = {
              type: 'DELETE_ELEMENTS',
              payload: { classIds: [res.undoPayload.classId] },
            };
          } else if (forward.type === 'DELETE_ELEMENTS' && res.undoPayload.classes) {
            actualInverse = {
              type: 'RESTORE_ELEMENTS',
              payload: {
                classes: res.undoPayload.classes,
                relations: res.undoPayload.relations || [],
              },
            };
          }
        }

        this.history.pushAction({
          description,
          forwardCommand: forward,
          inverseCommand: actualInverse,
        });

        this.collabGateway.broadcastCommand(command);
      },
      error: (err) => {
        this.state.setSaving(false);
        console.error(`Error al ejecutar comando ${forward.type}:`, err);
        this.history.clear();
        this.reloadSnapshot(canvasId);
      },
    });
  }

  dispatchCommand<T>(type: any, payload: T): void {
    const canvasId = this.state.canvasId();
    if (!canvasId) return;

    const command: EditorCommand<T> = {
      operationId: crypto.randomUUID(),
      expectedVersion: this.state.version(),
      type,
      payload,
    };

    this.state.setSaving(true);
    this.api.sendCommand(canvasId, command).subscribe({
      next: (res) => {
        this.state.setVersion(res.version);
        this.state.setSaving(false);
        this.collabGateway.broadcastCommand(command);
      },
      error: (err) => {
        this.state.setSaving(false);
        console.error('Error al persistir comando:', err);
        this.history.clear();
        this.reloadSnapshot(canvasId);
      },
    });
  }

  undo(): void {
    const canvasId = this.state.canvasId();
    if (!canvasId) return;
    const action = this.history.peekUndo();
    if (!action) return;

    const command: EditorCommand<any> = {
      operationId: crypto.randomUUID(),
      expectedVersion: this.state.version(),
      type: action.inverseCommand.type as any,
      payload: action.inverseCommand.payload,
    };

    this.state.setSaving(true);
    this.api.sendCommand(canvasId, command).subscribe({
      next: (res) => {
        this.state.setVersion(res.version);
        this.state.setSaving(false);
        this.history.popUndo();
        this.history.pushRedo(action);

        if (res.canvas) {
          this.applyCanvasSnapshot(res.canvas);
        }
        this.collabGateway.broadcastCommand(command);
      },
      error: (err) => {
        this.state.setSaving(false);
        console.error('Error al deshacer comando:', err);
        if (err.status === 409) {
          this.history.clear();
          this.reloadSnapshot(canvasId);
        }
      },
    });
  }

  redo(): void {
    const canvasId = this.state.canvasId();
    if (!canvasId) return;
    const action = this.history.peekRedo();
    if (!action) return;

    const command: EditorCommand<any> = {
      operationId: crypto.randomUUID(),
      expectedVersion: this.state.version(),
      type: action.forwardCommand.type as any,
      payload: action.forwardCommand.payload,
    };

    this.state.setSaving(true);
    this.api.sendCommand(canvasId, command).subscribe({
      next: (res) => {
        this.state.setVersion(res.version);
        this.state.setSaving(false);
        this.history.popRedo();
        this.history.pushUndo(action);

        if (res.canvas) {
          this.applyCanvasSnapshot(res.canvas);
        }
        this.collabGateway.broadcastCommand(command);
      },
      error: (err) => {
        this.state.setSaving(false);
        console.error('Error al rehacer comando:', err);
        if (err.status === 409) {
          this.history.clear();
          this.reloadSnapshot(canvasId);
        }
      },
    });
  }

  applyCanvasSnapshot(dto: LienzoDetailDto): void {
    const loadedModel: ModeloUML = {
      classes: dto.model?.classes || [],
      relations: dto.model?.relations || [],
    };
    const loadedLayout: DiagramLayout = dto.visualLayout || {
      viewport: { zoom: 1, panX: 0, panY: 0 },
      nodes: {},
      links: {},
    };

    this.state.setSnapshot(loadedModel, loadedLayout);
    this.state.setVersion(dto.version);
    if (this.graphService.isInitialized) {
      const cells = this.adapter.modelToCells(loadedModel, loadedLayout);
      this.graphService.renderCells(cells.nodes, cells.edges);
    }
  }

  reloadSnapshot(canvasId: string): void {
    this.api.getCanvas(canvasId).subscribe({
      next: (dto) => this.applyCanvasSnapshot(dto),
      error: (err) => console.error('Error al recargar snapshot:', err),
    });
  }

  createClass(name: string, x: number, y: number): void {
    const classId = crypto.randomUUID();
    const newClass: UmlClassDto = {
      id: classId,
      name,
      isAbstract: false,
      attributes: [],
      operations: [],
    };

    const width = 190;
    const height = 130;

    this.executeCommandWithHistory<CreateClassPayload>(
      {
        type: 'CREATE_CLASS',
        payload: { classId, name, isAbstract: false, x, y, width, height },
      },
      {
        type: 'DELETE_ELEMENTS',
        payload: { classIds: [classId] },
      },
      `Crear clase ${name}`,
      () => {
        this.state.updateClasses((classes) => [...classes, newClass]);
        const currentLayout = this.state.layout();
        this.state.layout.set({
          ...currentLayout,
          nodes: { ...currentLayout.nodes, [classId]: { x, y, width, height } },
        });
        if (this.graphService.isInitialized) {
          const cells = this.adapter.modelToCells(
            { classes: [newClass], relations: [] },
            { viewport: { zoom: 1, panX: 0, panY: 0 }, nodes: { [classId]: { x, y, width, height } }, links: {} }
          );
          if (cells.nodes.length > 0) {
            this.graphService.addNode(cells.nodes[0]);
          }
        }
      }
    );
  }

  updateClassName(classId: string, newName: string): void {
    const currentModel = this.state.model();
    const cls = currentModel.classes.find((c) => c.id === classId);
    if (!cls || cls.name === newName) return;
    const oldName = cls.name;

    this.executeCommandWithHistory(
      { type: 'UPDATE_CLASS_NAME', payload: { classId, name: newName } },
      { type: 'UPDATE_CLASS_NAME', payload: { classId, name: oldName } },
      `Renombrar clase a ${newName}`,
      () => this.mutateClass(classId, (c) => ({ ...c, name: newName }))
    );
  }

  updateClassAbstract(classId: string, isAbstract: boolean): void {
    const currentModel = this.state.model();
    const cls = currentModel.classes.find((c) => c.id === classId);
    if (!cls || cls.isAbstract === isAbstract) return;

    this.executeCommandWithHistory(
      { type: 'UPDATE_CLASS_NAME', payload: { classId, name: cls.name, isAbstract } },
      { type: 'UPDATE_CLASS_NAME', payload: { classId, name: cls.name, isAbstract: cls.isAbstract } },
      `Modificar modificador abstracto de ${cls.name}`,
      () => this.mutateClass(classId, (c) => ({ ...c, isAbstract }))
    );
  }

  updateClassDetails(classId: string, updates: Partial<UmlClassDto>): void {
    if (updates.name !== undefined) {
      this.updateClassName(classId, updates.name);
    }
    if (updates.isAbstract !== undefined) {
      this.updateClassAbstract(classId, updates.isAbstract);
    }
  }

  moveElement(classId: string, x: number, y: number): void {
    const currentLayout = this.state.layout();
    const oldNode = currentLayout.nodes[classId];
    const oldX = oldNode ? oldNode.x : x;
    const oldY = oldNode ? oldNode.y : y;

    this.executeCommandWithHistory<MoveElementPayload>(
      { type: 'MOVE_ELEMENT', payload: { elementId: classId, x, y } },
      { type: 'MOVE_ELEMENT', payload: { elementId: classId, x: oldX, y: oldY } },
      `Mover elemento`,
      () => {
        this.state.layout.set({
          ...currentLayout,
          nodes: {
            ...currentLayout.nodes,
            [classId]: { ...(oldNode || { width: 190, height: 130 }), x, y },
          },
        });
      }
    );
  }

  resizeElement(classId: string, width: number, height: number, x: number, y: number): void {
    const currentLayout = this.state.layout();
    const oldNode = currentLayout.nodes[classId];
    const oldW = oldNode ? oldNode.width : width;
    const oldH = oldNode ? oldNode.height : height;

    this.executeCommandWithHistory<ResizeElementPayload>(
      { type: 'RESIZE_ELEMENT', payload: { elementId: classId, width, height, x, y } },
      { type: 'RESIZE_ELEMENT', payload: { elementId: classId, width: oldW, height: oldH, x, y } },
      `Redimensionar elemento`,
      () => {
        this.state.layout.set({
          ...currentLayout,
          nodes: {
            ...currentLayout.nodes,
            [classId]: { ...(oldNode || { x, y }), width, height, x, y },
          },
        });
      }
    );
  }

  /**
   * Persiste el puerto elegido manualmente (arrastrando el extremo de una relación) para que
   * tenga prioridad sobre el cálculo automático de distribución por lado en los próximos renders.
   */
  updateRelationLayout(relationId: string, sourcePort?: string, targetPort?: string): void {
    const currentLayout = this.state.layout();
    const oldLink = currentLayout.links[relationId] || {};

    this.executeCommandWithHistory<UpdateRelationLayoutPayload>(
      { type: 'UPDATE_RELATION_LAYOUT', payload: { relationId, sourcePort, targetPort } },
      {
        type: 'UPDATE_RELATION_LAYOUT',
        payload: { relationId, sourcePort: oldLink.sourcePort, targetPort: oldLink.targetPort },
      },
      `Reconectar relación`,
      () => {
        this.state.layout.set({
          ...currentLayout,
          links: {
            ...currentLayout.links,
            [relationId]: {
              ...oldLink,
              ...(sourcePort ? { sourcePort } : {}),
              ...(targetPort ? { targetPort } : {}),
            },
          },
        });
      }
    );
  }

  /**
   * Persiste los vértices intermedios que el usuario arrastró/agregó/quitó a mano sobre el
   * trazado de una relación (no afecta origen/destino, sólo el camino visual entre ambos).
   */
  updateRelationVertices(relationId: string, vertices: Array<{ x: number; y: number }>): void {
    const currentLayout = this.state.layout();
    const oldLink = currentLayout.links[relationId] || {};
    const oldVertices = oldLink.vertices || [];

    this.executeCommandWithHistory<UpdateRelationVerticesPayload>(
      { type: 'UPDATE_RELATION_VERTICES', payload: { relationId, vertices } },
      { type: 'UPDATE_RELATION_VERTICES', payload: { relationId, vertices: oldVertices } },
      `Ajustar trazado de relación`,
      () => {
        this.state.layout.set({
          ...currentLayout,
          links: {
            ...currentLayout.links,
            [relationId]: { ...oldLink, vertices },
          },
        });
      }
    );
  }

  deleteSelected(): void {
    const selectedNodes = this.selection.selectedNodes();
    const selectedEdges = this.selection.selectedEdges();

    if (selectedNodes.length === 0 && selectedEdges.length === 0) return;

    if (selectedEdges.length > 0 && selectedNodes.length === 0) {
      selectedEdges.forEach((edgeId) => this.deleteRelation(edgeId));
      this.selection.clearSelection();
      return;
    }

    const currentModel = this.state.model();
    const classesToDelete = currentModel.classes.filter((c) => selectedNodes.includes(c.id));
    const relationsToDelete = currentModel.relations.filter(
      (r) => selectedNodes.includes(r.sourceClassId) || selectedNodes.includes(r.targetClassId)
    );

    this.executeCommandWithHistory(
      { type: 'DELETE_ELEMENTS', payload: { classIds: selectedNodes } },
      {
        type: 'RESTORE_ELEMENTS',
        payload: { classes: classesToDelete, relations: relationsToDelete },
      },
      `Eliminar ${selectedNodes.length} elemento(s)`,
      () => {
        this.state.updateClasses((classes) => classes.filter((c) => !selectedNodes.includes(c.id)));
        this.state.updateRelations((relations) =>
          relations.filter(
            (r) => !selectedNodes.includes(r.sourceClassId) && !selectedNodes.includes(r.targetClassId)
          )
        );
        selectedNodes.forEach((nodeId) => this.graphService.deleteCell(nodeId));
        selectedEdges.forEach((edgeId) => this.graphService.deleteCell(edgeId));
        this.selection.clearSelection();
      }
    );
  }

  createRelation(
    sourceId: string,
    targetId: string,
    type: UmlRelationType = 'ASSOCIATION',
    edgeId?: string,
    sourcePort?: string,
    targetPort?: string
  ): void {
    if (edgeId && this.graphService.isInitialized) {
      this.graphService.deleteCell(edgeId);
    }

    const relationId = crypto.randomUUID();
    const newRelation: UmlRelationDto = {
      id: relationId,
      type,
      sourceClassId: sourceId,
      targetClassId: targetId,
      sourceMultiplicity: '1',
      targetMultiplicity: '1',
    };

    this.executeCommandWithHistory<CreateRelationPayload>(
      {
        type: 'CREATE_RELATION',
        payload: {
          relationId,
          type,
          sourceClassId: sourceId,
          targetClassId: targetId,
          sourceMultiplicity: '1',
          targetMultiplicity: '1',
        },
      },
      { type: 'DELETE_RELATION', payload: { relationId } },
      `Crear relación ${type}`,
      () => {
        this.state.updateRelations((relations) => [...relations, newRelation]);

        // Preserva el puerto exacto que el usuario eligió al dibujar la conexión (en vez de
        // dejar que buildEdgeConfig recalcule uno por distribución automática): sin esto, el
        // edge visual que X6 ya dibujó se descarta y se recrea sin recordar dónde se soltó.
        if (sourcePort || targetPort) {
          const currentLayout = this.state.layout();
          this.state.layout.set({
            ...currentLayout,
            links: {
              ...currentLayout.links,
              [relationId]: {
                ...(currentLayout.links[relationId] || {}),
                ...(sourcePort ? { sourcePort } : {}),
                ...(targetPort ? { targetPort } : {}),
              },
            },
          });
        }

        if (this.graphService.isInitialized) {
          const edgeConfig = this.adapter.buildEdgeConfig(
            newRelation,
            this.state.model().relations,
            this.state.layout()
          );
          this.graphService.addEdge(edgeConfig);
        }
      }
    );
  }

  updateRelation(relationId: string, updates: Partial<UpdateRelationPayload>): void {
    const currentModel = this.state.model();
    const oldRel = currentModel.relations.find((r) => r.id === relationId);
    if (!oldRel) return;

    this.executeCommandWithHistory<UpdateRelationPayload>(
      { type: 'UPDATE_RELATION', payload: { relationId, ...updates } },
      {
        type: 'UPDATE_RELATION',
        payload: {
          relationId,
          name: oldRel.name,
          type: oldRel.type,
          sourceRole: oldRel.sourceRole,
          targetRole: oldRel.targetRole,
        },
      },
      `Actualizar relación`,
      () => {
        this.state.updateRelations((relations) =>
          relations.map((r) => (r.id === relationId ? { ...r, ...updates } : r))
        );
        const updatedRel = this.state.model().relations.find((r) => r.id === relationId);
        if (updatedRel && this.graphService.isInitialized) {
          this.graphService.deleteCell(relationId);
          const edgeConfig = this.adapter.buildEdgeConfig(
            updatedRel,
            this.state.model().relations,
            this.state.layout()
          );
          this.graphService.addEdge(edgeConfig);
        }
      }
    );
  }

  updateMultiplicity(
    relationId: string,
    sourceMultiplicity?: string,
    targetMultiplicity?: string
  ): void {
    this.updateRelation(relationId, {
      sourceMultiplicity,
      targetMultiplicity,
    });
  }

  deleteRelation(relationId: string): void {
    const currentModel = this.state.model();
    const oldRel = currentModel.relations.find((r) => r.id === relationId);
    if (!oldRel) return;

    this.executeCommandWithHistory<DeleteRelationPayload>(
      { type: 'DELETE_RELATION', payload: { relationId } },
      {
        type: 'CREATE_RELATION',
        payload: {
          relationId: oldRel.id,
          type: oldRel.type,
          sourceClassId: oldRel.sourceClassId,
          targetClassId: oldRel.targetClassId,
          sourceRole: oldRel.sourceRole,
          targetRole: oldRel.targetRole,
          sourceMultiplicity: oldRel.sourceMultiplicity,
          targetMultiplicity: oldRel.targetMultiplicity,
        },
      },
      `Eliminar relación`,
      () => {
        this.state.updateRelations((relations) => relations.filter((r) => r.id !== relationId));
        this.graphService.deleteCell(relationId);
      }
    );
  }

  private mutateClass(
    classId: string,
    mutator: (cls: UmlClassDto) => UmlClassDto,
    preserveSubSelection = false
  ): void {
    this.state.updateClasses((classes) =>
      classes.map((c) => (c.id === classId ? mutator(c) : c))
    );
    const updated = this.state.model().classes.find((c) => c.id === classId);
    if (updated) {
      this.graphService.updateNodeData(classId, updated);
      if (preserveSubSelection) {
        const currentSub = this.selection.selectedSubElement();
        if (currentSub && currentSub.classId === classId) {
          this.selection.selectSubElement(currentSub);
        }
      }
    }
  }
}
