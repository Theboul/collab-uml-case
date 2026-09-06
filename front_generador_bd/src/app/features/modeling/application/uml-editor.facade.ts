import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import {
  DiagramLayout,
  EditorMode,
  LienzoDetailDto,
  ModeloUML,
  UmlClassDto,
  UmlMultiplicity,
  UmlRelationDto,
  UmlRelationType,
} from '../domain/models/uml-editor.models';
import {
  CreateClassPayload,
  CreateRelationPayload,
  DeleteElementPayload,
  DeleteRelationPayload,
  EditorCommand,
  MoveElementPayload,
  ResizeElementPayload,
  UpdateMultiplicityPayload,
  UpdateRelationPayload,
} from '../domain/commands/editor-commands';
import { UmlApiService } from './uml-api.service';
import { UmlDiagramAdapterService } from '../infrastructure/x6/uml-diagram-adapter.service';
import { UmlGraphService } from '../infrastructure/x6/uml-graph.service';
import { COLLABORATION_GATEWAY } from './collaboration-gateway.service';

@Injectable({
  providedIn: 'root',
})
export class UmlEditorFacade {
  private readonly api = inject(UmlApiService);
  private readonly adapter = inject(UmlDiagramAdapterService);
  private readonly graphService = inject(UmlGraphService);
  private readonly collabGateway = inject(COLLABORATION_GATEWAY);

  readonly canvasId = signal<string | null>(null);
  readonly canvasName = signal<string>('Diagrama Sin Título');
  readonly roomName = signal<string | null>(null);
  readonly role = signal<'ANFITRION' | 'COLABORADOR' | 'INVITADO'>('COLABORADOR');
  readonly version = signal<number>(1);
  readonly mode = signal<EditorMode>('SELECT');
  readonly defaultRelationType = signal<UmlRelationType>('ASSOCIATION');

  readonly isLoading = signal<boolean>(true);
  readonly loadError = signal<string | null>(null);

  readonly model = signal<ModeloUML>({ classes: [], relations: [] });
  readonly layout = signal<DiagramLayout>({
    viewport: { zoom: 1, panX: 0, panY: 0 },
    nodes: {},
    links: {},
  });


  readonly selectedNodes = signal<string[]>([]);
  readonly selectedEdges = signal<string[]>([]);
  readonly canUndo = signal<boolean>(false);
  readonly canRedo = signal<boolean>(false);
  readonly isSaving = signal<boolean>(false);
  readonly lastSaved = signal<Date | null>(null);
  readonly isShareModalOpen = signal<boolean>(false);

  readonly contextMenu = signal<{
    visible: boolean;
    edgeId: string;
    x: number;
    y: number;
  } | null>(null);

  readonly selectedClass = computed<UmlClassDto | null>(() => {
    const ids = this.selectedNodes();
    if (ids.length !== 1) return null;
    return this.model().classes.find((c) => c.id === ids[0]) ?? null;
  });

  constructor() {
    this.setupGraphSubscriptions();
  }

