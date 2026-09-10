import { Injectable, NgZone, inject } from '@angular/core';
import { Subject } from 'rxjs';
import { Graph, Node, Edge } from '@antv/x6';
import { Selection } from '@antv/x6-plugin-selection';
import { Transform } from '@antv/x6-plugin-transform';
import { History } from '@antv/x6-plugin-history';
import { Snapline } from '@antv/x6-plugin-snapline';
import { Scroller } from '@antv/x6-plugin-scroller';
import { Dnd } from '@antv/x6-plugin-dnd';
import { Clipboard } from '@antv/x6-plugin-clipboard';
import { UmlDiagramAdapterService, X6EdgeConfig, X6NodeConfig } from './uml-diagram-adapter.service';
import { UML_NODE_DIMENSIONS, UmlNodeSubElementEvent } from '../../domain/models/uml-editor.models';
import { UmlPortService } from './uml-port.service';
import { UmlInteractionService } from './uml-interaction.service';
import { UmlEdgeToolsService } from './uml-edge-tools.service';
import { registerUmlClassNode } from './uml-class-node.registration';

export interface CellSelectionEvent {
  selectedNodes: string[];
  selectedEdges: string[];
}

export interface NodePositionChangeEvent {
  nodeId: string;
  x: number;
  y: number;
}

export interface NodeSizeChangeEvent {
  nodeId: string;
  width: number;
  height: number;
  x: number;
  y: number;
}

export interface EdgeConnectedEvent {
  edgeId: string;
  sourceId: string;
  targetId: string;
  sourcePort?: string;
  targetPort?: string;
}

export interface EdgeReconnectedEvent {
  edgeId: string;
  sourceId: string;
  targetId: string;
  sourcePort?: string;
  targetPort?: string;
}

export interface NodeDblClickEvent {
  nodeId: string;
  targetType: 'class' | 'attribute' | 'operation';
  targetId?: string;
  name: string;
  type?: string;
  visibility?: string;
  itemRelY: number;
  nodeBBox: { x: number; y: number; width: number; height: number };
}

@Injectable({
  providedIn: 'root',
})
export class UmlGraphService {
  private readonly ngZone = inject(NgZone);
  private readonly portService = inject(UmlPortService);
  private readonly interactionService = inject(UmlInteractionService);
  private readonly edgeToolsService = inject(UmlEdgeToolsService);
  private readonly adapter = inject(UmlDiagramAdapterService);

  private graph: Graph | null = null;
  private scrollerPlugin: Scroller | null = null;
  private selectionPlugin: Selection | null = null;
  private dnd: Dnd | null = null;
  private isPanningActive = false;
  private pointerMoveContainer: HTMLElement | null = null;
  private readonly handlePointerMove = (e: MouseEvent): void => {
    if (!this.graph) return;
    const { x, y } = this.graph.clientToLocal(e.clientX, e.clientY);
    this.localPointerMove$.next({ x, y });
  };

  readonly selectionChange$ = new Subject<CellSelectionEvent>();
  readonly nodeMoved$ = new Subject<NodePositionChangeEvent>();
  readonly nodeResized$ = new Subject<NodeSizeChangeEvent>();
  readonly edgeConnected$ = new Subject<EdgeConnectedEvent>();
  readonly edgeReconnected$ = new Subject<EdgeReconnectedEvent>();
  readonly edgeVerticesChanged$ = this.edgeToolsService.verticesChanged$;
  readonly edgeRightClick$ = new Subject<{ edgeId: string; x: number; y: number }>();
  readonly blankClick$ = new Subject<{ x: number; y: number }>();
  readonly nodeAdded$ = new Subject<{ nodeId: string; name: string; x: number; y: number }>();
  readonly nodeDblClick$ = new Subject<NodeDblClickEvent>();
  readonly nodeSubElementClick$ = new Subject<UmlNodeSubElementEvent>();
  readonly historyChange$ = new Subject<{ canUndo: boolean; canRedo: boolean }>();
  /**
   * Posición del mouse en coordenadas locales del canvas (ya convertidas vía
   * clientToLocal, robustas a pan/zoom), sin throttle — eso es
   * responsabilidad del consumidor (ver UmlEditorFacade). Se emite fuera de
   * la zona de Angular por ser de alta frecuencia; no hace falta CD para
   * mandar la posición por WebSocket.
   */
  readonly localPointerMove$ = new Subject<{ x: number; y: number }>();

