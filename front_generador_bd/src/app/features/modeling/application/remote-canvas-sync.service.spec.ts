import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Observable, Subject, of, throwError } from 'rxjs';
import { CanvasDelta, CanvasDeltaMessage } from '../domain/canvas-delta';
import {
  DiagramLayout,
  LienzoDetailDto,
  ModeloUML,
  UmlClassDto,
} from '../domain/models/uml-editor.models';
import { UmlGraphService } from '../infrastructure/x6/uml-graph.service';
import { COLLABORATION_GATEWAY } from './collaboration-gateway.service';
import { MAX_QUEUED_DELTAS } from './collaboration-tuning';
import { EditorCommandService } from './editor-command.service';
import { EditorStateService } from './editor-state.service';
import { RemoteCanvasSyncService } from './remote-canvas-sync.service';
import { RemoteNodeDragService } from './remote-node-drag.service';
import { UmlApiService } from './uml-api.service';

const lienzo = (version: number) => ({ version }) as LienzoDetailDto;
const clase = (id: string, name: string) => ({ id, name }) as unknown as UmlClassDto;
const delta = (fromVersion: number, changes: CanvasDelta = {}): CanvasDeltaMessage => ({
  type: 'canvas_delta',
  fromVersion,
  toVersion: fromVersion + 1,
  delta: changes,
});
const nuevaClase = (fromVersion: number, id: string): CanvasDeltaMessage =>
  delta(fromVersion, { model: { classes: { upsert: [clase(id, id.toUpperCase())] } } });