  private setupGraphSubscriptions(): void {
    // 1. Mover nodo -> persiste en pointerUp (no cada mousemove)
    this.graphService.nodeMoved$.subscribe(({ nodeId, x, y }) => {
      this.moveElement(nodeId, x, y);
    });

    // 2. Redimensionar nodo
    this.graphService.nodeResized$.subscribe(({ nodeId, width, height, x, y }) => {
      this.resizeElement(nodeId, width, height, x, y);
    });

    // 3. Conectar arista entre dos clases
    this.graphService.edgeConnected$.subscribe(({ edgeId, sourceId, targetId }) => {
      this.createRelation(sourceId, targetId, this.defaultRelationType(), edgeId);
    });

    // 4. Clic derecho en arista -> Menú contextual
    this.graphService.edgeRightClick$.subscribe(({ edgeId, x, y }) => {
      this.contextMenu.set({ visible: true, edgeId, x, y });
    });

    // 5. Clic en canvas vacío -> si está en CREATE_CLASS crea clase; cierra menú
    this.graphService.blankClick$.subscribe(({ x, y }) => {
      this.closeContextMenu();
      if (this.mode() === 'CREATE_CLASS') {
        this.createClass(`Clase_${Math.floor(Math.random() * 900 + 100)}`, x, y);
        this.setMode('SELECT');
      }
    });

    // 6. Selección cambiada
    this.graphService.selectionChange$.subscribe(({ selectedNodes, selectedEdges }) => {
      this.selectedNodes.set(selectedNodes);
      this.selectedEdges.set(selectedEdges);
    });

    // 7. Historial undo/redo
    this.graphService.historyChange$.subscribe(({ canUndo, canRedo }) => {
      this.canUndo.set(canUndo);
      this.canRedo.set(canRedo);
    });

    // 8. Nodo agregado por Drag & Drop
    this.graphService.nodeAdded$.subscribe(({ nodeId, name, x, y }) => {
      const currentModel = this.model();
      if (!currentModel.classes.some((c) => c.id === nodeId)) {
        const newClass: UmlClassDto = {
          id: nodeId,
          name,
          isAbstract: false,
          attributes: [{ id: crypto.randomUUID(), name: 'id', type: 'UUID', visibility: '-' }],
          operations: [{ id: crypto.randomUUID(), name: 'ejecutar', returnType: 'void', visibility: '+' }],
        };

        this.model.set({
          ...currentModel,
          classes: [...currentModel.classes, newClass],
        });

        const currentLayout = this.layout();
        this.layout.set({
          ...currentLayout,
          nodes: {
            ...currentLayout.nodes,
            [nodeId]: { x, y, width: 190, height: 130 },
          },
        });

        this.dispatchCommand<CreateClassPayload>('CREATE_CLASS', {
          classId: nodeId,
          name,
          isAbstract: false,
          x,
          y,
          width: 190,
          height: 130,
        });
      }
    });
  }

  /**
   * Carga el lienzo inicial desde la API (por room_name o id).
   */
  loadCanvas(roomIdOrId: string): Observable<LienzoDetailDto> {
    this.isLoading.set(true);
    this.loadError.set(null);

    const req$ = roomIdOrId.startsWith('room-')
      ? this.api.getCanvasByRoom(roomIdOrId)
      : this.api.getCanvas(roomIdOrId);

    return req$.pipe(
      tap({
        next: (dto) => {
          this.canvasId.set(dto.id);
          this.canvasName.set(dto.name);
          this.roomName.set(dto.roomName ?? null);
          this.role.set(dto.role || 'COLABORADOR');
          this.version.set(dto.version);

          const loadedModel: ModeloUML = {
            classes: dto.model?.classes || [],
            relations: dto.model?.relations || [],
          };
          const loadedLayout: DiagramLayout = dto.visualLayout || {
            viewport: { zoom: 1, panX: 0, panY: 0 },
            nodes: {},
            links: {},
          };

          this.model.set(loadedModel);
          this.layout.set(loadedLayout);

          if (dto.roomName) {
            this.collabGateway.connect(dto.roomName);
          }

          if (this.graphService.isInitialized) {
            const cells = this.adapter.modelToCells(loadedModel, loadedLayout);
            this.graphService.renderCells(cells.nodes, cells.edges);
          }
          this.isLoading.set(false);
        },
        error: (err) => {
          this.isLoading.set(false);
          const msg = err?.error?.message || 'Error al recuperar el snapshot del lienzo.';
          this.loadError.set(msg);
        },
      })
    );
  }


  renderLoadedModel(): void {
    if (this.graphService.isInitialized) {
      const cells = this.adapter.modelToCells(this.model(), this.layout());
      this.graphService.renderCells(cells.nodes, cells.edges);
    }
  }

  setMode(newMode: EditorMode): void {
    this.mode.set(newMode);
  }

  setDefaultRelationType(type: UmlRelationType): void {
    this.defaultRelationType.set(type);
  }

  closeContextMenu(): void {
    this.contextMenu.set(null);
  }

  openShareModal(): void {
    this.isShareModalOpen.set(true);
  }

  closeShareModal(): void {
    this.isShareModalOpen.set(false);
  }

