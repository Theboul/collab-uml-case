import { TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { UmlDiagramAdapterService } from './uml-diagram-adapter.service';
import { DiagramLayout, ModeloUML } from '../../domain/models/uml-editor.models';

describe('UmlDiagramAdapterService', () => {
  let service: UmlDiagramAdapterService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        UmlDiagramAdapterService,
      ],
    });
    service = TestBed.inject(UmlDiagramAdapterService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should translate ModeloUML classes to X6 nodes with 4 ports', () => {
    const model: ModeloUML = {
      classes: [
        {
          id: 'c-1',
          name: 'Cliente',
          isAbstract: false,
          attributes: [{ id: 'a1', name: 'id', type: 'UUID', visibility: '-' }],
          operations: [{ id: 'o1', name: 'registrar', returnType: 'void', visibility: '+' }],
        },
      ],
      relations: [],
    };

    const layout: DiagramLayout = {
      viewport: { zoom: 1, panX: 0, panY: 0 },
      nodes: {
        'c-1': { x: 150, y: 220, width: 200, height: 140 },
      },
      links: {},
    };

    const { nodes, edges } = service.modelToCells(model, layout);

    expect(nodes.length).toBe(1);
    expect(edges.length).toBe(0);
    expect(nodes[0].id).toBe('c-1');
    expect(nodes[0].shape).toBe('uml-class-node');
    expect(nodes[0].x).toBe(150);
    expect(nodes[0].y).toBe(220);
    expect(nodes[0].width).toBe(200);
    expect(nodes[0].height).toBe(140);
    expect(nodes[0].data.name).toBe('Cliente');
    expect(nodes[0].ports.items.length).toBe(4);
  });

  it('should configure markers correctly based on relation type', () => {
    const relAggregation = service.buildEdgeConfig({
      id: 'r-1',
      type: 'AGGREGATION',
      sourceClassId: 'c-1',
      targetClassId: 'c-2',
      sourceMultiplicity: '1',
      targetMultiplicity: '0..*',
    });

    expect(relAggregation.attrs['line'].sourceMarker).toBeTruthy();
    expect(relAggregation.attrs['line'].sourceMarker.fill).toBe('#ffffff'); // rombo hueco

    const relComposition = service.buildEdgeConfig({
      id: 'r-2',
      type: 'COMPOSITION',
      sourceClassId: 'c-1',
      targetClassId: 'c-2',
      sourceMultiplicity: '1',
      targetMultiplicity: '1',
    });

    expect(relComposition.attrs['line'].sourceMarker.fill).toBe('#1e293b'); // rombo relleno

    const relGeneralization = service.buildEdgeConfig({
      id: 'r-3',
      type: 'GENERALIZATION',
      sourceClassId: 'c-1',
      targetClassId: 'c-2',
      sourceMultiplicity: '',
      targetMultiplicity: '',
    });

    expect(relGeneralization.attrs['line'].targetMarker).toBeTruthy();
    expect(relGeneralization.attrs['line'].targetMarker.fill).toBe('#ffffff'); // triángulo cerrado
  });
});
