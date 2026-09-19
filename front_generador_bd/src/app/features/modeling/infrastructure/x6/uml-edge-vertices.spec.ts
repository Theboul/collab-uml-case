import { TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { UmlEditorFacade } from '../../application/uml-editor.facade';
import {
  COLLABORATION_GATEWAY,
  NoOpCollaborationGateway,
} from '../../application/collaboration-gateway.service';
import { UmlGraphService } from './uml-graph.service';
import { EdgeVerticesChangedEvent } from './uml-edge-tools.service';
import { X6EdgeConfig, X6NodeConfig } from './uml-diagram-adapter.service';

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

function edgeConfig(id: string, source: string, target: string): X6EdgeConfig {
  return {
    id,
    source: { cell: source },
    target: { cell: target },
    router: { name: 'manhattan' },
    connector: { name: 'rounded' },
    vertices: [],
    attrs: { line: { stroke: '#334155', strokeWidth: 1.75 } },
    data: { relationType: 'ASSOCIATION', sourceMultiplicity: '1', targetMultiplicity: '*' },
  };
}

describe('Herramienta de vértices de relaciones: persistencia al mover / borrar (CU4)', () => {
  const STEPS = 12;
  let container: HTMLElement;
  let graphService: UmlGraphService;
  let facade: UmlEditorFacade;
  let updateRelationVertices: jasmine.Spy;
  let emitted: EdgeVerticesChangedEvent[];

  function toolPath(): SVGGeometryElement | null {
    return container.querySelector<SVGGeometryElement>('.x6-edge-tool-vertex-path');
  }

  function midpointOf(path: SVGGeometryElement): { x: number; y: number } {
    const m = path.getScreenCTM()!;
    const p = path.getPointAtLength(path.getTotalLength() / 2);
    return { x: m.a * p.x + m.c * p.y + m.e, y: m.b * p.x + m.d * p.y + m.f };
  }

  /**
   * Arrastra la relación agarrándola por su centro (X6 agrega un vértice ahí y lo
   * arrastra). Devuelve cuántas emisiones de persistencia hubo ANTES de soltar.
   */
  async function dragEdgeMidpoint(dy: number): Promise<{ emittedBeforeRelease: number }> {
    const path = await waitFor(toolPath);
    // La arista se rutea y se pinta de forma asíncrona: se espera a que su punto medio
    // deje de moverse antes de agarrarla (con la máquina cargada se medía a mitad de layout).
    let { x, y } = midpointOf(path);
    for (let stable = 0; stable < 3;) {
      await sleep(16);
      const next = midpointOf(path);
      stable = next.x === x && next.y === y ? stable + 1 : 0;
      ({ x, y } = next);
    }
    fireMouse(path, 'mousedown', x, y);
    for (let i = 1; i <= STEPS; i++) {
      await sleep(4);
      fireMouse(document.body, 'mousemove', x, y + (dy * i) / STEPS);
    }
    const emittedBeforeRelease = emitted.length;
    fireMouse(document.body, 'mouseup', x, y + dy);
    // Espera a que llegue la emisión de persistencia y deja un margen para que un
    // duplicado (el bug que este spec cubre) alcance a manifestarse.
    await waitFor(() => emitted.length > 0);
    await sleep(60);
    return { emittedBeforeRelease };
  }

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: COLLABORATION_GATEWAY, useValue: new NoOpCollaborationGateway() },
      ],
    });
    facade = TestBed.inject(UmlEditorFacade);
    updateRelationVertices = spyOn(facade, 'updateRelationVertices');
    graphService = TestBed.inject(UmlGraphService);

    emitted = [];
    graphService.edgeVerticesChanged$.subscribe((e) => emitted.push(e));

    container = document.createElement('div');
    container.style.cssText = 'position:fixed;left:0;top:0;width:900px;height:600px';
    document.body.appendChild(container);
    graphService.initGraph(container);
    graphService.addNode(nodeConfig('a', 100, 100));
    graphService.addNode(nodeConfig('b', 500, 100));
    graphService.addEdge(edgeConfig('e1', 'a', 'b'));
  });

  afterEach(() => {
    graphService.dispose();
    container.remove();
  });

  it('un arrastre de vértice no persiste nada durante el gesto: una sola actualización al soltar', async () => {
    const { emittedBeforeRelease } = await dragEdgeMidpoint(-120);

    expect(emittedBeforeRelease).toBe(0);
    expect(emitted.length).toBe(1);
    expect(emitted[0].edgeId).toBe('e1');
    expect(emitted[0].vertices.length).toBe(1);
  });

  it('el facade recibe un único UPDATE_RELATION_VERTICES por gesto, con el vértice final', async () => {
    await dragEdgeMidpoint(-120);

    expect(updateRelationVertices).toHaveBeenCalledTimes(1);
    const [relationId, vertices] = updateRelationVertices.calls.mostRecent().args;
    expect(relationId).toBe('e1');
    expect(vertices.length).toBe(1);
  });

  it('un vértice realmente eliminado (doble clic sobre su handle) sí se persiste, una vez y sin vértices', async () => {
    await dragEdgeMidpoint(-120);
    expect(emitted.length).toBe(1);

    const handle = await waitFor(() => container.querySelector('.x6-edge-tool-vertex'));
    const r = handle.getBoundingClientRect();
    fireMouse(handle, 'dblclick', r.left + r.width / 2, r.top + r.height / 2);
    await sleep(80);

    expect(emitted.length).toBe(2);
    expect(emitted[1].vertices).toEqual([]);
  });

  it('cambios de vértices hechos por código (reconciliación de un snapshot remoto) no se re-persisten', async () => {
    const edge = graphService.rawGraph!.getCellById('e1') as ReturnType<
      typeof graphService.addEdge
    >;

    edge.setVertices([{ x: 300, y: 60 }]);
    edge.setVertices([{ x: 320, y: 60 }]);
    edge.setVertices([]);
    await sleep(50);

    expect(emitted.length).toBe(0);
    expect(updateRelationVertices).not.toHaveBeenCalled();
  });
});
