import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { UmlApiService } from '../application/uml-api.service';
import {
  applyCanvasDelta,
  CanvasContent,
  CanvasDelta,
  CanvasDeltaMessage,
  isCanvasDeltaMessage,
  NormalizeRelations,
} from './canvas-delta';
import { UmlClassDto } from './models/uml-editor.models';
// Ejemplos GENERADOS por el backend con comandos reales del despachador
// (backend_case/tests/test_canvas_delta.py): si el delta cambia allá, este spec lo detecta.
import examples from '../../../../../../contracts/canvas-delta.examples.json';

interface WireState {
  model: Record<string, unknown[]>;
  layout: unknown;
}
interface ExampleStep {
  name: string;
  command: string;
  message: CanvasDeltaMessage;
  after: WireState;
}
const initial = examples.initial as unknown as WireState;
const steps = examples.steps as unknown as ExampleStep[];

describe('applyCanvasDelta (contrato canvas-delta.v1)', () => {
  let normalizeRelations: NormalizeRelations;
  let toContent: (wire: WireState) => CanvasContent;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    const api = TestBed.inject(UmlApiService);
    normalizeRelations = (wire) => api.normalizeRelationsPart(wire);
    // El estado "verdadero" que reconstruye un cliente al bajar el lienzo entero por HTTP.
    toContent = (wire) => ({
      model: api.normalizeCanvas({ model: wire.model }).model,
      layout: wire.layout as CanvasContent['layout'],
    });
  });

  it('los ejemplos del contrato cubren los tipos de cambio que importan', () => {
    const comandos = new Set(steps.map((s) => s.command));
    for (const esperado of [
      'CREATE_CLASS',
      'UPDATE_CLASS_NAME',
      'DELETE_ELEMENTS',
      'CREATE_RELATION',
      'DELETE_RELATION',
      'MOVE_ELEMENT',
      'UPDATE_RELATION_VERTICES',
      'UPDATE_VIEWPORT',
    ]) {
      expect(comandos.has(esperado)).withContext(esperado).toBeTrue();
    }
  });

  it('aplicar cada delta al contenido anterior da EXACTAMENTE lo que daría bajar el lienzo entero', () => {
    let actual = toContent(initial);

    for (const step of steps) {
      actual = applyCanvasDelta(actual, step.message.delta, normalizeRelations);

      expect(actual).withContext(step.name).toEqual(toContent(step.after));
    }
  });

  it('los mensajes de ejemplo se encadenan: cada uno parte de la versión a la que llegó el anterior', () => {
    steps.forEach((step, index) => {
      expect(isCanvasDeltaMessage(step.message)).withContext(step.name).toBeTrue();
      if (index > 0) {
        expect(step.message.fromVersion).toBe(steps[index - 1].message.toVersion);
      }
      expect(step.message.toVersion).toBe(step.message.fromVersion + 1);
    });
  });

  it('no muta el contenido de entrada ni el delta', () => {
    let actual = toContent(initial);
    for (const step of steps) {
      const antes = JSON.stringify(actual);
      const delta = JSON.stringify(step.message.delta);

      const siguiente = applyCanvasDelta(actual, step.message.delta, normalizeRelations);

      expect(JSON.stringify(actual)).withContext(step.name).toBe(antes);
      expect(JSON.stringify(step.message.delta)).toBe(delta);
      actual = siguiente;
    }
  });

  it('mover una clase solo cambia esa posición y deja intacto el modelo (misma referencia)', () => {
    const paso = steps.find((s) => s.name === 'mover una clase')!;
    const antes = toContent(steps[steps.indexOf(paso) - 1].after);

    const despues = applyCanvasDelta(antes, paso.message.delta, normalizeRelations);

    expect(despues.model).toBe(antes.model);
    expect(despues.layout.links).toBe(antes.layout.links);
    expect(Object.keys(despues.layout.nodes)).toEqual(Object.keys(antes.layout.nodes));
  });

  it('un delta vacío deja el contenido igual', () => {
    const contenido = toContent(initial);

    expect(applyCanvasDelta(contenido, {}, normalizeRelations)).toEqual(contenido);
  });

  it('agrega al final las clases nuevas y reemplaza en su sitio las existentes', () => {
    const clase = (id: string, name: string) => ({ id, name }) as unknown as UmlClassDto;
    const contenido: CanvasContent = {
      model: { classes: [clase('a', 'A'), clase('b', 'B')], relations: [] },
      layout: { viewport: { zoom: 1, panX: 0, panY: 0 }, nodes: {}, links: {} },
    };
    const delta: CanvasDelta = {
      model: { classes: { upsert: [clase('b', 'B2'), clase('c', 'C')], remove: ['a'] } },
    };

    const resultado = applyCanvasDelta(contenido, delta, normalizeRelations);

    expect(resultado.model.classes.map((c) => `${c.id}:${c.name}`)).toEqual(['b:B2', 'c:C']);
  });

  it('una clave __proto__ en el layout no contamina el prototipo', () => {
    const contenido = toContent(initial);
    const delta = JSON.parse(
      '{"layout": {"nodes": {"set": {"__proto__": {"x": 1}}}}}',
    ) as CanvasDelta;

    const resultado = applyCanvasDelta(contenido, delta, normalizeRelations);

    expect(Object.getPrototypeOf(resultado.layout.nodes)).toBe(Object.prototype);
    expect(({} as Record<string, unknown>)['x']).toBeUndefined();
    expect(Object.keys(resultado.layout.nodes)).toContain('__proto__');
  });
});

describe('isCanvasDeltaMessage', () => {
  it('acepta un mensaje bien formado', () => {
    expect(
      isCanvasDeltaMessage({ type: 'canvas_delta', fromVersion: 1, toVersion: 2, delta: {} }),
    ).toBeTrue();
  });

  it('rechaza lo que no se puede encadenar ni aplicar', () => {
    const malos: unknown[] = [
      null,
      'canvas_delta',
      { type: 'canvas_update', fromVersion: 1, toVersion: 2, delta: {} },
      { type: 'canvas_delta', toVersion: 2, delta: {} },
      { type: 'canvas_delta', fromVersion: '1', toVersion: 2, delta: {} },
      { type: 'canvas_delta', fromVersion: 1.5, toVersion: 2, delta: {} },
      { type: 'canvas_delta', fromVersion: 1, toVersion: 2 },
      { type: 'canvas_delta', fromVersion: 1, toVersion: 2, delta: null },
    ];
    for (const malo of malos) {
      expect(isCanvasDeltaMessage(malo)).withContext(JSON.stringify(malo)).toBeFalse();
    }
  });
});
