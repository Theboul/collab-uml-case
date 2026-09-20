/**
 * Sincronización por deltas en un navegador REAL contra un servidor REAL (Nivel B).
 *
 * Ana edita el lienzo por HTTP (comandos reales del editor). Beto es un cliente completo: gateway
 * WebSocket real + RemoteCanvasSyncService real + UmlApiService real; solo se sustituyen el
 * `EditorCommandService` (que aquí solo escribe el estado, sin grafo X6) y el grafo. Se comprueba
 * que los cambios de Ana llegan a Beto como deltas y que su estado converge con el del servidor.
 *
 * Necesita el arnés `scripts/collab-e2e/run.py` (uvicorn + proxy que se puede cortar). Sin él, los
 * tests quedan pendientes y `ng test` sigue verde. Ver scripts/collab-e2e/README.md.
 */

import { HttpInterceptorFn, provideHttpClient, withInterceptors } from '@angular/common/http';
import { inject, provideZonelessChangeDetection, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Subject, filter, firstValueFrom, of } from 'rxjs';
import { AuthService } from '../../../core/auth';
import { CanvasDeltaMessage } from '../domain/canvas-delta';
import { DiagramLayout, LienzoDetailDto, ModeloUML } from '../domain/models/uml-editor.models';
import { UmlGraphService } from '../infrastructure/x6/uml-graph.service';
import {
  COLLABORATION_GATEWAY,
  CollaborationGateway,
  WebSocketCollaborationGateway,
} from './collaboration-gateway.service';
import {
  admin,
  backend,
  loadHarnessConfig,
  resetHarness,
  waitFor,
} from './collaboration-integration.harness.spec';
import { EditorCommandService } from './editor-command.service';
import { EditorStateService } from './editor-state.service';
import { RemoteCanvasSyncService } from './remote-canvas-sync.service';
import { RemoteNodeDragService } from './remote-node-drag.service';
import { UmlApiService } from './uml-api.service';

/** Ana: el dueño edita por HTTP, como lo haría su editor. Devuelve la versión resultante. */
async function ana(type: string, payload: Record<string, unknown>): Promise<number> {
  const c = backend();
  const headers = { Authorization: `Bearer ${c.tokens.owner}`, 'Content-Type': 'application/json' };
  const url = `${c.httpBase}/api/v2/canvases/${c.canvasId}`;
  const actual = (await (await fetch(url, { headers })).json()) as { version: number };
  const res = await fetch(`${url}/commands`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ expectedVersion: actual.version, type, payload }),
  });
  expect(res.status)
    .withContext(`${type} → ${await res.clone().text()}`)
    .toBe(200);
  return ((await res.json()) as { version: number }).version;
}

const nuevaClase = (classId: string, name: string, x: number) =>
  ana('CREATE_CLASS', { classId, name, x, y: 40, width: 190, height: 130 });

interface Beto {
  gateway: WebSocketCollaborationGateway;
  state: EditorStateService;
  api: UmlApiService;
  /** Deltas que el gateway real entregó (antes de cualquier descarte simulado). */
  received: CanvasDeltaMessage[];
  /** GET del lienzo que hizo Beto después de cargarlo (= resincronizaciones). */
  resyncs: () => number;
}

/** Monta a Beto: gateway real conectado y abierto, con el lienzo ya cargado por HTTP. */
async function montarBeto(dropDelta: (message: CanvasDeltaMessage) => boolean = () => false) {
  const c = backend();
  const auth = {
    currentUser: () => ({ fullName: 'Beto' }),
    accessToken: signal<string | null>(c.tokens.peer),
    refreshSession: () => of({}),
  } as unknown as AuthService;
  const gateway = new WebSocketCollaborationGateway(auth, c.wsBase);

  const received: CanvasDeltaMessage[] = [];
  let gets = 0;
  const alServidorReal: HttpInterceptorFn = (req, next) => {
    if (req.method === 'GET') gets++;
    return next(
      req.clone({
        url: c.httpBase + req.url,
        setHeaders: { Authorization: `Bearer ${c.tokens.peer}` },
      }),
    );
  };
  // El gateway real entrega todo; el sync solo ve lo que `dropDelta` no descarte (pérdida simulada).
  const visto: CollaborationGateway = Object.assign(Object.create(gateway), {
    remoteCanvasDelta$: gateway.remoteCanvasDelta$.pipe(filter((m) => !dropDelta(m))),
  });
  gateway.remoteCanvasDelta$.subscribe((m) => received.push(m));

  TestBed.configureTestingModule({
    providers: [
      provideZonelessChangeDetection(),
      provideHttpClient(withInterceptors([alServidorReal])),
      { provide: COLLABORATION_GATEWAY, useValue: visto },
      {
        provide: EditorCommandService,
        useFactory: () => {
          const state = inject(EditorStateService);
          const apply = (model: ModeloUML, layout: DiagramLayout, version: number) => {
            state.setSnapshot(model, layout);
            state.setVersion(version);
          };
          return {
            applyCanvasContent: apply,
            applyCanvasSnapshot: (dto: LienzoDetailDto) =>
              apply(dto.model, dto.visualLayout, dto.version),
          };
        },
      },
      {
        provide: UmlGraphService,
        useValue: { isDraggingLocally: false, nodeMoved$: new Subject() },
      },
      { provide: RemoteNodeDragService, useValue: { clearAll: () => undefined } },
    ],
  });
  const state = TestBed.inject(EditorStateService);
  const api = TestBed.inject(UmlApiService);
  TestBed.inject(RemoteCanvasSyncService);

  const inicial = await firstValueFrom(api.getCanvas(c.canvasId));
  state.canvasId.set(c.canvasId);
  state.setSnapshot(inicial.model, inicial.visualLayout);
  state.setVersion(inicial.version);
  const getsAlCargar = gets;

  gateway.connect(c.canvasId);
  await waitFor(() => gateway.connectionState() === 'open', 10_000, 'canal abierto');
  const beto: Beto = { gateway, state, api, received, resyncs: () => gets - getsAlCargar };
  return beto;
}