  get isInitialized(): boolean {
    return this.graph !== null;
  }

  get rawGraph(): Graph | null {
    return this.graph;
  }

  /**
   * Inicializa el Grafo X6 en el elemento contenedor con los plugins configurados.
   */
  initGraph(container: HTMLElement): Graph {
    registerUmlClassNode();

    this.graph = new Graph({
      container,
      autoResize: true,
      moveThreshold: 2,
      background: {
        color: '#f8fafc',
      },
      grid: {
        size: 20,
        visible: true,
        type: 'dot',
        args: {
          color: '#94a3b8',
          thickness: 1.5,
        },
      },
      connecting: {
        snap: true,
        allowBlank: false,
        allowLoop: false,
        allowNode: true,
        allowPort: true,
        highlight: true,
        router: { name: 'manhattan' },
        connector: { name: 'rounded' },
        connectionPoint: 'boundary',
        createEdge() {
          return this.createEdge({
            shape: 'edge',
            router: { name: 'manhattan' },
            connector: { name: 'rounded' },
            attrs: {
              line: {
                stroke: '#334155',
                strokeWidth: 1.75,
              },
            },
            data: {
              relationType: 'ASSOCIATION',
              sourceMultiplicity: '1',
              targetMultiplicity: '1',
            },
          });
        },
        validateMagnet: ({ magnet }) => this.portService.validateMagnet(magnet),
        validateConnection: ({ sourceCell, targetCell, sourceMagnet }) =>
          this.portService.validateConnection(sourceCell, targetCell, sourceMagnet),
      },
      interacting: {
        nodeMovable: () => !this.isPanningActive,
        edgeMovable: () => !this.isPanningActive,
        vertexMovable: () => !this.isPanningActive,
        arrowheadMovable: () => !this.isPanningActive,
      },
      mousewheel: {
        enabled: true,
        modifiers: ['ctrl', 'meta'],
        minScale: 0.2,
        maxScale: 3.0,
      },
    });

    // 1. Selección (Rubberband activado en espacio vacío, selección múltiple con Ctrl/Cmd/Shift)
    this.selectionPlugin = new Selection({
      enabled: true,
      multiple: true,
      rubberband: true,
      movable: true,
      showNodeSelectionBox: true,
      showEdgeSelectionBox: true,
      pointerEvents: 'none',
      multipleSelectionModifiers: ['ctrl', 'meta', 'shift'],
    });
    this.graph.use(this.selectionPlugin);

    // 2. Transform (Resize únicamente en las 4 esquinas para no chocar con los 4 puertos)
    this.graph.use(
      new Transform({
        resizing: {
          enabled: true,
          minWidth: 160,
          minHeight: 90,
          orthogonal: false, // ¡Solo esquinas (nw, ne, se, sw)! Los bordes quedan libres para los puertos.
        },
      })
    );

    // 3. Snapline (Alineación magnética entre clases)
    this.graph.use(
      new Snapline({
        enabled: true,
        sharp: true,
      })
    );

    // 4. History (Desactivado en X6; el historial semántico de UmlEditorFacade es la única fuente)
    this.graph.use(
      new History({
        enabled: false,
      })
    );

    // 5. Scroller (Pan con espacio o botón central, permitiendo rubberband en drag vacío)
    this.scrollerPlugin = new Scroller({
      enabled: true,
      pannable: false, // Importante: false permite que el drag estándar dibuje el rectángulo de selección
      pageVisible: false,
      pageBreak: false,
    });
    this.graph.use(this.scrollerPlugin);

    // 6. Clipboard (Copiar / Pegar)
    this.graph.use(new Clipboard({ enabled: true }));

    // 7. Drag & Drop
    this.dnd = new Dnd({
      target: this.graph,
      scaled: false,
    });

    this.setupEventListeners();

    this.pointerMoveContainer = container;
    this.ngZone.runOutsideAngular(() => {
      container.addEventListener('mousemove', this.handlePointerMove);
    });

    return this.graph;
  }