  /**
   * CU1 / CU3: Crear una nueva clase en el lienzo y enviar comando al backend.
   */
  createClass(name: string, x: number, y: number, isAbstract = false): void {
    const classId = crypto.randomUUID();
    const newClass: UmlClassDto = {
      id: classId,
      name,
      isAbstract,
      attributes: [{ id: crypto.randomUUID(), name: 'id', type: 'UUID', visibility: '-' }],
      operations: [{ id: crypto.randomUUID(), name: 'ejecutar', returnType: 'void', visibility: '+' }],
    };

    const currentModel = this.model();
    this.model.set({
      ...currentModel,
      classes: [...currentModel.classes, newClass],
    });

    const currentLayout = this.layout();
    const updatedNodes = {
      ...currentLayout.nodes,
      [classId]: { x, y, width: 190, height: 130 },
    };
    this.layout.set({
      ...currentLayout,
      nodes: updatedNodes,
    });

    if (this.graphService.isInitialized) {
      const cells = this.adapter.modelToCells(
        { classes: [newClass], relations: [] },
        { viewport: { zoom: 1, panX: 0, panY: 0 }, nodes: { [classId]: { x, y, width: 190, height: 130 } }, links: {} }
      );
      if (cells.nodes.length > 0) {
        this.graphService.addNode(cells.nodes[0]);
      }
    }

    this.dispatchCommand<CreateClassPayload>('CREATE_CLASS', {
      classId,
      name,
      isAbstract,
      x,
      y,
      width: 190,
      height: 130,
    });
  }

  moveElement(elementId: string, x: number, y: number): void {
    const currentLayout = this.layout();
    const nodeLayout = currentLayout.nodes[elementId] || { width: 190, height: 130 };
    this.layout.set({
      ...currentLayout,
      nodes: {
        ...currentLayout.nodes,
        [elementId]: { ...nodeLayout, x, y },
      },
    });

    this.dispatchCommand<MoveElementPayload>('MOVE_ELEMENT', {
      elementId,
      x,
      y,
    });
  }

  resizeElement(elementId: string, width: number, height: number, x: number, y: number): void {
    const currentLayout = this.layout();
    this.layout.set({
      ...currentLayout,
      nodes: {
        ...currentLayout.nodes,
        [elementId]: { x, y, width, height },
      },
    });

    this.dispatchCommand<ResizeElementPayload>('RESIZE_ELEMENT', {
      elementId,
      width,
      height,
      x,
      y,
    });
  }

  createRelation(
    sourceClassId: string,
    targetClassId: string,
    type: UmlRelationType = 'ASSOCIATION',
    existingEdgeId?: string
  ): void {
    const relationId = existingEdgeId ?? crypto.randomUUID();
    const newRelation: UmlRelationDto = {
      id: relationId,
      type,
      sourceClassId,
      targetClassId,
      sourceMultiplicity: '1',
      targetMultiplicity: '1',
    };

    const currentModel = this.model();
    this.model.set({
      ...currentModel,
      relations: [...currentModel.relations, newRelation],
    });

    if (this.graphService.isInitialized) {
      if (existingEdgeId) {
        this.graphService.deleteCell(existingEdgeId);
      }
      const edgeConfig = this.adapter.buildEdgeConfig(newRelation);
      this.graphService.addEdge(edgeConfig);
    }

    this.dispatchCommand<CreateRelationPayload>('CREATE_RELATION', {
      relationId,
      type,
      sourceClassId,
      targetClassId,
      sourceMultiplicity: '1',
      targetMultiplicity: '1',
    });
  }

  updateRelation(relationId: string, updates: Partial<UpdateRelationPayload>): void {
    const currentModel = this.model();
    const updatedRelations = currentModel.relations.map((r) => {
      if (r.id === relationId) {
        return {
          ...r,
          type: updates.type ?? r.type,
          sourceMultiplicity: (updates.sourceMultiplicity as string) ?? r.sourceMultiplicity,
          targetMultiplicity: (updates.targetMultiplicity as string) ?? r.targetMultiplicity,
          sourceRole: updates.sourceRole !== undefined ? updates.sourceRole : r.sourceRole,
          targetRole: updates.targetRole !== undefined ? updates.targetRole : r.targetRole,
          name: updates.name !== undefined ? updates.name : r.name,
        };
      }
      return r;
    });

    this.model.set({ ...currentModel, relations: updatedRelations });

    const updatedRel = updatedRelations.find((r) => r.id === relationId);
    if (updatedRel && this.graphService.isInitialized) {
      this.graphService.deleteCell(relationId);
      const edgeConfig = this.adapter.buildEdgeConfig(updatedRel);
      this.graphService.addEdge(edgeConfig);
    }

    this.dispatchCommand<UpdateRelationPayload>('UPDATE_RELATION', {
      relationId,
      ...updates,
    });
  }

