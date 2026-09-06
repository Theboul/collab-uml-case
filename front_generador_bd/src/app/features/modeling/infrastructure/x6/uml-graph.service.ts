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
import { X6EdgeConfig, X6NodeConfig } from './uml-diagram-adapter.service';

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
}

@Injectable({
  providedIn: 'root',
})
export class UmlGraphService {
  private readonly ngZone = inject(NgZone);
  private graph: Graph | null = null;
  private scrollerPlugin: Scroller | null = null;
  private dnd: Dnd | null = null;
  private registered = false;

  readonly selectionChange$ = new Subject<CellSelectionEvent>();
  readonly nodeMoved$ = new Subject<NodePositionChangeEvent>();
  readonly nodeResized$ = new Subject<NodeSizeChangeEvent>();
  readonly edgeConnected$ = new Subject<EdgeConnectedEvent>();
  readonly edgeRightClick$ = new Subject<{ edgeId: string; x: number; y: number }>();
  readonly blankClick$ = new Subject<{ x: number; y: number }>();
  readonly nodeAdded$ = new Subject<{ nodeId: string; name: string; x: number; y: number }>();
  readonly historyChange$ = new Subject<{ canUndo: boolean; canRedo: boolean }>();

  get isInitialized(): boolean {
    return this.graph !== null;
  }

  get rawGraph(): Graph | null {
    return this.graph;
  }

  /**
   * Registra el nodo visual canónico ClaseUML con estructura compartimental
   * (Nombre, Atributos y Operaciones) con SVG responsive y estilizado.
   */
  private registerUmlClassNode(): void {
    if (this.registered) return;
    try {
      Graph.registerNode('uml-class-node', {
        inherit: 'rect',
        width: 190,
        height: 130,
        markup: [
          { tagName: 'rect', selector: 'body' },
          { tagName: 'rect', selector: 'header' },
          { tagName: 'text', selector: 'title' },
          { tagName: 'line', selector: 'separator1' },
          { tagName: 'text', selector: 'attributes' },
          { tagName: 'line', selector: 'separator2' },
          { tagName: 'text', selector: 'operations' },
        ],
        attrs: {
          body: {
            refWidth: '100%',
            refHeight: '100%',
            fill: '#ffffff',
            stroke: '#1e293b',
            strokeWidth: 1.5,
            rx: 4,
            ry: 4,
          },
          header: {
            refWidth: '100%',
            height: 32,
            fill: '#f8fafc',
            stroke: 'none',
            rx: 4,
            ry: 4,
          },
          title: {
            refX: '50%',
            refY: 16,
            textAnchor: 'middle',
            textVerticalAnchor: 'middle',
            fontFamily: 'Inter, system-ui, sans-serif',
            fontSize: 13,
            fontWeight: 700,
            fill: '#0f172a',
          },
          separator1: {
            stroke: '#1e293b',
            strokeWidth: 1.5,
            x1: 0,
            refX2: '100%',
            y1: 32,
            y2: 32,
          },
          attributes: {
            refX: 10,
            refY: 42,
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 11,
            fill: '#334155',
            textAnchor: 'start',
            textVerticalAnchor: 'top',
          },
          separator2: {
            stroke: '#cbd5e1',
            strokeWidth: 1,
            x1: 0,
            refX2: '100%',
            y1: 82,
            y2: 82,
          },
          operations: {
            refX: 10,
            refY: 92,
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 11,
            fill: '#334155',
            textAnchor: 'start',
            textVerticalAnchor: 'top',
          },
        },
      });
      this.registered = true;
    } catch {
      this.registered = true;
    }
  }

  /**
   * Inicializa el Grafo X6 en el elemento contenedor con los plugins configurados.
   */
  initGraph(container: HTMLElement): Graph {
    this.registerUmlClassNode();

    this.graph = new Graph({
      container,
      autoResize: true,
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
        validateConnection({ sourceCell, targetCell }) {
          return Boolean(sourceCell && targetCell && sourceCell !== targetCell);
        },
      },
      interacting: {
        nodeMovable: true,
        edgeMovable: true,
      },
      mousewheel: {
        enabled: true,
        modifiers: ['ctrl', 'meta'],
        minScale: 0.2,
        maxScale: 3.0,
      },
    });

    // 1. Selección (Rubberband activado, selección múltiple con Ctrl/Cmd)
    this.graph.use(
      new Selection({
        enabled: true,
        multiple: true,
        rubberband: true,
        movable: true,
        showNodeSelectionBox: true,
        showEdgeSelectionBox: true,
        pointerEvents: 'auto',
        modifiers: ['ctrl', 'meta'],
      })
    );

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

