import { WritableSignal, signal } from '@angular/core';
import { Observable, Subject, defer, of, throwError } from 'rxjs';
import { AuthService } from '../../../core/auth';
import { WebSocketCollaborationGateway } from './collaboration-gateway.service';

/** WebSocket controlable a mano: el test decide cuándo el servidor establece o cierra. */
class FakeWebSocket {
  static readonly OPEN = 1;
  static instances: FakeWebSocket[] = [];

  readyState = 0;
  onopen: ((event: unknown) => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;
  readonly sent: string[] = [];
  closedByClient = false;

  constructor(
    readonly url: string,
    readonly protocols?: string | string[],
  ) {
    FakeWebSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.closedByClient = true;
    this.readyState = 3;
  }

  serverSends(message: unknown): void {
    this.onmessage?.({ data: JSON.stringify(message) });
  }

  /** El servidor acepta el handshake: el navegador dispara `onopen`, pero aún puede cerrar. */
  serverAccepts(): void {
    this.readyState = 1;
    this.onopen?.({});
  }

  /** El servidor acepta y envía `connected`: la Sesión ya está en la Sala. */
  serverEstablishes(peerId = 'peer-1'): void {
    this.serverAccepts();
    this.serverSends({ type: 'connected', peerId });
  }

  serverCloses(code: number): void {
    this.readyState = 3;
    this.onclose?.({ code });
  }
}

describe('WebSocketCollaborationGateway (reconexión)', () => {
  let originalWebSocket: typeof WebSocket;
  let token: WritableSignal<string | null>;
  let refreshCalls: number;
  let refresh$: Observable<unknown>;
  let gateway: WebSocketCollaborationGateway;

  const sockets = () => FakeWebSocket.instances;
  const last = () => sockets()[sockets().length - 1];
  const state = () => gateway.connectionState();
  const global = globalThis as unknown as { WebSocket: unknown };

  beforeEach(() => {
    jasmine.clock().install();
    spyOn(Math, 'random').and.returnValue(1); // sin recorte por jitter: retardos 1000, 2000, 4000...
    originalWebSocket = globalThis.WebSocket;
    FakeWebSocket.instances = [];
    global.WebSocket = FakeWebSocket;

    token = signal<string | null>('token-viejo');
    refreshCalls = 0;
    refresh$ = defer(() => {
      token.set('token-nuevo');
      return of({});
    });
    const auth = {
      currentUser: () => ({ fullName: 'Ana' }),
      accessToken: token,
      refreshSession: () => {
        refreshCalls++;
        return refresh$;
      },
    } as unknown as AuthService;
    gateway = new WebSocketCollaborationGateway(auth, 'ws://prueba');
  });

  afterEach(() => {
    gateway.disconnect();
    jasmine.clock().uninstall();
    global.WebSocket = originalWebSocket;
  });

  it('arma la URL con el lienzo y el nombre y manda el token como subprotocolo', () => {
    gateway.connect('c1');

    expect(last().url).toBe('ws://prueba/ws/canvas/c1/collaboration?display_name=Ana');
    expect(last().protocols).toEqual(['bearer', 'token-viejo']);
  });

  it('no se da por establecido hasta recibir connected (no basta con abrir el socket)', () => {
    gateway.connect('c1');
    expect(state()).toBe('connecting');

    last().serverAccepts(); // el servidor aceptó, pero todavía puede cerrar con 4401/4403
    expect(state()).toBe('connecting');

    last().serverEstablishes('p1');
    expect(state()).toBe('open');
    expect(gateway.peerId).toBe('p1');
  });

  it('solo envía mensajes cuando el socket está abierto', () => {
    gateway.connect('c1');
    gateway.sendCursorPosition(1, 2);
    expect(last().sent).toEqual([]);

    last().serverEstablishes();
    gateway.sendCursorPosition(1, 2);
    expect(last().sent.length).toBe(1);
  });

  it('entrega los mensajes remotos como antes de la reconexión', () => {
    const cursores: unknown[] = [];
    const deltas: unknown[] = [];
    gateway.remoteCursor$.subscribe((c) => cursores.push(c));
    gateway.remoteCanvasDelta$.subscribe((d) => deltas.push(d));
    gateway.connect('c1');
    last().serverEstablishes();

    last().serverSends({
      from: 'p2',
      fromDisplayName: 'Bea',
      payload: { type: 'cursor', x: 1, y: 2 },
    });
    const delta = { type: 'canvas_delta', fromVersion: 6, toVersion: 7, delta: { layout: {} } };
    last().serverSends({ from: 'p2', payload: delta });

    expect(cursores).toEqual([{ peerId: 'p2', displayName: 'Bea', x: 1, y: 2 }]);
    expect(deltas).toEqual([delta]);
  });

  describe('canvas_delta', () => {
    let deltas: unknown[];

    beforeEach(() => {
      deltas = [];
      gateway.remoteCanvasDelta$.subscribe((d) => deltas.push(d));
      gateway.connect('c1');
      last().serverEstablishes();
    });

    it('un delta malformado se descarta con un aviso y no llega a quien aplica', () => {
      const aviso = spyOn(console, 'warn');

      last().serverSends({ from: 'p2', payload: { type: 'canvas_delta', fromVersion: 1 } });
      last().serverSends({
        from: 'p2',
        payload: { type: 'canvas_delta', fromVersion: '1', toVersion: 2, delta: {} },
      });

      expect(deltas).toEqual([]);
      expect(aviso).toHaveBeenCalledTimes(2);
    });

    it('el mensaje canvas_update ya no existe: se ignora sin emitir nada', () => {
      last().serverSends({
        from: 'p2',
        payload: { type: 'canvas_update', canvas: { version: 7 } },
      });

      expect(deltas).toEqual([]);
    });
  });

  describe('caídas de red', () => {
    it('una caída anormal pasa a reconnecting y reabre tras el retardo', () => {
      gateway.connect('c1');
      last().serverEstablishes();

      last().serverCloses(1006);

      expect(state()).toBe('reconnecting');
      expect(sockets().length).toBe(1);
      jasmine.clock().tick(999);
      expect(sockets().length).toBe(1);
      jasmine.clock().tick(1);
      expect(sockets().length).toBe(2);
      last().serverEstablishes();
      expect(state()).toBe('open');
    });

    it('emite reconnected$ al restablecerse tras una caída, no en la primera conexión', () => {
      let emisiones = 0;
      gateway.reconnected$.subscribe(() => emisiones++);

      gateway.connect('c1');
      last().serverEstablishes();
      expect(emisiones).toBe(0);

      last().serverCloses(1006);
      jasmine.clock().tick(1000);
      last().serverEstablishes();

      expect(emisiones).toBe(1);
    });

    it('si la primera conexión falla y luego funciona, también emite reconnected$', () => {
      let emisiones = 0;
      gateway.reconnected$.subscribe(() => emisiones++);
      gateway.connect('c1');

      last().serverCloses(1006); // nunca llegó a establecerse
      jasmine.clock().tick(1000);
      last().serverEstablishes();

      expect(emisiones).toBe(1);
    });

    it('el retardo se duplica en cada fallo consecutivo', () => {
      gateway.connect('c1');

      for (const retardo of [1000, 2000, 4000, 8000]) {
        const antes = sockets().length;
        last().serverCloses(1006);
        jasmine.clock().tick(retardo - 1);
        expect(sockets().length).toBe(antes);
        jasmine.clock().tick(1);
        expect(sockets().length).toBe(antes + 1);
      }
    });

    it('agota los reintentos: tras 8 fallos pasa a failed y retry() reanuda desde cero', () => {
      gateway.connect('c1');

      for (const retardo of [1000, 2000, 4000, 8000, 16000, 30000, 30000, 30000]) {
        last().serverCloses(1006);
        jasmine.clock().tick(retardo);
      }
      expect(sockets().length).toBe(9); // el intento inicial + 8 reintentos

      last().serverCloses(1006);
      expect(state()).toBe('failed');
      jasmine.clock().tick(600_000);
      expect(sockets().length).toBe(9);

      gateway.retry();
      expect(state()).toBe('connecting');
      expect(sockets().length).toBe(10);
      last().serverCloses(1006);
      jasmine.clock().tick(1000); // el contador volvió a cero: el primer retardo es de nuevo 1 s
      expect(sockets().length).toBe(11);
    });

    it('retry() solo actúa desde failed', () => {
      gateway.connect('c1');
      last().serverEstablishes();

      gateway.retry();

      expect(sockets().length).toBe(1);
      expect(state()).toBe('open');
    });

    it('una conexión estable durante 10 s reinicia el contador de fallos', () => {
      gateway.connect('c1');
      for (const retardo of [1000, 2000, 4000]) {
        last().serverCloses(1006);
        jasmine.clock().tick(retardo);
      }
      last().serverEstablishes();
      jasmine.clock().tick(10_000); // estable

      last().serverCloses(1006);

      jasmine.clock().tick(999);
      expect(sockets().length).toBe(4);
      jasmine.clock().tick(1);
      expect(sockets().length).toBe(5); // volvió al retardo de 1 s
    });

    it('una conexión que cae antes de 10 s NO reinicia el contador', () => {
      gateway.connect('c1');
      for (const retardo of [1000, 2000]) {
        last().serverCloses(1006);
        jasmine.clock().tick(retardo);
      }
      last().serverEstablishes();
      jasmine.clock().tick(9_999); // todavía no es estable

      last().serverCloses(1006);

      jasmine.clock().tick(3_999);
      expect(sockets().length).toBe(3);
      jasmine.clock().tick(1);
      expect(sockets().length).toBe(4); // el retardo sigue creciendo: 4 s
    });

    it('connect() al mismo lienzo mientras reconecta no reinicia el ciclo', () => {
      gateway.connect('c1');
      last().serverCloses(1006);

      gateway.connect('c1');

      expect(sockets().length).toBe(1);
      jasmine.clock().tick(1000);
      expect(sockets().length).toBe(2);
    });

    it('ignora los eventos de un socket que ya fue reemplazado', () => {
      gateway.connect('c1');
      const viejo = last();
      gateway.connect('c2');

      viejo.serverCloses(1006);

      expect(state()).toBe('connecting');
      jasmine.clock().tick(600_000);
      expect(sockets().length).toBe(2);
    });
  });

  describe('permiso (4403)', () => {
    it('pasa a denied y no vuelve a intentar', () => {
      gateway.connect('c1');

      last().serverCloses(4403);

      expect(state()).toBe('denied');
      jasmine.clock().tick(600_000);
      expect(sockets().length).toBe(1);
      expect(refreshCalls).toBe(0);
    });
  });

  describe('token vencido (4401)', () => {
    it('renueva el token una vez y reconecta con el token nuevo', () => {
      gateway.connect('c1');

      last().serverCloses(4401);

      expect(refreshCalls).toBe(1);
      expect(sockets().length).toBe(2);
      expect(last().protocols).toEqual(['bearer', 'token-nuevo']);
    });

    it('un segundo 4401 tras renovar se rinde (failed) sin más renovaciones', () => {
      gateway.connect('c1');
      last().serverCloses(4401);

      last().serverCloses(4401);

      expect(state()).toBe('failed');
      expect(refreshCalls).toBe(1);
      jasmine.clock().tick(600_000);
      expect(sockets().length).toBe(2);
    });

    it('si la renovación del token falla, pasa a failed', () => {
      refresh$ = throwError(() => new Error('refresh rechazado'));
      gateway.connect('c1');

      last().serverCloses(4401);

      expect(state()).toBe('failed');
      expect(sockets().length).toBe(1);
    });

    it('un disconnect() mientras se renueva el token no abre un socket después', () => {
      const pendiente = new Subject<unknown>();
      refresh$ = pendiente;
      gateway.connect('c1');
      last().serverCloses(4401);
      expect(state()).toBe('reconnecting');

      gateway.disconnect();
      pendiente.next({});

      expect(sockets().length).toBe(1);
      expect(state()).toBe('idle');
    });
  });

  describe('cierre intencional', () => {
    it('disconnect() no reconecta, cierra el socket y limpia los temporizadores', () => {
      gateway.connect('c1');
      last().serverEstablishes();
      const socket = last();

      gateway.disconnect();
      socket.serverCloses(1006); // el navegador notifica el cierre después: se ignora

      expect(state()).toBe('idle');
      expect(socket.closedByClient).toBe(true);
      jasmine.clock().tick(600_000);
      expect(sockets().length).toBe(1);
    });

    it('disconnect() durante la espera de un reintento cancela ese reintento', () => {
      gateway.connect('c1');
      last().serverCloses(1006);

      gateway.disconnect();

      jasmine.clock().tick(600_000);
      expect(sockets().length).toBe(1);
    });
  });
});