  /**
   * Habilita o deshabilita el modo paneo (utilizado con la barra espaciadora).
   * Al activar, desactiva el rubberband de selección y bloquea el arrastre de nodos.
   */
  setPanning(enabled: boolean): void {
    this.isPanningActive = enabled;
    if (this.scrollerPlugin) {
      if (enabled) {
        this.selectionPlugin?.disableRubberband();
        this.selectionPlugin?.disable();
        this.scrollerPlugin.enablePanning();
      } else {
        this.scrollerPlugin.disablePanning();
        this.selectionPlugin?.enable();
        this.selectionPlugin?.enableRubberband();
      }
    }
  }

  private setupEventListeners(): void {
    if (!this.graph) return;

    this.edgeToolsService.registerListeners(this.graph);

    // Movimiento persistente al terminar el arrastre
    this.graph.on('node:moved', ({ node }) => {
      if (this.isPanningActive) return;
      this.ngZone.run(() => {
        const pos = node.getPosition();
        this.nodeMoved$.next({
          nodeId: node.id,
          x: pos.x,
          y: pos.y,
        });
      });
    });

    // Clic en nodo -> Seleccionar nodo y detectar subelemento (Atributo, Operación o Encabezado)
    this.graph.on('node:click', ({ node, e }) => {
      this.ngZone.run(() => {
        const subEvent = this.resolveSemanticTarget(node, e.clientX, e.clientY, e.target as SVGElement);
        if (subEvent) {
          this.nodeSubElementClick$.next(subEvent);
        }
      });
    });

    // Doble clic en nodo -> Edición inline semántica (Clase, Atributo u Operación)
    this.graph.on('node:dblclick', ({ node, e }) => {
      e.stopPropagation();
      this.ngZone.run(() => {
        const eventData = this.resolveSemanticTarget(node, e.clientX, e.clientY, e.target as SVGElement);
        if (eventData) {
          this.nodeDblClick$.next({
            nodeId: eventData.classId,
            targetType: eventData.type,
            targetId: eventData.elementId,
            name: eventData.name || '',
            type: eventData.typeOrReturn,
            visibility: eventData.visibility,
            itemRelY: eventData.itemRelY,
            nodeBBox: eventData.nodeBBox,
          });
        }
      });
    });

    // Redimensionamiento
    this.graph.on('node:resized', ({ node }) => {
      this.ngZone.run(() => {
        const pos = node.getPosition();
        const size = node.getSize();
        this.nodeResized$.next({
          nodeId: node.id,
          x: pos.x,
          y: pos.y,
          width: size.width,
          height: size.height,
        });
      });
    });

    // Conexión entre clases (desde puerto o herramienta)
    this.graph.on('edge:connected', ({ isNew, edge }) => {
      this.ngZone.run(() => {
        const source = edge.getSourceCell();
        const target = edge.getTargetCell();
        if (!source || !target) return;

        if (isNew) {
          this.edgeConnected$.next({
            edgeId: edge.id,
            sourceId: source.id,
            targetId: target.id,
            sourcePort: edge.getSourcePortId(),
            targetPort: edge.getTargetPortId(),
          });
          return;
        }

        // Reconexión de una relación ya existente (se arrastró uno de sus extremos a otro
        // puerto/clase): NO se trata como una relación nueva, solo se actualiza dónde se
        // conecta visualmente.
        this.edgeReconnected$.next({
          edgeId: edge.id,
          sourceId: source.id,
          targetId: target.id,
          sourcePort: edge.getSourcePortId(),
          targetPort: edge.getTargetPortId(),
        });
      });
    });

    // Clic en arista -> seleccionarla
    this.graph.on('edge:click', ({ edge, e }) => {
      e.stopPropagation();
      this.ngZone.run(() => {
        if (!e.ctrlKey && !e.metaKey) {
          this.graph?.cleanSelection();
        }
        this.graph?.select(edge);
      });
    });

    // Clic derecho en arista -> seleccionar y abrir menú contextual
    this.graph.on('edge:contextmenu', ({ edge, e }) => {
      e.preventDefault();
      e.stopPropagation();
      this.ngZone.run(() => {
        this.graph?.cleanSelection();
        this.graph?.select(edge);
        this.edgeRightClick$.next({
          edgeId: edge.id,
          x: e.clientX,
          y: e.clientY,
        });
      });
    });

    // Clic en fondo -> ocultar puertos, limpiar highlight y notificar clic en blanco
    this.graph.on('blank:click', ({ e }) => {
      this.ngZone.run(() => {
        this.clearRowHighlight();
        this.hideAllPorts();
        if (this.graph) {
          const p = this.graph.clientToLocal(e.clientX, e.clientY);
          this.blankClick$.next({ x: p.x, y: p.y });
        }
      });
    });

    // Selección -> actualizar visibilidad de puertos según cardinalidad (1 clase = visible, multiselección/0 = oculto)
    this.graph.on('selection:changed', ({ selected }) => {
      this.ngZone.run(() => {
        const selectedNodes = selected.filter((c) => c.isNode()).map((c) => c.id);
        const selectedEdges = selected.filter((c) => c.isEdge()).map((c) => c.id);
        this.updatePortsVisibility(selectedNodes);
        if (selectedNodes.length !== 1) {
          this.clearRowHighlight();
        }
        this.selectionChange$.next({ selectedNodes, selectedEdges });
      });
    });

    // Historial
    this.graph.on('history:change', () => {
      this.ngZone.run(() => {
        this.historyChange$.next({
          canUndo: this.canUndo(),
          canRedo: this.canRedo(),
        });
      });
    });

    // Dnd drop: capturar cuando un nodo se agrega al grafo por Dnd
    this.graph.on('node:added', ({ node }) => {
      this.ngZone.run(() => {
        const data = node.getData() || {};
        const pos = node.getPosition();
        this.nodeAdded$.next({
          nodeId: node.id,
          name: data.name || 'Clase',
          x: pos.x,
          y: pos.y,
        });
      });
    });
  }

