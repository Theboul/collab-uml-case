/**
 * Integración del canal de colaboración en un navegador REAL contra un servidor REAL (Nivel B).
 *
 * Necesita el arnés `scripts/collab-e2e/run.py` (uvicorn + proxy que se puede cortar). Sin él,
 * todos los tests quedan pendientes y `ng test` sigue verde. Ver scripts/collab-e2e/README.md.
 */

import { WritableSignal, signal } from '@angular/core';
import { defer, of } from 'rxjs';
import { AuthService } from '../../../core/auth';
import {
  CollaborationConnectionState,
  WebSocketCollaborationGateway,
} from './collaboration-gateway.service';

const ADMIN = 'http://127.0.0.1:8941';

interface HarnessConfig {
  wsBase: string;
  httpBase: string;
  canvasId: string;
  collaboratorUserId: string;
  tokens: { owner: string; outsider: string; collaborator: string; expiredOwner: string };
}

let config: HarnessConfig | null = null;

function backend(): HarnessConfig {
  if (!config) {
    pending('arnés de integración no disponible (ver scripts/collab-e2e/README.md)');
  }
  return config as HarnessConfig;
}

async function admin(path: string): Promise<void> {
  await fetch(`${ADMIN}${path}`);
}

interface RawResult {
  opened: boolean;
  protocol: string;
  messages: { type?: string }[];
  closeCode: number | null;
}

/** Abre un WebSocket del navegador y espera al cierre (o al primer mensaje si `until` lo indica). */
function connectRaw(
  url: string,
  protocols: string[] | undefined,
  until: 'close' | 'first-message',
  timeoutMs = 5_000,
): Promise<RawResult> {
  return new Promise((resolve) => {
    const result: RawResult = { opened: false, protocol: '', messages: [], closeCode: null };
    const socket = new WebSocket(url, protocols);
    const timer = setTimeout(() => finish(), timeoutMs);
    function finish(): void {
      clearTimeout(timer);
      socket.close();
      resolve(result);
    }
    socket.onopen = () => {
      result.opened = true;
      result.protocol = socket.protocol;
    };
    socket.onmessage = (event) => {
      result.messages.push(JSON.parse(event.data as string) as { type?: string });
      if (until === 'first-message') finish();
    };
    socket.onclose = (event) => {
      result.closeCode = event.code;
      finish();
    };
  });
}

interface ProxyStats {
  accepted: number;
  refused: number;
  open: number;
  cut: boolean;
}

async function stats(): Promise<ProxyStats> {
  return (await (await fetch(`${ADMIN}/stats`)).json()) as ProxyStats;
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

async function waitFor(condition: () => boolean, timeoutMs: number, what: string): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (!condition()) {
    if (Date.now() > deadline) throw new Error(`Tiempo agotado esperando: ${what}`);
    await sleep(50);
  }
}

/** Gateway REAL apuntando al proxy, con un AuthService de mentira (el refresco real es del Nivel C). */
function realGateway(initialToken: string, tokenAfterRefresh?: string) {
  const token: WritableSignal<string | null> = signal(initialToken);
  const spy = { refreshCalls: 0 };
  const auth = {
    currentUser: () => ({ fullName: 'Integración' }),
    accessToken: token,
    refreshSession: () => {
      spy.refreshCalls++;
      return defer(() => {
        if (tokenAfterRefresh) token.set(tokenAfterRefresh);
        return of({});
      });
    },
  } as unknown as AuthService;
  const gateway = new WebSocketCollaborationGateway(auth, (config as HarnessConfig).wsBase);
  const state = (): CollaborationConnectionState => gateway.connectionState();
  const untilState = (expected: CollaborationConnectionState, ms: number) =>
    waitFor(() => state() === expected, ms, `estado '${expected}' (actual: '${state()}')`);
  return { gateway, spy, state, untilState };
}

