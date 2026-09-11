import { Injectable, inject } from '@angular/core';
import { Observable, tap, throttleTime } from 'rxjs';
import {
  DiagramLayout,
  EditorMode,
  LienzoDetailDto,
  ModeloUML,
  SubElementSelection,
  UmlAttribute,
  UmlClassDto,
  UmlMultiplicity,
  UmlOperation,
  UmlParameter,
  UmlRelationDto,
  UmlRelationType,
} from '../domain/models/uml-editor.models';
import { UmlApiService } from './uml-api.service';
import { UmlDiagramAdapterService } from '../infrastructure/x6/uml-diagram-adapter.service';
import { UmlGraphService } from '../infrastructure/x6/uml-graph.service';
import { COLLABORATION_GATEWAY } from './collaboration-gateway.service';
import { RemoteCursorsService } from './remote-cursors.service';
import { RemoteCanvasSyncService } from './remote-canvas-sync.service';
import { RemoteNodeDragService } from './remote-node-drag.service';
import { NODE_DRAG_BROADCAST_THROTTLE_MS } from './collaboration-tuning';
import { EditorStateService } from './editor-state.service';
import { EditorHistoryService } from './editor-history.service';
import { EditorSelectionService } from './editor-selection.service';
import { EditorCommandService } from './editor-command.service';
import { EditorMemberCommandService } from './editor-member-command.service';

/** Cadencia de emisión del cursor propio hacia los demás peers (dentro del rango 50-100ms del ADR). */
const CURSOR_BROADCAST_THROTTLE_MS = 80;

@Injectable({
  providedIn: 'root',
})
export class UmlEditorFacade {
  private readonly state = inject(EditorStateService);
  private readonly history = inject(EditorHistoryService);
  private readonly selection = inject(EditorSelectionService);
  private readonly commandService = inject(EditorCommandService);
  private readonly memberService = inject(EditorMemberCommandService);

  private readonly api = inject(UmlApiService);
  private readonly adapter = inject(UmlDiagramAdapterService);
  private readonly graphService = inject(UmlGraphService);
  private readonly collabGateway = inject(COLLABORATION_GATEWAY);
  private readonly remoteCursorsService = inject(RemoteCursorsService);
  private readonly remoteCanvasSyncService = inject(RemoteCanvasSyncService);
  private readonly remoteNodeDragService = inject(RemoteNodeDragService);

  // Re-export reactive signals from specialized services (no API breaking changes)
  readonly canvasId = this.state.canvasId;
  readonly canvasName = this.state.canvasName;
  readonly roomName = this.state.roomName;
  readonly role = this.state.role;
  readonly version = this.state.version;
  readonly mode = this.state.mode;
  readonly defaultRelationType = this.state.defaultRelationType;

  readonly isLoading = this.state.isLoading;
  readonly loadError = this.state.loadError;

  readonly model = this.state.model;
  readonly layout = this.state.layout;

  readonly selectedNodes = this.selection.selectedNodes;
  readonly selectedEdges = this.selection.selectedEdges;
  readonly selectedSubElement = this.selection.selectedSubElement;
  readonly selectedClass = this.selection.selectedClass;

  readonly canUndo = this.history.canUndo;
  readonly canRedo = this.history.canRedo;

  readonly isSaving = this.state.isSaving;
  readonly lastSaved = this.state.lastSaved;
  readonly isShareModalOpen = this.state.isShareModalOpen;
  readonly contextMenu = this.state.contextMenu;
  readonly remoteCursors = this.remoteCursorsService.cursors;

  constructor() {
    this.setupGraphSubscriptions();
  }

