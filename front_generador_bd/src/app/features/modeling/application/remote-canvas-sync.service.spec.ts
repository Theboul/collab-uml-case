import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Observable, Subject, of, throwError } from 'rxjs';
import { LienzoDetailDto } from '../domain/models/uml-editor.models';
import { UmlGraphService } from '../infrastructure/x6/uml-graph.service';
import { COLLABORATION_GATEWAY } from './collaboration-gateway.service';
import { EditorCommandService } from './editor-command.service';
import { EditorStateService } from './editor-state.service';
import { RemoteCanvasSyncService } from './remote-canvas-sync.service';
import { RemoteNodeDragService } from './remote-node-drag.service';
import { UmlApiService } from './uml-api.service';

const lienzo = (version: number) => ({ version }) as LienzoDetailDto;

describe('RemoteCanvasSyncService (resync tras reconectar)', () => {
  let remoteCanvasUpdate$: Subject<unknown>;
  let reconnected$: Subject<void>;
  let graph: { isDraggingLocally: boolean; nodeMoved$: Subject<void> };
  let getCanvas: jasmine.Spy<(canvasId: string) => Observable<LienzoDetailDto>>;
  let applyCanvasSnapshot: jasmine.Spy;
  let clearAll: jasmine.Spy;
  let state: EditorStateService;

  beforeEach(() => {
    remoteCanvasUpdate$ = new Subject<unknown>();
    reconnected$ = new Subject<void>();
    graph = { isDraggingLocally: false, nodeMoved$: new Subject<void>() };
    getCanvas = jasmine.createSpy('getCanvas');
    applyCanvasSnapshot = jasmine.createSpy('applyCanvasSnapshot');
    clearAll = jasmine.createSpy('clearAll');

    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        { provide: COLLABORATION_GATEWAY, useValue: { remoteCanvasUpdate$, reconnected$ } },
        {
          provide: UmlApiService,
          useValue: { normalizeCanvas: (raw: unknown) => raw as LienzoDetailDto, getCanvas },
        },
        { provide: EditorCommandService, useValue: { applyCanvasSnapshot } },
        { provide: RemoteNodeDragService, useValue: { clearAll } },
        { provide: UmlGraphService, useValue: graph },
      ],
    });
    state = TestBed.inject(EditorStateService);
    state.canvasId.set('c1');
    state.version.set(3);
    TestBed.inject(RemoteCanvasSyncService);
  });

  describe('al reconectar', () => {
    it('pide el lienzo actual y aplica el snapshot si es más nuevo que el estado local', () => {
      getCanvas.and.returnValue(of(lienzo(5)));

      reconnected$.next();

      expect(getCanvas).toHaveBeenCalledOnceWith('c1');
      expect(applyCanvasSnapshot).toHaveBeenCalledOnceWith(lienzo(5));
      expect(clearAll).toHaveBeenCalled();
    });

    it('no aplica nada si el estado local ya está al día (no se perdió ningún cambio)', () => {
      getCanvas.and.returnValue(of(lienzo(3)));

      reconnected$.next();

      expect(getCanvas).toHaveBeenCalledTimes(1);
      expect(applyCanvasSnapshot).not.toHaveBeenCalled();
    });

    it('durante un arrastre local lo difiere hasta que el arrastre termina', () => {
      getCanvas.and.returnValue(of(lienzo(6)));
      graph.isDraggingLocally = true;

      reconnected$.next();
      expect(applyCanvasSnapshot).not.toHaveBeenCalled();

      graph.isDraggingLocally = false;
      graph.nodeMoved$.next();
      expect(applyCanvasSnapshot).toHaveBeenCalledOnceWith(lienzo(6));
    });

    it('sin lienzo abierto no pide nada', () => {
      state.canvasId.set(null);

      reconnected$.next();

      expect(getCanvas).not.toHaveBeenCalled();
    });

    it('un error de red al resincronizar no aplica nada ni rompe los snapshots en vivo', () => {
      const consoleError = spyOn(console, 'error');
      getCanvas.and.returnValue(throwError(() => new Error('sin red')));

      reconnected$.next();

      expect(applyCanvasSnapshot).not.toHaveBeenCalled();
      expect(consoleError).toHaveBeenCalled();
      remoteCanvasUpdate$.next(lienzo(9));
      expect(applyCanvasSnapshot).toHaveBeenCalledOnceWith(lienzo(9));
    });
  });

  describe('snapshots en vivo (comportamiento previo, sin cambios)', () => {
    it('aplica uno más nuevo y descarta uno ya superado', () => {
      remoteCanvasUpdate$.next(lienzo(4));
      remoteCanvasUpdate$.next(lienzo(2));

      expect(applyCanvasSnapshot).toHaveBeenCalledOnceWith(lienzo(4));
    });

    it('durante un arrastre local guarda solo el más reciente y lo aplica al terminar', () => {
      graph.isDraggingLocally = true;
      remoteCanvasUpdate$.next(lienzo(4));
      remoteCanvasUpdate$.next(lienzo(6));
      remoteCanvasUpdate$.next(lienzo(5));
      expect(applyCanvasSnapshot).not.toHaveBeenCalled();

      graph.isDraggingLocally = false;
      graph.nodeMoved$.next();

      expect(applyCanvasSnapshot).toHaveBeenCalledOnceWith(lienzo(6));
    });
  });
});