    // 4. History (Deshacer / Rehacer)
    this.graph.use(
      new History({
        enabled: true,
        beforeAddCommand: (_event, args: any) => {
          if (args.key === 'tools' || args.key === 'selection') return false;
          return true;
        },
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
    return this.graph;
  }

  /**
   * Habilita o deshabilita el modo paneo (utilizado con la barra espaciadora).
   */
  setPanning(enabled: boolean): void {
    if (this.scrollerPlugin) {
      if (enabled) {
        this.scrollerPlugin.enablePanning();
      } else {
        this.scrollerPlugin.disablePanning();
      }
    }
  }

  private setupEventListeners(): void {
    if (!this.graph) return;

    // Movimiento persistente al terminar el arrastre
    this.graph.on('node:moved', ({ node }) => {
      this.ngZone.run(() => {
        const pos = node.getPosition();
        this.nodeMoved$.next({
          nodeId: node.id,
          x: pos.x,
          y: pos.y,
        });
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
    this.graph.on('edge:connected', ({ edge }) => {
      this.ngZone.run(() => {
        const source = edge.getSourceCell();
        const target = edge.getTargetCell();
        if (source && target) {
          this.edgeConnected$.next({
            edgeId: edge.id,
            sourceId: source.id,
            targetId: target.id,
          });
        }
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

    // Clic en fondo
    this.graph.on('blank:click', ({ e }) => {
      this.ngZone.run(() => {
        if (this.graph) {
          const p = this.graph.clientToLocal(e.clientX, e.clientY);
          this.blankClick$.next({ x: p.x, y: p.y });
        }
      });
    });

    // Selección
    this.graph.on('selection:changed', ({ selected }) => {
      this.ngZone.run(() => {
        const selectedNodes = selected.filter((c) => c.isNode()).map((c) => c.id);
        const selectedEdges = selected.filter((c) => c.isEdge()).map((c) => c.id);
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
  }

  addNode(config: X6NodeConfig): Node {
    if (!this.graph) throw new Error('Graph no inicializado');

    const titleText = config.data.name + (config.data.isAbstract ? ' {abstract}' : '');
    const attrsList = config.data.attributes?.length > 0
      ? config.data.attributes.map((a) => `${a.visibility} ${a.name} : ${a.type}`).join('\n')
      : '- id : UUID';
    const opsList = config.data.operations?.length > 0
      ? config.data.operations.map((o) => `${o.visibility} ${o.name}() : ${o.returnType}`).join('\n')
      : '+ ejecutar() : void';

    return this.graph.addNode({
      ...config,
      attrs: {
        title: { text: titleText },
        attributes: { text: attrsList },
        operations: { text: opsList },
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
        : '- id : UUID';
      const opsList = data.operations?.length > 0
        ? data.operations.map((o: any) => `${o.visibility} ${o.name}() : ${o.returnType}`).join('\n')
        : '+ ejecutar() : void';

      node.setAttrByPath('title/text', titleText);
      node.setAttrByPath('attributes/text', attrsList);
      node.setAttrByPath('operations/text', opsList);
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
        attributes: [{ name: 'id', type: 'UUID', visibility: '-' }],
        operations: [{ name: 'ejecutar', returnType: 'void', visibility: '+' }],
      },
      attrs: {
        title: { text: defaultName },
        attributes: { text: '- id : UUID' },
        operations: { text: '+ ejecutar() : void' },
      },
      ports: {
        groups: {
          top: { position: 'top', attrs: { circle: { r: 5, magnet: true, fill: '#fff', stroke: '#6366f1', strokeWidth: 2 } } },
          right: { position: 'right', attrs: { circle: { r: 5, magnet: true, fill: '#fff', stroke: '#6366f1', strokeWidth: 2 } } },
          bottom: { position: 'bottom', attrs: { circle: { r: 5, magnet: true, fill: '#fff', stroke: '#6366f1', strokeWidth: 2 } } },
          left: { position: 'left', attrs: { circle: { r: 5, magnet: true, fill: '#fff', stroke: '#6366f1', strokeWidth: 2 } } },
        },
        items: [
          { id: 'port-top', group: 'top' },
          { id: 'port-right', group: 'right' },
          { id: 'port-bottom', group: 'bottom' },
          { id: 'port-left', group: 'left' },
        ],
      },
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
    this.graph?.zoomToFit({ padding: 30, maxScale: 1.5 });
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
    this.graph?.dispose();
    this.graph = null;
    this.dnd = null;
    this.scrollerPlugin = null;
  }
}