  updateMultiplicity(
    relationId: string,
    sourceMultiplicity?: UmlMultiplicity | string,
    targetMultiplicity?: UmlMultiplicity | string
  ): void {
    this.updateRelation(relationId, {
      sourceMultiplicity,
      targetMultiplicity,
    });
  }

  deleteSelected(): void {
    const nodesToDelete = [...this.selectedNodes()];
    const edgesToDelete = [...this.selectedEdges()];

    for (const nodeId of nodesToDelete) {
      this.deleteElement(nodeId);
    }

    for (const edgeId of edgesToDelete) {
      this.deleteRelation(edgeId);
    }

    this.graphService.deleteSelected();
    this.selectedNodes.set([]);
    this.selectedEdges.set([]);
  }

  deleteElement(elementId: string): void {
    const currentModel = this.model();
    this.model.set({
      classes: currentModel.classes.filter((c) => c.id !== elementId),
      relations: currentModel.relations.filter(
        (r) => r.sourceClassId !== elementId && r.targetClassId !== elementId
      ),
    });

    const currentLayout = this.layout();
    const { [elementId]: _, ...remainingNodes } = currentLayout.nodes;
    this.layout.set({ ...currentLayout, nodes: remainingNodes });

    this.graphService.deleteCell(elementId);

    this.dispatchCommand<DeleteElementPayload>('DELETE_ELEMENT', {
      elementId,
    });
  }

  deleteRelation(relationId: string): void {
    const currentModel = this.model();
    this.model.set({
      ...currentModel,
      relations: currentModel.relations.filter((r) => r.id !== relationId),
    });

    this.graphService.deleteCell(relationId);

    this.dispatchCommand<DeleteRelationPayload>('DELETE_RELATION', {
      relationId,
    });
  }

  updateClassDetails(classId: string, updates: Partial<UmlClassDto>): void {
    const currentModel = this.model();
    const updatedClasses = currentModel.classes.map((c) => {
      if (c.id === classId) {
        return { ...c, ...updates };
      }
      return c;
    });

    this.model.set({ ...currentModel, classes: updatedClasses });

    const updated = updatedClasses.find((c) => c.id === classId);
    if (updated) {
      this.graphService.updateNodeData(classId, updated);
      this.dispatchCommand('CREATE_CLASS', {
        classId,
        name: updated.name,
        isAbstract: updated.isAbstract,
        x: this.layout().nodes[classId]?.x ?? 100,
        y: this.layout().nodes[classId]?.y ?? 100,
      });
    }
  }

  undo(): void {
    this.graphService.undo();
  }

  redo(): void {
    this.graphService.redo();
  }

  zoomIn(): void {
    this.graphService.zoomIn();
  }

  zoomOut(): void {
    this.graphService.zoomOut();
  }

  zoomToFit(): void {
    this.graphService.zoomToFit();
  }

  private dispatchCommand<T>(type: any, payload: T): void {
    const canvasId = this.canvasId();
    if (!canvasId) return;

    const command: EditorCommand<T> = {
      operationId: crypto.randomUUID(),
      expectedVersion: this.version(),
      type,
      payload,
    };

    this.isSaving.set(true);
    this.api.sendCommand(canvasId, command).subscribe({
      next: (res) => {
        this.version.set(res.version);
        this.isSaving.set(false);
        this.lastSaved.set(new Date());
        this.collabGateway.broadcastCommand(command);
      },
      error: (err) => {
        this.isSaving.set(false);
        console.error('Error al persistir comando:', err);
        if (err.status === 409) {
          this.loadCanvas(canvasId).subscribe();
        }
      },
    });
  }
}
