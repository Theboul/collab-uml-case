import { TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { Subject } from 'rxjs';
import { COLLABORATION_GATEWAY } from './collaboration-gateway.service';
import {
  LockAcquiredMessage,
  LockDeniedMessage,
  LockReleasedMessage,
  LocksSnapshotMessage,
} from '../domain/models/collaboration.models';
import { RemoteLocksService } from './remote-locks.service';
import { ToastService } from '../../../shared/ui/toast/toast.service';

describe('RemoteLocksService', () => {
  let service: RemoteLocksService;
  let toast: ToastService;

  let sendLockAcquireSpy: jasmine.Spy;
  let sendLockReleaseSpy: jasmine.Spy;

  let locksSnapshot$: Subject<LocksSnapshotMessage>;
  let lockAcquired$: Subject<LockAcquiredMessage>;
  let lockReleased$: Subject<LockReleasedMessage>;
  let lockDenied$: Subject<LockDeniedMessage>;
  let reconnected$: Subject<void>;
  let currentPeerId: string | null;

  beforeEach(() => {
    jasmine.clock().install();

    locksSnapshot$ = new Subject<LocksSnapshotMessage>();
    lockAcquired$ = new Subject<LockAcquiredMessage>();
    lockReleased$ = new Subject<LockReleasedMessage>();
    lockDenied$ = new Subject<LockDeniedMessage>();
    reconnected$ = new Subject<void>();
    currentPeerId = 'my-session-id';

    sendLockAcquireSpy = jasmine.createSpy('sendLockAcquire');
    sendLockReleaseSpy = jasmine.createSpy('sendLockRelease');

    const fakeGateway = {
      get peerId() {
        return currentPeerId;
      },
      sendLockAcquire: sendLockAcquireSpy,
      sendLockRelease: sendLockReleaseSpy,
      locksSnapshot$: locksSnapshot$.asObservable(),
      lockAcquired$: lockAcquired$.asObservable(),
      lockReleased$: lockReleased$.asObservable(),
      lockDenied$: lockDenied$.asObservable(),
      reconnected$: reconnected$.asObservable(),
    };

    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        RemoteLocksService,
        ToastService,
        { provide: COLLABORATION_GATEWAY, useValue: fakeGateway },
      ],
    });

    service = TestBed.inject(RemoteLocksService);
    toast = TestBed.inject(ToastService);
  });

  afterEach(() => {
    try {
      service?.reset();
    } finally {
      jasmine.clock().uninstall();
    }
  });

  it('adquiere el lock y envía lock_acquire al gateway', () => {
    service.acquireLock('class-1', 'Cliente', 'panel');

    expect(sendLockAcquireSpy).toHaveBeenCalledWith('class-1');
    expect(service.isHeldLocally('class-1')).toBeTrue();
  });

  it('renueva el lock cada 5 segundos mediante heartbeat enviando lock_acquire', () => {
    service.acquireLock('class-1', 'Cliente', 'panel');
    expect(sendLockAcquireSpy).toHaveBeenCalledTimes(1);

    jasmine.clock().tick(5000);
    expect(sendLockAcquireSpy).toHaveBeenCalledTimes(2);

    jasmine.clock().tick(5000);
    expect(sendLockAcquireSpy).toHaveBeenCalledTimes(3);
  });

  it('libera el lock por inactividad a los 60s con aviso toast', () => {
    service.acquireLock('class-1', 'Cliente', 'panel');
    expect(service.isHeldLocally('class-1')).toBeTrue();

    // Avanza 60 segundos de inactividad con reloj virtual controlable
    jasmine.clock().tick(60000);

    expect(sendLockReleaseSpy).toHaveBeenCalledWith('class-1');
    expect(service.isHeldLocally('class-1')).toBeFalse();

    const toasts = toast.toasts();
    expect(toasts.length).toBe(1);
    expect(toasts[0].text).toContain('liberaste Cliente por inactividad');

    // Comprobar que el heartbeat de 5s ya no sigue enviando renovaciones
    sendLockAcquireSpy.calls.reset();
    jasmine.clock().tick(10000);
    expect(sendLockAcquireSpy).not.toHaveBeenCalled();
  });

  it('reinicia el contador de inactividad de 60s si el usuario registra actividad', () => {
    service.acquireLock('class-1', 'Cliente', 'panel');

    // Pasan 50 segundos (aún no vence)
    jasmine.clock().tick(50000);
    expect(sendLockReleaseSpy).not.toHaveBeenCalled();

    // El usuario interactúa
    service.recordActivity();

    // Pasan 20 segundos más (70s en total desde el inicio, pero solo 20s desde la actividad)
    jasmine.clock().tick(20000);
    expect(sendLockReleaseSpy).not.toHaveBeenCalled();

    // Pasan otros 40 segundos (60s desde la actividad)
    jasmine.clock().tick(40000);
    expect(sendLockReleaseSpy).toHaveBeenCalledWith('class-1');
  });

  it('retoma edición desde cero tras inactividad al registrar nueva actividad', () => {
    service.acquireLock('class-1', 'Cliente', 'panel');
    jasmine.clock().tick(60000);
    expect(service.isHeldLocally('class-1')).toBeFalse();

    sendLockAcquireSpy.calls.reset();
    service.recordActivity('class-1', 'Cliente');

    expect(sendLockAcquireSpy).toHaveBeenCalledWith('class-1');
    expect(service.isHeldLocally('class-1')).toBeTrue();
  });

  it('libera el lock al cerrar el panel explícitamente', () => {
    service.acquireLock('class-1', 'Cliente', 'panel');
    service.onPanelClosed('class-1');

    expect(sendLockReleaseSpy).toHaveBeenCalledWith('class-1');
    expect(service.isHeldLocally('class-1')).toBeFalse();
  });

  it('libera el lock al terminar el arrastre si el panel no sigue abierto', () => {
    service.acquireLock('class-1', 'Cliente', 'drag');
    service.onNodeDragEnded('class-1', false);

    expect(sendLockReleaseSpy).toHaveBeenCalledWith('class-1');
  });

  it('NO libera el lock al terminar el arrastre si el panel sigue abierto para ese nodo', () => {
    service.acquireLock('class-1', 'Cliente', 'panel');
    service.onNodeDragEnded('class-1', true);

    expect(sendLockReleaseSpy).not.toHaveBeenCalled();
    expect(service.isHeldLocally('class-1')).toBeTrue();
  });

  it('libera el elemento anterior si se adquiere otro diferente', () => {
    service.acquireLock('class-1', 'Cliente', 'panel');
    service.acquireLock('class-2', 'Pedido', 'panel');

    expect(sendLockReleaseSpy).toHaveBeenCalledWith('class-1');
    expect(sendLockAcquireSpy).toHaveBeenCalledWith('class-2');
    expect(service.isHeldLocally('class-1')).toBeFalse();
    expect(service.isHeldLocally('class-2')).toBeTrue();
  });

  describe('Bloqueo remoto (real, no decorativo)', () => {
    it('bloquea el elemento cuando otro peer adquiere el lock', () => {
      lockAcquired$.next({
        type: 'lock_acquired',
        elementId: 'class-1',
        holder: { sessionId: 'peer-other', userId: 'u2', displayName: 'Carlos' },
        ttlMs: 15000,
      });

      expect(service.isLockedByOther('class-1')).toBeTrue();
      expect(service.getLockHolderName('class-1')).toBe('Carlos');
    });

    it('Ajuste B: el eco de la propia adquisición NO auto-bloquea el elemento', () => {
      lockAcquired$.next({
        type: 'lock_acquired',
        elementId: 'class-1',
        holder: { sessionId: 'my-session-id', userId: 'u1', displayName: 'Ana' },
        ttlMs: 15000,
      });

      expect(service.isLockedByOther('class-1')).toBeFalse();
      expect(service.getLockHolderName('class-1')).toBeNull();
      expect(service.remoteLocks()['class-1']).toBeUndefined();
    });

    it('si el titular tiene displayName null o vacío, usa el fallback "otro usuario"', () => {
      lockAcquired$.next({
        type: 'lock_acquired',
        elementId: 'class-1',
        holder: { sessionId: 'peer-anon', userId: null, displayName: null },
        ttlMs: 15000,
      });

      expect(service.isLockedByOther('class-1')).toBeTrue();
      expect(service.getLockHolderName('class-1')).toBe('otro usuario');
    });

    it('desbloquea el elemento cuando llega lock_released', () => {
      lockAcquired$.next({
        type: 'lock_acquired',
        elementId: 'class-1',
        holder: { sessionId: 'peer-other', userId: 'u2', displayName: 'Carlos' },
        ttlMs: 15000,
      });
      expect(service.isLockedByOther('class-1')).toBeTrue();

      lockReleased$.next({
        type: 'lock_released',
        elementId: 'class-1',
      });

      expect(service.isLockedByOther('class-1')).toBeFalse();
    });

    it('al recibir lock_denied por held, pasa a solo lectura con el titular', () => {
      service.acquireLock('class-1', 'Cliente', 'panel');

      lockDenied$.next({
        type: 'lock_denied',
        elementId: 'class-1',
        reason: 'held',
        holder: { sessionId: 'peer-other', userId: 'u2', displayName: 'Carlos' },
      });

      expect(service.isHeldLocally('class-1')).toBeFalse();
      expect(service.isLockedByOther('class-1')).toBeTrue();
      expect(service.getLockHolderName('class-1')).toBe('Carlos');
    });

    it('al recibir lock_denied por limit, muestra aviso de límite sin bloquear otros elementos', () => {
      service.acquireLock('class-1', 'Cliente', 'panel');

      lockDenied$.next({
        type: 'lock_denied',
        elementId: 'class-1',
        reason: 'limit',
        holder: null,
      });

      expect(service.isHeldLocally('class-1')).toBeFalse();
      expect(service.isLockedByOther('class-1')).toBeFalse();

      const toasts = toast.toasts();
      expect(
        toasts.some((t) => t.text.includes('demasiados elementos en edición a la vez')),
      ).toBeTrue();
    });

    it('aplica locks_snapshot de golpe excluyendo la propia sesión (Ajuste B)', () => {
      locksSnapshot$.next({
        type: 'locks_snapshot',
        locks: [
          {
            elementId: 'class-1',
            holder: { sessionId: 'peer-other', userId: 'u2', displayName: 'Carlos' },
            ttlMs: 15000,
          },
          {
            elementId: 'class-2',
            holder: { sessionId: 'my-session-id', userId: 'u1', displayName: 'Ana' },
            ttlMs: 15000,
          },
        ],
      });

      expect(service.isLockedByOther('class-1')).toBeTrue();
      expect(service.isLockedByOther('class-2')).toBeFalse();
      expect(service.remoteLocks()['class-2']).toBeUndefined();
      expect(service.remoteLocks()['class-1']).toBeDefined();
    });

    it('al reconectar limpia los locks viejos para recibir snapshot fresco', () => {
      lockAcquired$.next({
        type: 'lock_acquired',
        elementId: 'class-1',
        holder: { sessionId: 'peer-other', userId: 'u2', displayName: 'Carlos' },
        ttlMs: 15000,
      });
      expect(service.isLockedByOther('class-1')).toBeTrue();

      reconnected$.next();

      expect(service.isLockedByOther('class-1')).toBeFalse();
    });
  });
});
