import { Injectable, inject } from '@angular/core';
import { toObservable } from '@angular/core/rxjs-interop';
import { Observable, merge, pairwise, startWith, tap, throttleTime } from 'rxjs';
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
  ValidationResponseDto,
} from '../domain/models/uml-editor.models';
import { UmlApiService } from './uml-api.service';
import { UmlDiagramAdapterService } from '../infrastructure/x6/uml-diagram-adapter.service';
import { UmlGraphService } from '../infrastructure/x6/uml-graph.service';
import { UmlAttributeRowsService } from '../infrastructure/x6/uml-attribute-rows.service';
import { COLLABORATION_GATEWAY } from './collaboration-gateway.service';
import { RemoteCursorsService } from './remote-cursors.service';
import { RemoteCanvasSyncService } from './remote-canvas-sync.service';
import { RemoteNodeDragService } from './remote-node-drag.service';
import { RemoteLocksService } from './remote-locks.service';
import { RemotePresenceService } from './remote-presence.service';
import { NODE_DRAG_BROADCAST_THROTTLE_MS } from './collaboration-tuning';
import { EditorStateService } from './editor-state.service';
import { EditorHistoryService } from './editor-history.service';
import { EditorSelectionService } from './editor-selection.service';
import { EditorCommandService } from './editor-command.service';
import { EditorMemberCommandService } from './editor-member-command.service';
import { AiAssistantCommandService } from './ai-assistant-command.service';

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
  private readonly assistantCommandService = inject(AiAssistantCommandService);

  private readonly api = inject(UmlApiService);
  private readonly adapter = inject(UmlDiagramAdapterService);
  private readonly graphService = inject(UmlGraphService);
  private readonly attributeRowsService = inject(UmlAttributeRowsService);
  private readonly collabGateway = inject(COLLABORATION_GATEWAY);
  private readonly remoteCursorsService = inject(RemoteCursorsService);
  private readonly remoteCanvasSyncService = inject(RemoteCanvasSyncService);
  private readonly remoteNodeDragService = inject(RemoteNodeDragService);
  private readonly remoteLocksService = inject(RemoteLocksService);
  private readonly remotePresenceService = inject(RemotePresenceService);

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
  readonly collaborationState = this.collabGateway.connectionState;
  readonly isShareModalOpen = this.state.isShareModalOpen;
  readonly isAssistantPanelOpen = this.state.isAssistantPanelOpen;
  readonly isAssistantProcessing = this.state.isAssistantProcessing;
  readonly assistantError = this.state.assistantError;
  readonly assistantMessage = this.state.assistantMessage;
  readonly contextMenu = this.state.contextMenu;
  readonly remoteCursors = this.remoteCursorsService.cursors;
  readonly presencePeers = this.remotePresenceService.remotePeers;

  readonly validationResult = this.state.validationResult;
  readonly isValidating = this.state.isValidating;
  readonly isValidationPanelOpen = this.state.isValidationPanelOpen;

  readonly isGeneratingSpringBackend = this.state.isGeneratingSpringBackend;
  readonly springGenerationError = this.state.springGenerationError;

  constructor() {
    this.setupGraphSubscriptions();
  }

  private setupGraphSubscriptions(): void {
    this.graphService.nodeDragStarted$.subscribe((nodeId) => {
      const clsName = this.state.model().classes.find((c) => c.id === nodeId)?.name || 'elemento';
      this.remoteLocksService.acquireLock(nodeId, clsName, 'drag');
    });

    this.graphService.nodeMoved$.subscribe(({ nodeId, x, y }) => {
      this.moveElement(nodeId, x, y);
      this.collabGateway.sendNodeDragEnd(nodeId);
      const isSelected = this.selectedClass()?.id === nodeId;
      this.remoteLocksService.onNodeDragEnded(nodeId, isSelected);
    });

    toObservable(this.selectedClass)
      .pipe(startWith(null), pairwise())
      .subscribe(([prev, curr]) => {
        if (prev && (!curr || prev.id !== curr.id)) {
          this.remoteLocksService.onPanelClosed(prev.id);
        }
        if (curr && (!prev || prev.id !== curr.id)) {
          this.remoteLocksService.acquireLock(curr.id, curr.name, 'panel');
        }
      });

    toObservable(this.contextMenu)
      .pipe(startWith(null), pairwise())
      .subscribe(([prev, curr]) => {
        if (prev && (!curr || prev.edgeId !== curr.edgeId)) {
          this.remoteLocksService.onPanelClosed(prev.edgeId);
        }
        if (curr && (!prev || prev.edgeId !== curr.edgeId)) {
          const rel = this.state.model().relations.find((r) => r.id === curr.edgeId);
          this.remoteLocksService.acquireLock(curr.edgeId, rel?.name || 'relación', 'panel');
        }
      });

    this.graphService.nodeDragging$
      .pipe(
        throttleTime(NODE_DRAG_BROADCAST_THROTTLE_MS, undefined, { leading: true, trailing: true }),
      )
      .subscribe(({ nodeId, x, y }) => {
        this.collabGateway.sendNodeDragPosition(nodeId, x, y);
      });

    this.graphService.nodeResized$.subscribe(({ nodeId, width, height, x, y }) => {
      this.resizeElement(nodeId, width, height, x, y);
    });

    this.graphService.edgeConnected$.subscribe(
      ({ edgeId, sourceId, targetId, sourcePort, targetPort }) => {
        this.createRelation(
          sourceId,
          targetId,
          this.defaultRelationType(),
          edgeId,
          sourcePort,
          targetPort,
        );
      },
    );

    this.graphService.edgeReconnected$.subscribe(
      ({ edgeId, sourceId, targetId, sourcePort, targetPort }) => {
        const currentRel = this.state.model().relations.find((r) => r.id === edgeId);
        if (
          currentRel &&
          (currentRel.sourceClassId !== sourceId || currentRel.targetClassId !== targetId)
        ) {
          this.updateRelation(edgeId, { sourceClassId: sourceId, targetClassId: targetId });
        }
        this.updateRelationLayout(edgeId, sourcePort, targetPort);
      },
    );

    this.graphService.edgeVerticesChanged$.subscribe(({ edgeId, vertices }) => {
      this.updateRelationVertices(edgeId, vertices);
    });

    this.graphService.localPointerMove$
      .pipe(
        throttleTime(CURSOR_BROADCAST_THROTTLE_MS, undefined, { leading: true, trailing: true }),
      )
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
      if (
        currentSub &&
        (!selectedNodes.includes(currentSub.classId) || selectedNodes.length !== 1)
      ) {
        this.clearSubElement();
      }
    });

    // El compartimento de atributos (Fase 2) resuelve su propio click/doble-click
    // con listeners nativos por fila (ver UmlAttributeRowsService) en vez de la
    // geometría genérica de resolveSemanticTarget — mismo shape de evento, se
    // mergea acá para que el resto de la lógica de selección no distinga la fuente.
    merge(this.graphService.nodeSubElementClick$, this.attributeRowsService.rowClick$).subscribe(
      (event) => {
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
      },
    );

    this.attributeRowsService.deleteRequested$.subscribe(({ classId, attributeId }) => {
      this.deleteAttribute(classId, attributeId);
      this.clearSubElement();
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
      }),
    );
  }

  renderLoadedModel(): void {
    if (this.graphService.isInitialized) {
      const cells = this.adapter.modelToCells(this.model(), this.layout());
      this.graphService.renderCells(cells.nodes, cells.edges);
    }
  }

  /**
   * CU9: valida el modelo YA persistido del lienzo contra el motor real
   * (UMLValidator, vía POST /canvases/{id}/validate) — reemplaza el panel
   * legacy que en realidad consultaba a Gemini por WebSocket.
   */
  validateModel(): void {
    const id = this.canvasId();
    if (!id) return;
    this.state.setValidating(true);
    this.api.validateCanvas(id).subscribe({
      next: (result) => {
        this.state.setValidating(false);
        this.state.setValidationResult(result);
      },
      error: () => {
        this.state.setValidating(false);
      },
    });
  }

  /** CU8: exporta el lienzo actual a un archivo XMI 1.1/UML 1.3 compatible con Enterprise Architect. */
  exportXmi(): void {
    const id = this.canvasId();
    if (!id) return;
    this.api.exportXmi(id).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const name = this.canvasName() || 'modelo';
        a.download = `${name}.xmi`;
        a.click();
        window.URL.revokeObjectURL(url);
      },
      error: (err) => {
        console.error('[UmlEditorFacade] Error al exportar XMI:', err);
      },
    });
  }

  /** CU10: genera el backend Spring Boot real del lienzo actual y descarga el .zip resultante. */
  generateSpringBackend(): void {
    const id = this.canvasId();
    if (!id) return;
    this.state.setGeneratingSpringBackend(true);
    this.state.setSpringGenerationError(null);
    this.api.generateSpringBackend(id).subscribe({
      next: (response) => {
        this.state.setGeneratingSpringBackend(false);
        const blob = response.body;
        if (!blob) return;
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download =
          this.filenameFromContentDisposition(response.headers.get('Content-Disposition')) ??
          `${this.canvasName() || 'backend'}-spring-boot.zip`;
        a.click();
        window.URL.revokeObjectURL(url);
      },
      error: (err) => {
        this.state.setGeneratingSpringBackend(false);
        void this.reportSpringGenerationError(err);
      },
    });
  }

  /**
   * Con `responseType: 'blob'`, Angular también entrega el cuerpo de un error
   * HTTP como Blob (no JSON parseado) -- sin esto, los mensajes reales del
   * backend (ej. "el modelo usa herencia múltiple, no soportada") nunca
   * llegarían a mostrarse, y toda falla se vería como un error genérico.
   */
  private async reportSpringGenerationError(err: unknown): Promise<void> {
    const fallback = 'No se pudo generar el backend Spring Boot. Intentá de nuevo.';
    const httpErr = err as { error?: unknown };
    if (httpErr?.error instanceof Blob) {
      try {
        const text = await httpErr.error.text();
        const parsed = JSON.parse(text) as { message?: string };
        this.state.setSpringGenerationError(parsed.message || fallback);
        return;
      } catch {
        this.state.setSpringGenerationError(fallback);
        return;
      }
    }
    const message = (httpErr?.error as { message?: string } | undefined)?.message;
    this.state.setSpringGenerationError(message || fallback);
  }

  private filenameFromContentDisposition(header: string | null): string | null {
    if (!header) return null;
    const utf8Match = /filename\*=UTF-8''([^;]+)/i.exec(header);
    if (utf8Match) {
      try {
        return decodeURIComponent(utf8Match[1]);
      } catch {
        // sigue al fallback de abajo
      }
    }
    const plainMatch = /filename="?([^";]+)"?/i.exec(header);
    return plainMatch ? plainMatch[1] : null;
  }

  /** CU8: importa un archivo XMI delegando al ApiService. */
  importXmi(
    file: File,
  ): Observable<{ canvas: LienzoDetailDto; validation: ValidationResponseDto }> {
    return this.api.importXmi(file);
  }

  toggleValidationPanel(): void {
    this.state.toggleValidationPanel();
  }

  /** Selecciona y centra en el canvas el elemento señalado por un issue de validación. */
  focusIssue(elementId: string | null): void {
    if (!elementId) return;
    this.graphService.focusCell(elementId);
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

  openAssistantPanel(): void {
    this.state.openAssistantPanel();
  }

  closeAssistantPanel(): void {
    this.state.closeAssistantPanel();
  }

  toggleAssistantPanel(): void {
    this.state.toggleAssistantPanel();
  }

  sendAssistantPrompt(prompt: string): void {
    this.assistantCommandService.sendPrompt(prompt);
  }

  sendAssistantImage(image: File): void {
    this.assistantCommandService.sendImage(image);
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

  updateRelationVertices(relationId: string, vertices: { x: number; y: number }[]): void {
    this.commandService.updateRelationVertices(relationId, vertices);
  }

  /** Cierra el canal de colaboración y limpia los cursores remotos — llamar al salir del lienzo. */
  disconnectCollaboration(): void {
    this.collabGateway.disconnect();
    this.remoteCursorsService.reset();
    this.remoteNodeDragService.reset();
    this.remoteLocksService.reset();
    this.remotePresenceService.reset();
  }

  /** Reintento manual del canal de colaboración, tras agotarse los automáticos. */
  retryCollaboration(): void {
    this.collabGateway.retry();
  }

  deleteElement(elementId: string): void {
    this.selection.selectedNodes.set([elementId]);
    this.commandService.deleteSelected();
  }

  addAttribute(classId: string, attr?: Partial<UmlAttribute>): void {
    this.memberService.addAttribute(classId, attr);
  }

  updateAttribute(classId: string, attributeId: string, updates: Partial<UmlAttribute>): void {
    this.memberService.updateAttribute(classId, attributeId, updates);
  }

  deleteAttribute(classId: string, attributeId: string): void {
    this.memberService.deleteAttribute(classId, attributeId);
  }

  addOperation(classId: string, op?: Partial<UmlOperation>): void {
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
    updates: Partial<UmlParameter>,
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
    targetPort?: string,
  ): void {
    this.commandService.createRelation(
      sourceClassId,
      targetClassId,
      type,
      existingEdgeId,
      sourcePort,
      targetPort,
    );
  }

  updateRelation(relationId: string, updates: Partial<UmlRelationDto>): void {
    this.commandService.updateRelation(relationId, updates);
  }

  updateMultiplicity(
    relationId: string,
    sourceMultiplicity?: UmlMultiplicity | string,
    targetMultiplicity?: UmlMultiplicity | string,
  ): void {
    this.commandService.updateMultiplicity(
      relationId,
      sourceMultiplicity as string,
      targetMultiplicity as string,
    );
  }

  deleteRelation(relationId: string): void {
    this.commandService.deleteRelation(relationId);
  }

  dispatchCommand<T>(type: string, payload: T): void {
    this.commandService.dispatchCommand(type, payload);
  }

  isElementLockedByOther(elementId: string): boolean {
    return this.remoteLocksService.isLockedByOther(elementId);
  }

  getLockHolderName(elementId: string): string | null {
    return this.remoteLocksService.getLockHolderName(elementId);
  }

  recordActivity(elementId?: string, elementName?: string): void {
    this.remoteLocksService.recordActivity(elementId, elementName);
  }
}