  /**
   * Muestra los puertos de conexión de un nodo específico.
   */
  showPorts(nodeId: string): void {
    this.portService.showPorts(this.graph, nodeId);
  }

  /**
   * Oculta los puertos de conexión de un nodo específico.
   */
  hidePorts(nodeId: string): void {
    this.portService.hidePorts(this.graph, nodeId);
  }

  /**
   * Oculta los puertos de conexión de todos los nodos del lienzo.
   */
  hideAllPorts(): void {
    this.portService.hideAllPorts(this.graph);
  }

  /**
   * Encapsula la regla de visibilidad de puertos:
   * 1 clase seleccionada -> 4 puertos visibles.
   * 0 o 2+ clases seleccionadas -> puertos ocultos.
   */
  updatePortsVisibility(selectedNodeIds: string[]): void {
    this.portService.updatePortsVisibility(this.graph, selectedNodeIds);
  }

  /**
   * Resuelve semánticamente el objetivo de interacción (clic o doble clic) dentro de un nodo UML:
   * Encabezado (Clase), Compartimento de Atributos (por attributeId), o de Operaciones (por operationId).
   */
  resolveSemanticTarget(
    node: Node,
    clientX: number,
    clientY: number,
    targetElem?: SVGElement | null
  ): UmlNodeSubElementEvent | null {
    return this.interactionService.resolveSemanticTarget(
      this.graph,
      node,
      clientX,
      clientY,
      targetElem
    );
  }

