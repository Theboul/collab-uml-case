import { TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { UmlEditorFacade } from './uml-editor.facade';
import { UmlGraphService } from '../infrastructure/x6/uml-graph.service';
import { X6NodeConfig } from '../infrastructure/x6/uml-diagram-adapter.service';
import { COLLABORATION_GATEWAY, NoOpCollaborationGateway } from './collaboration-gateway.service';

class RecordingGateway extends NoOpCollaborationGateway {
  readonly dragPositions: { nodeId: string; x: number; y: number }[] = [];
  readonly dragEnds: string[] = [];

  override sendNodeDragPosition(nodeId: string, x: number, y: number): void {
    this.dragPositions.push({ nodeId, x, y });
  }

  override sendNodeDragEnd(nodeId: string): void {
    this.dragEnds.push(nodeId);
  }
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

async function waitFor<T>(find: () => T | null | undefined, timeoutMs = 2000): Promise<T> {
  const start = performance.now();
  for (;;) {
    const found = find();
    if (found) return found;
    if (performance.now() - start > timeoutMs) throw new Error('waitFor: timeout');
    await sleep(16);
  }
}

function fireMouse(target: EventTarget, type: string, x: number, y: number): void {
  target.dispatchEvent(
    new MouseEvent(type, {
      bubbles: true,
      cancelable: true,
      clientX: x,
      clientY: y,
      button: 0,
      buttons: type === 'mouseup' ? 0 : 1,
      view: window,
    }),
  );
}

function nodeConfig(id: string, x: number, y: number): X6NodeConfig {
  return {
    id,
    shape: 'uml-class-node',
    x,
    y,
    width: 190,
    height: 130,
    data: {
      name: id,
      isAbstract: false,
      attributes: [{ name: 'id', type: 'Long', visibility: '-' }],
      operations: [],
    },
  };
}

describe('Arrastre de clases: emisión en vivo hacia los peers (CU5)', () => {
  const STEPS = 60;
  let container: HTMLElement;
  let graphService: UmlGraphService;
  let gateway: RecordingGateway;

  /** Gesto real de mouse sobre el nodo: mousedown, STEPS mousemove intermedios y mouseup. */
  async function dragNode(nodeId: string, dx: number, dy: number, stepMs: number): Promise<void> {
    const nodeEl = await waitFor(() =>
      container.querySelector(`g.x6-node[data-cell-id="${nodeId}"]`),
    );
    const rect = nodeEl.getBoundingClientRect();
    const x0 = rect.left + rect.width / 2;
    const y0 = rect.top + 14;
    fireMouse(nodeEl, 'mousedown', x0, y0);
    for (let i = 1; i <= STEPS; i++) {
      await sleep(stepMs);
      fireMouse(document.body, 'mousemove', x0 + (dx * i) / STEPS, y0 + (dy * i) / STEPS);
    }
    fireMouse(document.body, 'mouseup', x0 + dx, y0 + dy);
    await sleep(50);
  }

  beforeEach(() => {
    gateway = new RecordingGateway();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: COLLABORATION_GATEWAY, useValue: gateway },
      ],
    });
    // El constructor del facade es quien conecta nodeDragging$ -> throttle -> gateway.
    TestBed.inject(UmlEditorFacade);
    graphService = TestBed.inject(UmlGraphService);

    container = document.createElement('div');
    container.style.cssText = 'position:fixed;left:0;top:0;width:900px;height:600px';
    document.body.appendChild(container);
    graphService.initGraph(container);
    graphService.addNode(nodeConfig('n1', 100, 100));
  });

  afterEach(() => {
    graphService.dispose();
    container.remove();
  });

  it('el grafo emite la posición del nodo en cada movimiento del arrastre, no solo al iniciar el gesto', async () => {
    const positions: { x: number; y: number }[] = [];
    graphService.nodeDragging$.subscribe(({ x, y }) => positions.push({ x, y }));

    await dragNode('n1', 200, 120, 4);

    // Con `node:move` (se dispara una única vez por gesto) esto daba 1.
    expect(positions.length).toBeGreaterThanOrEqual(STEPS * 0.8);
    const distinct = new Set(positions.map((p) => `${p.x},${p.y}`));
    expect(distinct.size).toBeGreaterThan(3);
  });

  it('se envían varios node_drag por el gateway durante un arrastre, con posiciones que avanzan', async () => {
    await dragNode('n1', 200, 120, 4);

    expect(gateway.dragPositions.length).toBeGreaterThanOrEqual(3);
    const distinct = new Set(gateway.dragPositions.map((p) => `${p.x},${p.y}`));
    expect(distinct.size).toBeGreaterThan(1);
    // la última posición transmitida es (cerca de) el destino real, no la de inicio
    const first = gateway.dragPositions[0];
    const last = gateway.dragPositions[gateway.dragPositions.length - 1];
    expect(last.x).toBeGreaterThan(first.x);
    expect(last.nodeId).toBe('n1');
  });

  it('el throttle acota la cadencia: no sale un mensaje por cada movimiento', async () => {
    await dragNode('n1', 200, 120, 4);

    // 60 movimientos en ~250 ms; sin throttle saldrían ~60 mensajes. El piso evita
    // que este test pase en vacío cuando el emisor casi no transmite nada.
    expect(gateway.dragPositions.length).toBeGreaterThanOrEqual(3);
    expect(gateway.dragPositions.length).toBeLessThan(STEPS / 2);
  });

  it('al soltar se avisa el fin del arrastre una vez', async () => {
    await dragNode('n1', 200, 120, 4);

    expect(gateway.dragEnds).toEqual(['n1']);
  });
});