describe('RemoteCanvasSyncService', () => {
  let remoteCanvasDelta$: Subject<CanvasDeltaMessage>;
  let reconnected$: Subject<void>;
  let graph: { isDraggingLocally: boolean; nodeMoved$: Subject<void> };
  let getCanvas: jasmine.Spy<(canvasId: string) => Observable<LienzoDetailDto>>;
  let applyCanvasSnapshot: jasmine.Spy;
  let applyCanvasContent: jasmine.Spy;
  let clearAll: jasmine.Spy;
  let state: EditorStateService;

  beforeEach(() => {
    remoteCanvasDelta$ = new Subject<CanvasDeltaMessage>();
    reconnected$ = new Subject<void>();
    graph = { isDraggingLocally: false, nodeMoved$: new Subject<void>() };
    getCanvas = jasmine.createSpy('getCanvas');
    // Como el servicio real: aplicar contenido o snapshot deja el estado local en esa versión.
    applyCanvasSnapshot = jasmine
      .createSpy('applyCanvasSnapshot')
      .and.callFake((dto: LienzoDetailDto) => {
        state.version.set(dto.version);
      });
    applyCanvasContent = jasmine
      .createSpy('applyCanvasContent')
      .and.callFake((model: ModeloUML, layout: DiagramLayout, version: number) => {
        state.setSnapshot(model, layout);
        state.version.set(version);
      });
    clearAll = jasmine.createSpy('clearAll');

    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        { provide: COLLABORATION_GATEWAY, useValue: { remoteCanvasDelta$, reconnected$ } },
        {
          provide: UmlApiService,
          useValue: { getCanvas, normalizeRelationsPart: () => [] },
        },
        { provide: EditorCommandService, useValue: { applyCanvasSnapshot, applyCanvasContent } },
        { provide: RemoteNodeDragService, useValue: { clearAll } },
        { provide: UmlGraphService, useValue: graph },
      ],
    });
    state = TestBed.inject(EditorStateService);
    state.canvasId.set('c1');
    state.version.set(3);
    TestBed.inject(RemoteCanvasSyncService);
  });

  const versionesAplicadas = () =>
    applyCanvasContent.calls.allArgs().map(([, , version]) => version as number);
  const nombresDeClases = () => state.model().classes.map((c) => c.id);

  describe('deltas en vivo', () => {
    it('aplica el delta que parte exactamente de la versión local y avanza a su toVersion', () => {
      remoteCanvasDelta$.next(nuevaClase(3, 'a'));

      expect(versionesAplicadas()).toEqual([4]);
      expect(nombresDeClases()).toEqual(['a']);
      expect(state.version()).toBe(4);
      expect(clearAll).toHaveBeenCalled();
    });

    it('aplica una cadena de deltas en orden', () => {
      remoteCanvasDelta$.next(nuevaClase(3, 'a'));
      remoteCanvasDelta$.next(nuevaClase(4, 'b'));
      remoteCanvasDelta$.next(nuevaClase(5, 'c'));

      expect(nombresDeClases()).toEqual(['a', 'b', 'c']);
      expect(state.version()).toBe(6);
      expect(getCanvas).not.toHaveBeenCalled();
    });

    it('descarta un delta ya incluido (p. ej. el eco del propio cambio) sin pedir nada', () => {
      remoteCanvasDelta$.next(nuevaClase(2, 'a')); // toVersion 3 <= 3
      remoteCanvasDelta$.next(nuevaClase(1, 'b'));

      expect(applyCanvasContent).not.toHaveBeenCalled();
      expect(getCanvas).not.toHaveBeenCalled();
    });

    it('un hueco fuerza un resync y NO aplica el delta sobre un estado incorrecto', () => {
      getCanvas.and.returnValue(of(lienzo(3)));

      remoteCanvasDelta$.next(nuevaClase(5, 'a')); // faltan 3→4 y 4→5

      expect(getCanvas).toHaveBeenCalledOnceWith('c1');
      expect(applyCanvasContent).not.toHaveBeenCalled();
    });

    it('tras el resync aplica el snapshot y luego el delta que ya encadena con él', () => {
      getCanvas.and.returnValue(of(lienzo(5)));

      remoteCanvasDelta$.next(nuevaClase(5, 'a')); // hueco (local 3) pero encadena con el snapshot v5

      expect(applyCanvasSnapshot).toHaveBeenCalledOnceWith(lienzo(5));
      expect(versionesAplicadas()).toEqual([6]);
      expect(state.version()).toBe(6);
    });

    it('los deltas que llegan mientras el snapshot viaja esperan y se aplican en orden después', () => {
      const respuesta = new Subject<LienzoDetailDto>();
      getCanvas.and.returnValue(respuesta);

      remoteCanvasDelta$.next(nuevaClase(5, 'a')); // hueco → resync en vuelo
      remoteCanvasDelta$.next(nuevaClase(6, 'b'));
      remoteCanvasDelta$.next(nuevaClase(7, 'c'));
      expect(applyCanvasContent).not.toHaveBeenCalled();
      expect(getCanvas).toHaveBeenCalledTimes(1); // no lanza un resync por cada mensaje

      respuesta.next(lienzo(5));

      expect(applyCanvasSnapshot).toHaveBeenCalledOnceWith(lienzo(5));
      expect(versionesAplicadas()).toEqual([6, 7, 8]);
      expect(nombresDeClases()).toEqual(['a', 'b', 'c']);
    });

    it('si tras el resync el hueco persiste no entra en un bucle de resyncs', () => {
      const aviso = spyOn(console, 'warn');
      getCanvas.and.returnValue(of(lienzo(4)));

      remoteCanvasDelta$.next(nuevaClase(9, 'a'));

      expect(getCanvas).toHaveBeenCalledTimes(1);
      expect(applyCanvasContent).not.toHaveBeenCalled();
      expect(aviso).toHaveBeenCalled();
    });

    it('un delta que no se puede aplicar no deja el lienzo a medias: resincroniza', () => {
      const error = spyOn(console, 'error');
      getCanvas.and.returnValue(of(lienzo(3)));
      const malo = {
        type: 'canvas_delta',
        fromVersion: 3,
        toVersion: 4,
        delta: { model: { classes: { upsert: 5 } } },
      };

      remoteCanvasDelta$.next(malo as unknown as CanvasDeltaMessage);

      expect(applyCanvasContent).not.toHaveBeenCalled();
      expect(state.version()).toBe(3);
      expect(getCanvas).toHaveBeenCalledTimes(1);
      expect(error).toHaveBeenCalled();
    });
  });

  describe('durante un arrastre local', () => {
    it('guarda TODOS los deltas en orden (no solo el último) y los aplica al terminar', () => {
      graph.isDraggingLocally = true;
      remoteCanvasDelta$.next(nuevaClase(3, 'a'));
      remoteCanvasDelta$.next(nuevaClase(4, 'b'));
      remoteCanvasDelta$.next(nuevaClase(5, 'c'));
      expect(applyCanvasContent).not.toHaveBeenCalled();

      graph.isDraggingLocally = false;
      graph.nodeMoved$.next();

      expect(versionesAplicadas()).toEqual([4, 5, 6]);
      expect(nombresDeClases()).toEqual(['a', 'b', 'c']);
      expect(getCanvas).not.toHaveBeenCalled();
    });

    it('no aplica nada mientras el arrastre sigue en curso', () => {
      graph.isDraggingLocally = true;
      remoteCanvasDelta$.next(nuevaClase(3, 'a'));

      graph.nodeMoved$.next(); // el flag aún dice que arrastra

      expect(applyCanvasContent).not.toHaveBeenCalled();
    });

    it('si mientras arrastra el estado avanzó, los deltas ya incluidos se descartan al terminar', () => {
      graph.isDraggingLocally = true;
      remoteCanvasDelta$.next(nuevaClase(3, 'a'));
      remoteCanvasDelta$.next(nuevaClase(4, 'b'));
      state.version.set(5); // la respuesta HTTP de un cambio propio, ya con ambos incluidos

      graph.isDraggingLocally = false;
      graph.nodeMoved$.next();

      expect(applyCanvasContent).not.toHaveBeenCalled();
      expect(getCanvas).not.toHaveBeenCalled();
    });

    it('un hueco en la cola detectado al terminar el arrastre resincroniza', () => {
      getCanvas.and.returnValue(of(lienzo(3)));
      graph.isDraggingLocally = true;
      remoteCanvasDelta$.next(nuevaClase(4, 'b')); // falta 3→4

      graph.isDraggingLocally = false;
      graph.nodeMoved$.next();

      expect(getCanvas).toHaveBeenCalledTimes(1);
      expect(applyCanvasContent).not.toHaveBeenCalled();
    });

    it('si la cola se desborda se descarta y se resincroniza en vez de acumular sin límite', () => {
      getCanvas.and.returnValue(of(lienzo(3 + MAX_QUEUED_DELTAS + 5)));
      graph.isDraggingLocally = true;
      for (let i = 0; i < MAX_QUEUED_DELTAS + 5; i++) {
        remoteCanvasDelta$.next(nuevaClase(3 + i, `c${i}`));
      }

      graph.isDraggingLocally = false;
      graph.nodeMoved$.next();

      expect(getCanvas).toHaveBeenCalledTimes(1);
      expect(applyCanvasSnapshot).toHaveBeenCalledTimes(1);
    });
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

    it('mientras el snapshot viaja, un delta que sí encadena espera y se aplica después', () => {
      const respuesta = new Subject<LienzoDetailDto>();
      getCanvas.and.returnValue(respuesta);
      reconnected$.next();

      remoteCanvasDelta$.next(nuevaClase(3, 'a'));
      expect(applyCanvasContent).not.toHaveBeenCalled(); // la base va a ser reemplazada

      respuesta.next(lienzo(3)); // no se perdió nada mientras estuvo caído

      expect(versionesAplicadas()).toEqual([4]);
    });

    it('sin lienzo abierto no pide nada', () => {
      state.canvasId.set(null);

      reconnected$.next();

      expect(getCanvas).not.toHaveBeenCalled();
    });

    it('un error de red al resincronizar no aplica nada ni rompe los deltas siguientes', () => {
      const consoleError = spyOn(console, 'error');
      getCanvas.and.returnValue(throwError(() => new Error('sin red')));

      reconnected$.next();

      expect(applyCanvasSnapshot).not.toHaveBeenCalled();
      expect(consoleError).toHaveBeenCalled();
      remoteCanvasDelta$.next(nuevaClase(3, 'a'));
      expect(versionesAplicadas()).toEqual([4]);
    });

    it('un error de red con un hueco en cola no reintenta en bucle', () => {
      spyOn(console, 'error');
      spyOn(console, 'warn');
      getCanvas.and.returnValue(throwError(() => new Error('sin red')));

      remoteCanvasDelta$.next(nuevaClase(9, 'a')); // hueco → resync → falla

      expect(getCanvas).toHaveBeenCalledTimes(1);
    });
  });
});