/** El estado que tendría Beto si bajara el lienzo entero ahora mismo. */
async function delServidor(beto: Beto): Promise<LienzoDetailDto> {
  return firstValueFrom(beto.api.getCanvas(backend().canvasId));
}

describe('Sincronización por deltas en navegador real (Nivel B)', () => {
  let beto: Beto | null = null;

  beforeAll(loadHarnessConfig);

  afterEach(async () => {
    beto?.gateway.disconnect();
    beto = null;
    await resetHarness();
  });

  it('los cambios de Ana llegan a Beto como deltas encadenados y su estado converge, sin resync', async () => {
    backend();
    const b = (beto = await montarBeto());
    const idA = crypto.randomUUID();
    const idB = crypto.randomUUID();
    const base = b.state.version();

    await nuevaClase(idA, 'Cliente', 60);
    await nuevaClase(idB, 'Pedido', 320);
    await ana('MOVE_ELEMENT', { elementId: idA, x: 80, y: 95 });
    await ana('ADD_ATTRIBUTE', {
      classId: idA,
      id: crypto.randomUUID(),
      name: 'nombre',
      type: 'String',
    });
    await ana('CREATE_RELATION', {
      relationId: crypto.randomUUID(),
      type: 'ASSOCIATION',
      sourceClassId: idA,
      targetClassId: idB,
      sourceMultiplicity: '1',
      targetMultiplicity: '0..*',
    });
    const final = await ana('DELETE_ELEMENTS', { classIds: [idB] });
    await waitFor(() => b.state.version() === final, 10_000, `Beto en la versión ${final}`);

    // Llegaron como deltas (no como lienzo entero), uno por versión y encadenados.
    expect(b.received.map((m) => [m.fromVersion, m.toVersion])).toEqual(
      [0, 1, 2, 3, 4, 5].map((i) => [base + i, base + i + 1]),
    );
    expect(b.received.every((m) => !('canvas' in m))).toBeTrue();
    // Sin huecos no hubo que resincronizar: ninguna descarga del lienzo desde que Beto lo cargó.
    expect(b.resyncs()).toBe(0);
    // Y el estado resultante es EXACTAMENTE el del servidor.
    const servidor = await delServidor(b);
    expect(b.state.model()).toEqual(servidor.model);
    expect(b.state.layout()).toEqual(servidor.visualLayout);
  }, 60_000);

  it('un hueco (un delta que no llega) fuerza un resync y Beto converge igualmente', async () => {
    backend();
    const idA = crypto.randomUUID();
    const idB = crypto.randomUUID();
    const idC = crypto.randomUUID();
    let perdido = 0;
    // Se pierde el delta del SEGUNDO comando de Ana; los demás llegan de verdad por el WebSocket.
    const b = (beto = await montarBeto((m) => {
      const esElSegundo = m.delta.model?.classes?.upsert?.some((c) => c.id === idB) === true;
      if (esElSegundo) perdido++;
      return esElSegundo;
    }));
    const base = b.state.version();

    await nuevaClase(idA, 'A', 60);
    await nuevaClase(idB, 'B', 320); // este delta se pierde
    const final = await nuevaClase(idC, 'C', 580); // llega con fromVersion = base + 2 ≠ base + 1
    await waitFor(() => b.state.version() === final, 10_000, `Beto en la versión ${final}`);

    expect(perdido).toBe(1);
    expect(b.received.length).toBe(3); // el gateway sí los recibió todos
    expect(b.resyncs()).toBeGreaterThanOrEqual(1); // el hueco disparó al menos una descarga completa
    expect(final).toBe(base + 3);
    const servidor = await delServidor(b);
    expect(b.state.version()).toBe(final);
    expect(b.state.model()).toEqual(servidor.model);
    expect(b.state.layout()).toEqual(servidor.visualLayout);
  }, 60_000);

  it('un corte de red real: lo que Ana cambió mientras Beto estaba caído se recupera al reconectar', async () => {
    backend();
    const b = (beto = await montarBeto());
    const idA = crypto.randomUUID();
    const idB = crypto.randomUUID();
    await nuevaClase(idA, 'Antes del corte', 60);
    await waitFor(() => b.received.length === 1, 10_000, 'primer delta');

    await admin('/cut');
    await waitFor(() => b.gateway.connectionState() === 'reconnecting', 5_000, 'reconnecting');
    // Ana edita por HTTP directo al servidor (no pasa por el proxy cortado): Beto no se entera.
    await ana('MOVE_ELEMENT', { elementId: idA, x: 200, y: 200 });
    const final = await nuevaClase(idB, 'Durante el corte', 320);
    expect(b.state.version()).toBeLessThan(final);

    await admin('/restore');
    await waitFor(() => b.state.version() === final, 30_000, `Beto en la versión ${final}`);

    const servidor = await delServidor(b);
    expect(b.state.model()).toEqual(servidor.model);
    expect(b.state.layout()).toEqual(servidor.visualLayout);
    expect(b.state.layout().nodes[idA]).toEqual(jasmine.objectContaining({ x: 200, y: 200 }));
  }, 60_000);
});
