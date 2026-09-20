/**
 * Pruebas de integración del subsistema de locks en un navegador REAL contra un
 * servidor REAL con proxy cortable (Nivel B, Paso 5e).
 *
 * Cubre:
 * 1. Contención de un lock entre dos peers (adquisición, denegación por 'held', y adquisición tras liberación).
 * 2. Renovación del lock (heartbeat/renovación por el mismo titular refresca el TTL).
 * 3. Expiración/liberación cuando el titular cae por corte de red real (proxy /cut -> /restore).
 * 4. Verificación de la carrera de arrastre simultáneo (límite conocido documentado en ADR-0003).
 */

import { signal } from '@angular/core';
import { AuthService } from '../../../core/auth';
import {
  LockAcquiredMessage,
  LockDeniedMessage,
  LockReleasedMessage,
  NodeDragMessage,
} from '../domain/models/collaboration.models';
import { WebSocketCollaborationGateway } from './collaboration-gateway.service';
import {
  admin,
  backend,
  loadHarnessConfig,
  resetHarness,
  sleep,
  waitFor,
} from './collaboration-integration.harness.spec';

function createGateway(token: string, name: string): WebSocketCollaborationGateway {
  const c = backend();
  const auth = {
    currentUser: () => ({ fullName: name }),
    accessToken: signal<string | null>(token),
    refreshSession: () => undefined,
  } as unknown as AuthService;
  return new WebSocketCollaborationGateway(auth, c.wsBase);
}

