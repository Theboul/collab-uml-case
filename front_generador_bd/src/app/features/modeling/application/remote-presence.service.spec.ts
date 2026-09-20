import { TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { Subject } from 'rxjs';
import { COLLABORATION_GATEWAY } from './collaboration-gateway.service';
import {
  PresenceJoinedMessage,
  PresenceLeftMessage,
  PresenceSnapshotMessage,
  pickColorForPeer,
} from '../domain/models/collaboration.models';
import { RemotePresenceService } from './remote-presence.service';

describe('RemotePresenceService', () => {
  let service: RemotePresenceService;

  let presenceSnapshot$: Subject<PresenceSnapshotMessage>;
  let presenceJoined$: Subject<PresenceJoinedMessage>;
  let presenceLeft$: Subject<PresenceLeftMessage>;
  let reconnected$: Subject<void>;
  let currentPeerId: string | null;

  beforeEach(() => {
    presenceSnapshot$ = new Subject<PresenceSnapshotMessage>();
    presenceJoined$ = new Subject<PresenceJoinedMessage>();
    presenceLeft$ = new Subject<PresenceLeftMessage>();
    reconnected$ = new Subject<void>();
    currentPeerId = 'my-session-id';

    const fakeGateway = {
      get peerId() {
        return currentPeerId;
      },
      presenceSnapshot$: presenceSnapshot$.asObservable(),
      presenceJoined$: presenceJoined$.asObservable(),
      presenceLeft$: presenceLeft$.asObservable(),
      reconnected$: reconnected$.asObservable(),
    };

    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        RemotePresenceService,
        { provide: COLLABORATION_GATEWAY, useValue: fakeGateway },
      ],
    });

    service = TestBed.inject(RemotePresenceService);
  });

  afterEach(() => {
    service.reset();
  });

  it('presence_snapshot puebla todas las sesiones con sus colores determinísticos', () => {
    presenceSnapshot$.next({
      type: 'presence_snapshot',
      sessions: [
        { sessionId: 's-1', userId: 'u1', displayName: 'Ana' },
        { sessionId: 's-2', userId: null, displayName: null },
      ],
    });

    const all = service.sessions();
    expect(all.length).toBe(2);
    expect(all[0].displayName).toBe('Ana');
    expect(all[0].color).toBe(pickColorForPeer('s-1'));
    expect(all[1].displayName).toBeNull();
    expect(all[1].color).toBe(pickColorForPeer('s-2'));
  });

  it('remotePeers excluye la propia sesión del usuario actual', () => {
    presenceSnapshot$.next({
      type: 'presence_snapshot',
      sessions: [
        { sessionId: 'my-session-id', userId: 'u-me', displayName: 'Yo' },
        { sessionId: 'peer-carlos', userId: 'u2', displayName: 'Carlos' },
      ],
    });

    expect(service.sessions().length).toBe(2);

    const remote = service.remotePeers();
    expect(remote.length).toBe(1);
    expect(remote[0].sessionId).toBe('peer-carlos');
    expect(remote[0].displayName).toBe('Carlos');
  });

  it('presence_joined agrega un nuevo colaborador a la sala', () => {
    presenceSnapshot$.next({
      type: 'presence_snapshot',
      sessions: [{ sessionId: 'my-session-id', userId: 'u-me', displayName: 'Yo' }],
    });
    expect(service.remotePeers().length).toBe(0);

    presenceJoined$.next({
      type: 'presence_joined',
      session: { sessionId: 'peer-elena', userId: 'u3', displayName: 'Elena' },
    });

    const remote = service.remotePeers();
    expect(remote.length).toBe(1);
    expect(remote[0].sessionId).toBe('peer-elena');
    expect(remote[0].displayName).toBe('Elena');
    expect(remote[0].color).toBe(pickColorForPeer('peer-elena'));
  });

  it('presence_left retira al colaborador cuando abandona la sala', () => {
    presenceSnapshot$.next({
      type: 'presence_snapshot',
      sessions: [
        { sessionId: 'peer-1', userId: 'u1', displayName: 'Ana' },
        { sessionId: 'peer-2', userId: 'u2', displayName: 'Carlos' },
      ],
    });
    expect(service.remotePeers().length).toBe(2);

    presenceLeft$.next({
      type: 'presence_left',
      sessionId: 'peer-1',
    });

    const remote = service.remotePeers();
    expect(remote.length).toBe(1);
    expect(remote[0].sessionId).toBe('peer-2');
  });

  it('al emitir reconnected$ ejecuta reset() limpiando sessions antes de que llegue el siguiente snapshot', () => {
    spyOn(service, 'reset').and.callThrough();

    presenceSnapshot$.next({
      type: 'presence_snapshot',
      sessions: [{ sessionId: 'peer-1', userId: 'u1', displayName: 'Ana' }],
    });
    expect(service.remotePeers().length).toBe(1);

    // Evento de reconexión tras caída o reconexión de WebSocket
    reconnected$.next();

    expect(service.reset).toHaveBeenCalled();
    expect(service.remotePeers().length).toBe(0);
    expect(service.sessions().length).toBe(0);

    // Snapshot fresco entrante tras la reconexión
    presenceSnapshot$.next({
      type: 'presence_snapshot',
      sessions: [{ sessionId: 'peer-2', userId: 'u2', displayName: 'Beto' }],
    });
    expect(service.remotePeers().length).toBe(1);
    expect(service.remotePeers()[0].displayName).toBe('Beto');
  });
});