  /**
   * Resalta visualmente una fila específica dentro de un nodo UML mediante el subelemento SVG nativo.
   */
  setRowHighlight(nodeId: string, itemRelY: number): void {
    this.interactionService.setRowHighlight(this.graph, nodeId, itemRelY);
  }

  /**
   * Oculta el resaltado visual de fila en un nodo o en todos los nodos del lienzo.
   */
  clearRowHighlight(nodeId?: string): void {
    this.interactionService.clearRowHighlight(this.graph, nodeId);
  }

  /**
   * Renderiza el diagrama completo a partir de las configuraciones traducidas.
   */
  renderCells(nodes: X6NodeConfig[], edges: X6EdgeConfig[]): void {
    if (!this.graph) return;
    this.graph.clearCells();

    for (const nodeConfig of nodes) {
      this.addNode(nodeConfig);
    }

    for (const edgeConfig of edges) {
      this.graph.addEdge(edgeConfig);
    }

    this.hideAllPorts();
  }

  addNode(config: X6NodeConfig): Node {
    if (!this.graph) throw new Error('Graph no inicializado');

    const titleText = config.data.name + (config.data.isAbstract ? ' {abstract}' : '');
    const attrsList = config.data.attributes?.length > 0
      ? config.data.attributes.map((a) => `${a.visibility} ${a.name} : ${a.type}`).join('\n')
      : '';

    const opsList = config.data.operations?.length > 0
      ? config.data.operations
          .map((o) => {
            let paramsStr = '';
            if (Array.isArray(o.parameters)) {
              paramsStr = o.parameters.map((p: any) => `${p.name}: ${p.type}`).join(', ');
            } else if (typeof o.parameters === 'string') {
              paramsStr = o.parameters;
            }
            return `${o.visibility || '+'} ${o.name}(${paramsStr}) : ${o.returnType || 'void'}`;
          })
          .join('\n')
      : '';

    const attrLines = (config.data.attributes || []).length;
    const attrHeight = Math.max(1, attrLines) * UML_NODE_DIMENSIONS.LINE_HEIGHT;
    const sep2Y = UML_NODE_DIMENSIONS.HEADER_HEIGHT + UML_NODE_DIMENSIONS.SEP_PADDING + attrHeight + 6;
    const opY = sep2Y + UML_NODE_DIMENSIONS.SEP_PADDING;
    const opLines = (config.data.operations || []).length;
    const opHeight = Math.max(1, opLines) * UML_NODE_DIMENSIONS.LINE_HEIGHT;
    const totalHeight = Math.max(
      config.height || UML_NODE_DIMENSIONS.MIN_HEIGHT,
      opY + opHeight + UML_NODE_DIMENSIONS.BOTTOM_PADDING
    );

    return this.graph.addNode({
      ...config,
      height: Math.max(config.height || UML_NODE_DIMENSIONS.MIN_HEIGHT, totalHeight),
      attrs: {
        title: { text: titleText },
        attributes: { text: attrsList },
        separator2: { y1: sep2Y, y2: sep2Y },
        operations: { text: opsList, refY: opY },
      },
    });
  }

  addEdge(config: X6EdgeConfig): Edge {
    if (!this.graph) throw new Error('Graph no inicializado');
    return this.graph.addEdge(config);
  }