describe('Locks de colaboración en navegador real con servidor real (Nivel B, Paso 5e)', () => {
  beforeAll(async () => {
    await loadHarnessConfig();
  });

  beforeEach(async () => {
    await resetHarness();
  });

  it('1. Contención: Peer 1 adquiere, Peer 2 es denegado con reason "held", y Peer 2 adquiere tras liberación', async () => {
    const c = backend();
    const ana = createGateway(c.tokens.owner, 'Ana');
    const beto = createGateway(c.tokens.peer, 'Beto');

    const anaAcquired: LockAcquiredMessage[] = [];
    const betoAcquired: LockAcquiredMessage[] = [];
    const betoDenied: LockDeniedMessage[] = [];
    const betoReleased: LockReleasedMessage[] = [];

    ana.lockAcquired$.subscribe((m) => anaAcquired.push(m));
    beto.lockAcquired$.subscribe((m) => betoAcquired.push(m));
    beto.lockDenied$.subscribe((m) => betoDenied.push(m));
    beto.lockReleased$.subscribe((m) => betoReleased.push(m));

    ana.connect(c.canvasId);
    beto.connect(c.canvasId);

    await waitFor(
      () => ana.connectionState() === 'open' && beto.connectionState() === 'open',
      5000,
      'Ana y Beto conectados',
    );

    // Ana adquiere class-1
    ana.sendLockAcquire('class-1');

    await waitFor(
      () =>
        anaAcquired.some((m) => m.elementId === 'class-1') &&
        betoAcquired.some((m) => m.elementId === 'class-1'),
      5000,
      'lock_acquired recibido por ambos peers',
    );

    const anaLock = anaAcquired.find((m) => m.elementId === 'class-1')!;
    expect(anaLock.holder.sessionId).toBe(ana.peerId!);
    expect(anaLock.ttlMs).toBe(15000);

    // Beto intenta adquirir el mismo elemento
    beto.sendLockAcquire('class-1');

    await waitFor(
      () => betoDenied.some((m) => m.elementId === 'class-1'),
      5000,
      'lock_denied recibido por Beto',
    );

    const denial = betoDenied.find((m) => m.elementId === 'class-1')!;
    expect(denial.reason).toBe('held');
    expect(denial.holder?.sessionId).toBe(ana.peerId!);

    // Ana libera el lock
    ana.sendLockRelease('class-1');

    await waitFor(
      () => betoReleased.some((m) => m.elementId === 'class-1'),
      5000,
      'lock_released recibido por Beto',
    );

    // Ahora Beto puede adquirir class-1
    beto.sendLockAcquire('class-1');

    await waitFor(
      () =>
        betoAcquired.some((m) => m.elementId === 'class-1' && m.holder.sessionId === beto.peerId),
      5000,
      'lock_acquired recibido por Beto como nuevo titular',
    );

    const betoLock = betoAcquired.find(
      (m) => m.elementId === 'class-1' && m.holder.sessionId === beto.peerId,
    )!;
    expect(betoLock.holder.sessionId).toBe(beto.peerId!);

    ana.disconnect();
    beto.disconnect();
  });

  it('2. Renovación: titular renueva lock_acquire refrescando TTL sin ser denegado', async () => {
    const c = backend();
    const ana = createGateway(c.tokens.owner, 'Ana');
    const beto = createGateway(c.tokens.peer, 'Beto');

    const anaAcquired: LockAcquiredMessage[] = [];
    const betoDenied: LockDeniedMessage[] = [];

    ana.lockAcquired$.subscribe((m) => anaAcquired.push(m));
    beto.lockDenied$.subscribe((m) => betoDenied.push(m));

    ana.connect(c.canvasId);
    beto.connect(c.canvasId);

    await waitFor(
      () => ana.connectionState() === 'open' && beto.connectionState() === 'open',
      5000,
      'Ana y Beto conectados',
    );

    // Adquisición inicial
    ana.sendLockAcquire('class-renew');
    await waitFor(
      () => anaAcquired.some((m) => m.elementId === 'class-renew'),
      5000,
      'Primer lock_acquired recibido por Ana',
    );
    expect(anaAcquired.length).toBe(1);

    await sleep(200);

    // Renovación (heartbeat) por el mismo titular
    ana.sendLockAcquire('class-renew');
    await waitFor(
      () => anaAcquired.filter((m) => m.elementId === 'class-renew').length >= 2,
      5000,
      'Segundo lock_acquired (renovación) recibido',
    );

    expect(anaAcquired[1].holder.sessionId).toBe(ana.peerId!);
    expect(anaAcquired[1].ttlMs).toBe(15000);

    // Beto sigue sin poder tomarlo
    beto.sendLockAcquire('class-renew');
    await waitFor(
      () => betoDenied.some((m) => m.elementId === 'class-renew'),
      5000,
      'Beto denegado mientras el lock está renovado',
    );
    expect(betoDenied[0].reason).toBe('held');

    ana.disconnect();
    beto.disconnect();
  });

  it('3. Expiración y liberación: cuando el titular cae por corte real del proxy, el lock se libera en el servidor', async () => {
    const c = backend();
    const ana = createGateway(c.tokens.owner, 'Ana');
    const beto = createGateway(c.tokens.peer, 'Beto');

    const anaAcquired: LockAcquiredMessage[] = [];
    const betoAcquired: LockAcquiredMessage[] = [];

    ana.lockAcquired$.subscribe((m) => anaAcquired.push(m));
    beto.lockAcquired$.subscribe((m) => betoAcquired.push(m));

    ana.connect(c.canvasId);
    beto.connect(c.canvasId);

    await waitFor(
      () => ana.connectionState() === 'open' && beto.connectionState() === 'open',
      5000,
      'Conexión inicial',
    );

    // Ana adquiere el lock
    ana.sendLockAcquire('class-proxy-cut');
    await waitFor(
      () => anaAcquired.some((m) => m.elementId === 'class-proxy-cut'),
      5000,
      'Ana tiene el lock',
    );

    // Cortamos la red real a través del proxy TCP
    await admin('/cut');

    await waitFor(
      () => ana.connectionState() === 'reconnecting' || ana.connectionState() === 'failed',
      5000,
      'Ana detecta la caída TCP 1006',
    );

    // Restauramos el paso de red
    await admin('/restore');

    // Desconectamos Ana definitivamente para simular que no vuelve
    ana.disconnect();

    // Esperamos a que Beto se reconecte
    await waitFor(
      () => beto.connectionState() === 'open',
      8000,
      'Beto reconectado tras reponer el proxy',
    );

    // Al haber muerto la sesión de Ana en el corte, Beto solicita el lock y el servidor se lo concede
    beto.sendLockAcquire('class-proxy-cut');

    await waitFor(
      () =>
        betoAcquired.some(
          (m) => m.elementId === 'class-proxy-cut' && m.holder.sessionId === beto.peerId,
        ),
      5000,
      'Beto adquiere el lock liberado tras la caída del titular anterior',
    );

    beto.disconnect();
  });

  it('4. Carrera de arrastre simultáneo: límite conocido verificado explícitamente entre dos peers', async () => {
    const c = backend();
    const ana = createGateway(c.tokens.owner, 'Ana');
    const beto = createGateway(c.tokens.peer, 'Beto');

    const anaAcquired: LockAcquiredMessage[] = [];
    const anaDenied: LockDeniedMessage[] = [];
    const betoAcquired: LockAcquiredMessage[] = [];
    const betoDenied: LockDeniedMessage[] = [];
    const dragsReceivedByBeto: NodeDragMessage[] = [];
    const dragsReceivedByAna: NodeDragMessage[] = [];

    ana.lockAcquired$.subscribe((m) => anaAcquired.push(m));
    ana.lockDenied$.subscribe((m) => anaDenied.push(m));
    beto.lockAcquired$.subscribe((m) => betoAcquired.push(m));
    beto.lockDenied$.subscribe((m) => betoDenied.push(m));

    ana.remoteNodeDrag$.subscribe((e) =>
      dragsReceivedByAna.push({ type: 'node_drag', nodeId: e.nodeId, x: e.x, y: e.y }),
    );
    beto.remoteNodeDrag$.subscribe((e) =>
      dragsReceivedByBeto.push({ type: 'node_drag', nodeId: e.nodeId, x: e.x, y: e.y }),
    );

    ana.connect(c.canvasId);
    beto.connect(c.canvasId);

    await waitFor(
      () => ana.connectionState() === 'open' && beto.connectionState() === 'open',
      5000,
      'Ambos peers conectados',
    );

    // Carrera simultánea: ambos emiten arrastre optimista y solicitan el lock casi al mismo tiempo
    ana.sendNodeDragPosition('class-race', 100, 100);
    ana.sendLockAcquire('class-race');

    beto.sendNodeDragPosition('class-race', 200, 200);
    beto.sendLockAcquire('class-race');

    // Esperamos resolución del servidor para ambos peers
    await waitFor(
      () =>
        (anaAcquired.some((m) => m.elementId === 'class-race') ||
          anaDenied.some((m) => m.elementId === 'class-race')) &&
        (betoAcquired.some((m) => m.elementId === 'class-race') ||
          betoDenied.some((m) => m.elementId === 'class-race')),
      5000,
      'Servidor resolvió la carrera entre Ana y Beto',
    );

    // Exactamente uno gana y el otro recibe lock_denied (resolución determinista del servidor)
    const anaGanador = anaAcquired.some(
      (m) => m.elementId === 'class-race' && m.holder.sessionId === ana.peerId,
    );
    const betoGanador = betoAcquired.some(
      (m) => m.elementId === 'class-race' && m.holder.sessionId === beto.peerId,
    );

    expect(anaGanador !== betoGanador)
      .withContext('Exactamente uno de los dos peers debe ganar el lock')
      .toBeTrue();

    if (anaGanador) {
      expect(
        betoDenied.some((m) => m.elementId === 'class-race' && m.reason === 'held'),
      ).toBeTrue();
    } else {
      expect(anaDenied.some((m) => m.elementId === 'class-race' && m.reason === 'held')).toBeTrue();
    }

    // Comprobación del límite conocido: ambos eventos de arrastre viajaron por la red
    // en la ventana de carrera antes de que la denegación fuera procesada por el perdedor.
    const algunArrastreCruzado =
      dragsReceivedByBeto.some((d) => d.nodeId === 'class-race') ||
      dragsReceivedByAna.some((d) => d.nodeId === 'class-race');
    expect(algunArrastreCruzado)
      .withContext('Los eventos optimistas viajaron durante la ventana de carrera')
      .toBeTrue();

    ana.disconnect();
    beto.disconnect();
  });
});