  private setupGraphSubscriptions(): void {
    this.graphService.nodeMoved$.subscribe(({ nodeId, x, y }) => {
      this.moveElement(nodeId, x, y);
      this.collabGateway.sendNodeDragEnd(nodeId);
    });

    this.graphService.nodeDragging$
      .pipe(
        tap((e) => console.log('[DIAG] nodeDragging$ PRE-throttle', e)),
        throttleTime(NODE_DRAG_BROADCAST_THROTTLE_MS, undefined, { leading: true, trailing: true })
      )
      .subscribe(({ nodeId, x, y }) => {
        console.log('[DIAG] nodeDragging$ POST-throttle -> sendNodeDragPosition', { nodeId, x, y });
        this.collabGateway.sendNodeDragPosition(nodeId, x, y);
      });

    this.graphService.nodeResized$.subscribe(({ nodeId, width, height, x, y }) => {
      this.resizeElement(nodeId, width, height, x, y);
    });

    this.graphService.edgeConnected$.subscribe(({ edgeId, sourceId, targetId, sourcePort, targetPort }) => {
      this.createRelation(sourceId, targetId, this.defaultRelationType(), edgeId, sourcePort, targetPort);
    });

    this.graphService.edgeReconnected$.subscribe(({ edgeId, sourcePort, targetPort }) => {
      this.updateRelationLayout(edgeId, sourcePort, targetPort);
    });

    this.graphService.edgeVerticesChanged$.subscribe(({ edgeId, vertices }) => {
      this.updateRelationVertices(edgeId, vertices);
    });

    this.graphService.localPointerMove$
      .pipe(throttleTime(CURSOR_BROADCAST_THROTTLE_MS, undefined, { leading: true, trailing: true }))
      .subscribe(({ x, y }) => {
        this.collabGateway.sendCursorPosition(x, y);
      });

    this.graphService.edgeRightClick$.subscribe(({ edgeId, x, y }) => {
      this.contextMenu.set({ visible: true, edgeId, x, y });
    });

    this.graphService.blankClick$.subscribe(({ x, y }) => {
      this.closeContextMenu();
      if (this.mode() === 'CREATE_CLASS') {
        this.createClass(`Clase_${Math.floor(Math.random() * 900 + 100)}`, x, y);
        this.setMode('SELECT');
      }
    });

    this.graphService.selectionChange$.subscribe(({ selectedNodes, selectedEdges }) => {
      this.selectedNodes.set(selectedNodes);
      this.selectedEdges.set(selectedEdges);
      const currentSub = this.selectedSubElement();
      if (currentSub && (!selectedNodes.includes(currentSub.classId) || selectedNodes.length !== 1)) {
        this.clearSubElement();
      }
    });

    this.graphService.nodeSubElementClick$.subscribe((event) => {
      if (event.type === 'class') {
        this.clearSubElement();
      } else if (event.type === 'attribute' || event.type === 'operation') {
        if (event.elementId) {
          this.selectSubElement({
            type: event.type,
            classId: event.classId,
            elementId: event.elementId,
          });
        }
      }
    });

    this.graphService.nodeAdded$.subscribe(({ nodeId, name, x, y }) => {
      const currentModel = this.model();
      if (!currentModel.classes.some((c) => c.id === nodeId)) {
        const newClass: UmlClassDto = {
          id: nodeId,
          name,
          isAbstract: false,
          attributes: [],
          operations: [],
        };

        this.state.updateClasses((classes) => [...classes, newClass]);
        const currentLayout = this.layout();
        this.state.layout.set({
          ...currentLayout,
          nodes: {
            ...currentLayout.nodes,
            [nodeId]: { x, y, width: 190, height: 130 },
          },
        });

        this.dispatchCommand('CREATE_CLASS', {
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

          this.state.setSnapshot(loadedModel, loadedLayout);

          // El canal de colaboración usa el id real del lienzo (no `roomName`,
          // que es un identificador aparte heredado del stack legacy de
          // señalización WebRTC) — coincide con el `canvas_id` del endpoint
          // `/ws/canvas/{canvas_id}/collaboration`.
          this.collabGateway.connect(dto.id);

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
    this.state.setMode(newMode);
  }

  setDefaultRelationType(type: UmlRelationType): void {
    this.state.setDefaultRelationType(type);
  }

  selectSubElement(selection: SubElementSelection): void {
    this.selection.selectSubElement(selection);
  }

  clearSubElement(): void {
    this.selection.clearSubElement();
  }

  openShareModal(): void {
    this.isShareModalOpen.set(true);
  }

  closeShareModal(): void {
    this.isShareModalOpen.set(false);
  }

  closeContextMenu(): void {
    this.contextMenu.set(null);
  }

  updateContextMenuEdgeType(type: UmlRelationType): void {
    const menu = this.contextMenu();
    if (!menu) return;
    this.updateRelation(menu.edgeId, { type });
    this.closeContextMenu();
  }

  deleteContextMenuEdge(): void {
    const menu = this.contextMenu();
    if (!menu) return;
    this.deleteRelation(menu.edgeId);
    this.closeContextMenu();
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

  resetZoom(): void {
    this.graphService.resetZoom();
  }

  undo(): void {
    this.commandService.undo();
  }

  redo(): void {
    this.commandService.redo();
  }

  createClass(name: string, x: number, y: number): void {
    this.commandService.createClass(name, x, y);
  }

  updateClassName(classId: string, newName: string): void {
    this.commandService.updateClassName(classId, newName);
  }

  updateClassAbstract(classId: string, isAbstract: boolean): void {
    this.commandService.updateClassAbstract(classId, isAbstract);
  }

  updateClassDetails(classId: string, updates: Partial<UmlClassDto>): void {
    this.commandService.updateClassDetails(classId, updates);
  }

  moveElement(classId: string, x: number, y: number): void {
    this.commandService.moveElement(classId, x, y);
  }

  resizeElement(classId: string, width: number, height: number, x: number, y: number): void {
    this.commandService.resizeElement(classId, width, height, x, y);
  }

  deleteSelected(): void {
    this.commandService.deleteSelected();
  }

  updateRelationLayout(relationId: string, sourcePort?: string, targetPort?: string): void {
    this.commandService.updateRelationLayout(relationId, sourcePort, targetPort);
  }

  updateRelationVertices(relationId: string, vertices: Array<{ x: number; y: number }>): void {
    this.commandService.updateRelationVertices(relationId, vertices);
  }

  /** Cierra el canal de colaboración y limpia los cursores remotos — llamar al salir del lienzo. */
  disconnectCollaboration(): void {
    this.collabGateway.disconnect();
    this.remoteCursorsService.reset();
    this.remoteNodeDragService.reset();
  }

  deleteElement(elementId: string): void {
    this.selection.selectedNodes.set([elementId]);
    this.commandService.deleteSelected();
  }

  addAttribute(
    classId: string,
    attr?: { name?: string; type?: string; visibility?: any; isStatic?: boolean }
  ): void {
    this.memberService.addAttribute(classId, attr);
  }

  updateAttribute(classId: string, attributeId: string, updates: Partial<UmlAttribute>): void {
    this.memberService.updateAttribute(classId, attributeId, updates);
  }

  deleteAttribute(classId: string, attributeId: string): void {
    this.memberService.deleteAttribute(classId, attributeId);
  }

  addOperation(
    classId: string,
    op?: { name?: string; returnType?: string; visibility?: any; isStatic?: boolean; isAbstract?: boolean }
  ): void {
    this.memberService.addOperation(classId, op);
  }

  updateOperation(classId: string, operationId: string, updates: Partial<UmlOperation>): void {
    this.memberService.updateOperation(classId, operationId, updates);
  }

  deleteOperation(classId: string, operationId: string): void {
    this.memberService.deleteOperation(classId, operationId);
  }

  addParameter(classId: string, operationId: string, param?: Partial<UmlParameter>): void {
    this.memberService.addParameter(classId, operationId, param);
  }

  updateParameter(
    classId: string,
    operationId: string,
    parameterId: string,
    updates: Partial<UmlParameter>
  ): void {
    this.memberService.updateParameter(classId, operationId, parameterId, updates);
  }

  deleteParameter(classId: string, operationId: string, parameterId: string): void {
    this.memberService.deleteParameter(classId, operationId, parameterId);
  }

  createRelation(
    sourceClassId: string,
    targetClassId: string,
    type: UmlRelationType = 'ASSOCIATION',
    existingEdgeId?: string,
    sourcePort?: string,
    targetPort?: string
  ): void {
    this.commandService.createRelation(
      sourceClassId,
      targetClassId,
      type,
      existingEdgeId,
      sourcePort,
      targetPort
    );
  }

  updateRelation(relationId: string, updates: Partial<UmlRelationDto>): void {
    this.commandService.updateRelation(relationId, updates);
  }

  updateMultiplicity(
    relationId: string,
    sourceMultiplicity?: UmlMultiplicity | string,
    targetMultiplicity?: UmlMultiplicity | string
  ): void {
    this.commandService.updateMultiplicity(
      relationId,
      sourceMultiplicity as string,
      targetMultiplicity as string
    );
  }

  deleteRelation(relationId: string): void {
    this.commandService.deleteRelation(relationId);
  }

  dispatchCommand<T>(type: any, payload: T): void {
    this.commandService.dispatchCommand(type, payload);
  }
}