  updateNodeData(nodeId: string, data: any): void {
    if (!this.graph) return;
    const node = this.graph.getCellById(nodeId);
    if (node && node.isNode()) {
      node.setData(data);
      const titleText = data.name + (data.isAbstract ? ' {abstract}' : '');
      const attrsList = data.attributes?.length > 0
        ? data.attributes.map((a: any) => `${a.visibility} ${a.name} : ${a.type}`).join('\n')
        : '';
      const opsList = data.operations?.length > 0
        ? data.operations
            .map((o: any) => {
              let paramsStr = '';
              if (Array.isArray(o.parameters)) {
                paramsStr = o.parameters.map((p: any) => `${p.name}: ${p.type}`).join(', ');
              } else if (typeof o.parameters === 'string') {
                paramsStr = o.parameters;
              }
              return `${o.visibility || '+'} ${o.name}(${paramsStr}) : ${o.returnType || 'void'}`;
            })
            .join('\n')
        : '';

      const attrLines = (data.attributes || []).length;
      const attrHeight = Math.max(1, attrLines) * UML_NODE_DIMENSIONS.LINE_HEIGHT;
      const sep2Y = UML_NODE_DIMENSIONS.HEADER_HEIGHT + UML_NODE_DIMENSIONS.SEP_PADDING + attrHeight + 6;
      const opY = sep2Y + UML_NODE_DIMENSIONS.SEP_PADDING;
      const opLines = (data.operations || []).length;
      const opHeight = Math.max(1, opLines) * UML_NODE_DIMENSIONS.LINE_HEIGHT;
      const totalHeight = Math.max(
        UML_NODE_DIMENSIONS.MIN_HEIGHT,
        opY + opHeight + UML_NODE_DIMENSIONS.BOTTOM_PADDING
      );

      node.setAttrByPath('title/text', titleText);
      node.setAttrByPath('attributes/text', attrsList);
      node.setAttrByPath('separator2/y1', sep2Y);
      node.setAttrByPath('separator2/y2', sep2Y);
      node.setAttrByPath('operations/text', opsList);
      node.setAttrByPath('operations/refY', opY);

      const currentSize = node.getSize();
      node.setSize({
        width: Math.max(currentSize.width, UML_NODE_DIMENSIONS.MIN_WIDTH),
        height: Math.max(currentSize.height, totalHeight),
      });

      const selected = this.graph.getSelectedCells().filter((c) => c.isNode()).map((c) => c.id);
      this.updatePortsVisibility(selected);
    }
  }

  deleteCell(cellId: string): void {
    if (!this.graph) return;
    const cell = this.graph.getCellById(cellId);
    if (cell) {
      this.graph.removeCell(cell);
    }
  }

  deleteSelected(): void {
    if (!this.graph) return;
    const cells = this.graph.getSelectedCells();
    if (cells.length > 0) {
      this.graph.removeCells(cells);
    }
  }

  /**
   * Inicia el arrastre nativo de una clase UML desde la paleta con atributos iniciales.
   */
  startDnd(nodeElement: HTMLElement, event: MouseEvent, defaultName = 'NuevaClase'): void {
    if (!this.graph || !this.dnd) return;
    const node = this.graph.createNode({
      shape: 'uml-class-node',
      width: 190,
      height: 130,
      data: {
        name: defaultName,
        isAbstract: false,
        attributes: [],
        operations: [],
      },
      attrs: {
        title: { text: defaultName },
        attributes: { text: '' },
        operations: { text: '' },
      },
      ports: this.adapter.getDefaultPorts(),
    });
    this.dnd.start(node, event);
  }

  zoomIn(): void {
    this.graph?.zoom(0.1);
  }

  zoomOut(): void {
    this.graph?.zoom(-0.1);
  }

  zoomToFit(): void {
    if (this.scrollerPlugin) {
      this.scrollerPlugin.zoomToFit({ padding: 30, maxScale: 1.5 });
      this.scrollerPlugin.centerContent();
    } else {
      this.graph?.zoomToFit({ padding: 30, maxScale: 1.5 });
    }
  }

  resetZoom(): void {
    this.graph?.zoomTo(1);
  }

  undo(): void {
    this.graph?.undo();
  }

  redo(): void {
    this.graph?.redo();
  }

  canUndo(): boolean {
    return Boolean(this.graph?.canUndo());
  }

  canRedo(): boolean {
    return Boolean(this.graph?.canRedo());
  }

  dispose(): void {
    this.pointerMoveContainer?.removeEventListener('mousemove', this.handlePointerMove);
    this.pointerMoveContainer = null;
    this.graph?.dispose();
    this.graph = null;
    this.dnd = null;
    this.scrollerPlugin = null;
    this.selectionPlugin = null;
  }
}