describe('Canal de colaboración en navegador real (Nivel B)', () => {
  beforeAll(async () => {
    try {
      const res = await fetch(`${ADMIN}/config`);
      config = res.ok ? ((await res.json()) as HarnessConfig) : null;
    } catch {
      config = null;
    }
  });

  afterEach(async () => {
    if (config) {
      await admin('/restore');
      await admin('/reset');
    }
  });

  describe('handshake y códigos de cierre que el navegador realmente ve', () => {
    const url = (c: HarnessConfig) => `${c.wsBase}/ws/canvas/${c.canvasId}/collaboration`;

    it('acepta al dueño, negocia el subprotocolo bearer y envía connected', async () => {
      const c = backend();

      const r = await connectRaw(url(c), ['bearer', c.tokens.owner], 'first-message');

      expect(r.opened).toBe(true);
      expect(r.protocol).toBe('bearer');
      expect(r.messages[0]?.type).toBe('connected');
    });

    it('un usuario sin acceso: acepta y cierra con 4403 (sin permiso)', async () => {
      const c = backend();

      const r = await connectRaw(url(c), ['bearer', c.tokens.outsider], 'close');

      expect(r.opened).toBe(true); // se acepta: por eso el navegador puede leer el código
      expect(r.protocol).toBe('bearer');
      expect(r.messages).toEqual([]);
      expect(r.closeCode).toBe(4403);
    });

    it('sin token: cierra con 4403', async () => {
      const c = backend();

      const r = await connectRaw(url(c), undefined, 'close');

      expect(r.opened).toBe(true);
      expect(r.closeCode).toBe(4403);
    });

    it('token vencido: cierra con 4401 (se puede renovar y reintentar)', async () => {
      const c = backend();

      const r = await connectRaw(url(c), ['bearer', c.tokens.expiredOwner], 'close');

      expect(r.opened).toBe(true);
      expect(r.closeCode).toBe(4401);
    });

    it('token basura: cierra con 4401', async () => {
      const c = backend();

      const r = await connectRaw(url(c), ['bearer', 'no-es-un-jwt'], 'close');

      expect(r.closeCode).toBe(4401);
    });

    it('el token en la query string no autentica: cierra con 4403', async () => {
      const c = backend();

      const r = await connectRaw(`${url(c)}?token=${c.tokens.owner}`, undefined, 'close');

      expect(r.closeCode).toBe(4403);
    });
  });

  describe('gateway real: caídas, permiso y token vencido', () => {
    let gateways: WebSocketCollaborationGateway[] = [];
    const track = <T extends { gateway: WebSocketCollaborationGateway }>(g: T): T => {
      gateways.push(g.gateway);
      return g;
    };

    afterEach(() => {
      gateways.forEach((g) => g.disconnect());
      gateways = [];
    });

    it('escenas 1-3: cortar la red, esperar y reponerla → reconecta y pide resincronizar', async () => {
      const c = backend();
      const { gateway, untilState } = track(realGateway(c.tokens.owner));
      let reconectado = 0;
      gateway.reconnected$.subscribe(() => reconectado++);
      gateway.connect(c.canvasId);
      await untilState('open', 10_000);
      expect(reconectado).toBe(0);

      await admin('/cut'); // corte real: se abortan los TCP y se rechazan los nuevos
      await untilState('reconnecting', 5_000);
      await sleep(3_500); // esperar: pasan varios reintentos con backoff real (1 s, 2 s...)
      const durante = await stats();
      expect(durante.refused).toBeGreaterThanOrEqual(1); // hubo intentos rechazados durante el corte
      expect(gateway.connectionState()).toBe('reconnecting');

      await admin('/restore');
      await untilState('open', 20_000);
      expect(reconectado).toBe(1);
    }, 60_000);

    it('escena 4: se retira el acceso; la sesión abierta sigue, pero al reconectar recibe 4403 y no reintenta', async () => {
      const c = backend();
      const { gateway, state, untilState } = track(realGateway(c.tokens.collaborator));
      gateway.connect(c.canvasId);
      await untilState('open', 10_000);

      await admin('/revoke'); // se borra la fila del Colaborador
      await sleep(1_000);
      expect(state()).toBe('open'); // no hay revocación en caliente: el rol solo se mira al conectar

      await admin('/cut');
      await sleep(300);
      await admin('/restore');
      await untilState('denied', 20_000);

      const intentos = (await stats()).accepted;
      await sleep(3_000);
      expect((await stats()).accepted).toBe(intentos); // sin bucle de reintentos
    }, 60_000);

    it('un usuario sin acceso queda en denied desde el primer intento y no reintenta', async () => {
      const c = backend();
      const { gateway, untilState } = track(realGateway(c.tokens.outsider));

      gateway.connect(c.canvasId);
      await untilState('denied', 10_000);

      const intentos = (await stats()).accepted;
      await sleep(3_000);
      expect((await stats()).accepted).toBe(intentos);
    }, 30_000);

    it('escena 5: token vencido → 4401, renueva una vez, reconecta y pide resincronizar', async () => {
      const c = backend();
      const { gateway, spy, untilState } = track(
        realGateway(c.tokens.expiredOwner, c.tokens.owner),
      );
      let reconectado = 0;
      gateway.reconnected$.subscribe(() => reconectado++);

      gateway.connect(c.canvasId);
      await untilState('open', 10_000);

      expect(spy.refreshCalls).toBe(1);
      expect(reconectado).toBe(1);
      expect((await stats()).accepted).toBe(2); // el intento con el token vencido + el renovado
    }, 30_000);

    it('token vencido y la renovación tampoco sirve → failed, sin bucle', async () => {
      const c = backend();
      const { gateway, spy, untilState } = track(
        realGateway(c.tokens.expiredOwner, c.tokens.expiredOwner),
      );

      gateway.connect(c.canvasId);
      await untilState('failed', 10_000);

      expect(spy.refreshCalls).toBe(1);
      const intentos = (await stats()).accepted;
      await sleep(3_000);
      expect((await stats()).accepted).toBe(intentos);
    }, 30_000);

    it('disconnect() durante un corte no reconecta al reponer la red', async () => {
      const c = backend();
      const { gateway, untilState } = track(realGateway(c.tokens.owner));
      gateway.connect(c.canvasId);
      await untilState('open', 10_000);
      await admin('/cut');
      await untilState('reconnecting', 5_000);

      gateway.disconnect();
      const intentos = (await stats()).accepted;
      await admin('/restore');
      await sleep(3_000);

      expect((await stats()).accepted).toBe(intentos);
      expect(gateway.connectionState()).toBe('idle');
    }, 30_000);
  });
});
