import { TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { UmlGraphService } from './uml-graph.service';
import { X6NodeConfig } from './uml-diagram-adapter.service';

/**
 * El nodo de clase muestra TODO su contenido: sin scroll ni "+N", se ensancha según el
 * texto (hasta un máximo) y envuelve lo que aun así no entra. Se verifica contra el DOM
 * real (geometría medida por el navegador), no contra los números del layout.
 */

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

async function waitFor<T>(find: () => T | null | undefined, timeoutMs = 2000): Promise<T> {
  const start = performance.now();
  for (;;) {
    const found = find();
    if (found) return found;
    if (performance.now() - start > timeoutMs) throw new Error('waitFor: timeout');
    await sleep(16);
  }
}

interface ClassData {
  name: string;
  isAbstract?: boolean;
  attributes: { id: string; name: string; type: string; visibility: string }[];
  operations: {
    id: string;
    name: string;
    returnType: string;
    visibility: string;
    parameters?: { id: string; name: string; type: string }[];
  }[];
}

const LONG_NAME = 'GestorDeFacturacionElectronicaInternacional'; // 43 caracteres

function manyAttributes(count: number): ClassData['attributes'] {
  return Array.from({ length: count }, (_, i) => ({
    id: `a${i}`,
    name: `atributo${i}`,
    type: 'String',
    visibility: '-',
  }));
}

const LONG_OPERATION: ClassData['operations'][number] = {
  id: 'op-long',
  name: 'emitirComprobanteFiscal',
  returnType: 'String',
  visibility: '+',
  parameters: [
    { id: 'p0', name: 'cliente', type: 'String' },
    { id: 'p1', name: 'monto', type: 'double' },
    { id: 'p2', name: 'moneda', type: 'String' },
    { id: 'p3', name: 'referenciaExterna', type: 'String' },
  ],
};

const SHORT_OPERATION: ClassData['operations'][number] = {
  id: 'op-short',
  name: 'anular',
  returnType: 'void',
  visibility: '+',
};

describe('Nodo de clase X6: contenido completo, ancho adaptable y texto envuelto', () => {
  let container: HTMLElement;
  let graphService: UmlGraphService;

  function addClass(id: string, data: ClassData, width = 190, height = 130): void {
    const config: X6NodeConfig = {
      id,
      shape: 'uml-class-node',
      x: 60,
      y: 60,
      width,
      height,
      data: { isAbstract: false, ...data },
    };
    graphService.addNode(config);
  }

  function nodeEl(id: string): SVGGElement {
    return container.querySelector<SVGGElement>(`g.x6-node[data-cell-id="${id}"]`)!;
  }

  /** El primer <rect> del nodo es el fondo (`body`): su caja en pantalla es la caja del nodo. */
  function boxOf(id: string): DOMRect {
    return nodeEl(id).querySelector('rect')!.getBoundingClientRect();
  }

  async function mounted(id: string, attributeRows: number): Promise<void> {
    await waitFor(() => nodeEl(id));
    // Las filas de atributos y de operaciones se pintan en la misma pasada de render().
    await waitFor(() => nodeEl(id).querySelectorAll('.uml-attr-row').length === attributeRows);
    await sleep(60);
  }

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    graphService = TestBed.inject(UmlGraphService);
    container = document.createElement('div');
    container.style.cssText = 'position:fixed;left:0;top:0;width:1200px;height:900px';
    document.body.appendChild(container);
    graphService.initGraph(container);
  });

  afterEach(() => {
    graphService.dispose();
    container.remove();
  });

  describe('sin scroll ni recorte de atributos', () => {
    it('una clase con 12 atributos muestra las 12 filas, sin indicador "+N"', async () => {
      addClass('n1', {
        name: 'Grande',
        attributes: manyAttributes(12),
        operations: [SHORT_OPERATION],
      });
      await mounted('n1', 12);

      expect(nodeEl('n1').querySelectorAll('.uml-attr-row').length).toBe(12);
      const badges = Array.from(nodeEl('n1').querySelectorAll('text')).filter((t) =>
        /^\+\d+$/.test((t.textContent ?? '').trim()),
      );
      expect(badges.length).toBe(0);
    });

    it('todas las filas caen dentro del nodo: el alto crece con la cantidad de atributos', async () => {
      addClass('n1', {
        name: 'Grande',
        attributes: manyAttributes(12),
        operations: [SHORT_OPERATION],
      });
      await mounted('n1', 12);

      const box = boxOf('n1');
      const rows = Array.from(nodeEl('n1').querySelectorAll('.uml-attr-row'));
      for (const row of rows) {
        const r = row.getBoundingClientRect();
        expect(r.bottom).toBeLessThanOrEqual(box.bottom + 0.5);
      }
      expect(box.height).toBeGreaterThan(12 * 22); // 12 filas de 22px como mínimo
    });

    it('agregar atributos con updateNodeData agranda el nodo y pinta todas las filas nuevas', async () => {
      addClass('n1', { name: 'Clase', attributes: manyAttributes(2), operations: [] });
      await mounted('n1', 2);
      const before = boxOf('n1').height;

      graphService.updateNodeData('n1', {
        name: 'Clase',
        isAbstract: false,
        attributes: manyAttributes(10),
        operations: [],
      });
      await waitFor(() => nodeEl('n1').querySelectorAll('.uml-attr-row').length === 10);
      await sleep(60);

      expect(boxOf('n1').height).toBeGreaterThan(before + 7 * 22);
    });
  });

  describe('el ancho se adapta al contenido', () => {
    it('un nombre de 43 caracteres ensancha el nodo en vez de desbordar el encabezado', async () => {
      addClass('n1', { name: LONG_NAME, attributes: manyAttributes(1), operations: [] });
      await mounted('n1', 1);

      const box = boxOf('n1');
      const title = nodeEl('n1').querySelector('text')!.getBoundingClientRect();
      expect(box.width).toBeGreaterThan(190);
      expect(box.width).toBeLessThanOrEqual(340 + 1);
      expect(title.left).toBeGreaterThanOrEqual(box.left - 0.5);
      expect(title.right).toBeLessThanOrEqual(box.right + 0.5);
    });

    it('el rect del encabezado conserva dimensiones válidas (ancho = ancho del nodo, alto > 0)', async () => {
      addClass('n1', { name: LONG_NAME, attributes: manyAttributes(1), operations: [] });
      await mounted('n1', 1);

      const header = nodeEl('n1').querySelectorAll('rect')[1].getBoundingClientRect();
      const box = boxOf('n1');
      expect(header.height).toBeGreaterThan(0);
      expect(Math.abs(header.width - box.width)).toBeLessThanOrEqual(1);
    });

    it('un nombre más largo que el ancho máximo se envuelve y el encabezado crece en alto', async () => {
      const veryLong = `${LONG_NAME}ParaFacturacionElectronicaDeExportacionAlExterior`;
      addClass('n1', { name: veryLong, attributes: manyAttributes(1), operations: [] });
      await mounted('n1', 1);

      const box = boxOf('n1');
      const titleEl = nodeEl('n1').querySelector('text')!;
      const title = titleEl.getBoundingClientRect();
      const header = nodeEl('n1').querySelectorAll('rect')[1].getBoundingClientRect();

      expect(box.width).toBeLessThanOrEqual(340 + 1);
      expect(titleEl.querySelectorAll('tspan').length).toBeGreaterThan(1);
      expect(header.height).toBeGreaterThan(32);
      expect(title.left).toBeGreaterThanOrEqual(box.left - 0.5);
      expect(title.right).toBeLessThanOrEqual(box.right + 0.5);
      expect(title.bottom).toBeLessThanOrEqual(header.bottom + 0.5);
    });
  });

  describe('el texto largo se envuelve dentro del nodo', () => {
    it('una firma de método muy larga no se sale del borde derecho y ocupa varias líneas', async () => {
      addClass('n1', {
        name: 'Facturador',
        attributes: manyAttributes(1),
        operations: [LONG_OPERATION, SHORT_OPERATION],
      });
      await mounted('n1', 1);

      const box = boxOf('n1');
      const opTexts = Array.from(
        nodeEl('n1').querySelectorAll<SVGTextElement>('.uml-operations-text'),
      );
      for (const t of opTexts) {
        const r = t.getBoundingClientRect();
        expect(r.right).toBeLessThanOrEqual(box.right + 0.5);
        expect(r.bottom).toBeLessThanOrEqual(box.bottom + 0.5);
      }
      const lines = opTexts.reduce((n, t) => n + t.querySelectorAll('tspan').length, 0);
      expect(lines).toBeGreaterThan(2); // la firma larga (>1 línea) + la corta
    });

    it('un atributo con nombre y tipo largos se envuelve dentro del nodo, sin pisar el ícono ni el borde', async () => {
      addClass('n1', {
        name: 'Documento',
        attributes: [
          {
            id: 'a-long',
            name: 'atributoConNombreExtremadamenteLargoParaProbarElRecorteDelTexto',
            type: 'BigDecimalConPrecisionExtendida',
            visibility: '-',
          },
        ],
        operations: [],
      });
      await mounted('n1', 1);

      const box = boxOf('n1');
      const nameText = nodeEl('n1').querySelector('.uml-attr-name')!;
      const r = nameText.getBoundingClientRect();
      expect(nameText.querySelectorAll('tspan').length).toBeGreaterThan(1);
      expect(r.right).toBeLessThanOrEqual(box.right - 25 + 0.5);
      expect(r.left).toBeGreaterThanOrEqual(box.left);
      expect(nameText.textContent).not.toContain('…');
      expect(r.bottom).toBeLessThanOrEqual(box.bottom + 0.5);
    });
  });

  describe('separadores, encabezado y ritmo vertical', () => {
    it('los dos separadores se dibujan con ancho > 0 (el ancho del nodo)', async () => {
      addClass('n1', {
        name: 'Cliente',
        attributes: manyAttributes(2),
        operations: [SHORT_OPERATION],
      });
      await mounted('n1', 2);

      const box = boxOf('n1');
      const hairlines = Array.from(nodeEl('n1').querySelectorAll('line, rect')).filter((el) => {
        if (getComputedStyle(el).display === 'none') return false;
        return el.getBoundingClientRect().height <= 2.6;
      });

      expect(hairlines.length).toBe(2);
      for (const h of hairlines) {
        const r = h.getBoundingClientRect();
        expect(r.width).toBeGreaterThan(0);
        expect(Math.abs(r.width - box.width)).toBeLessThanOrEqual(1);
      }
    });

    it('el encabezado no usa el color del fondo del canvas (#f8fafc)', async () => {
      addClass('n1', { name: 'Cliente', attributes: manyAttributes(1), operations: [] });
      await mounted('n1', 1);

      const header = nodeEl('n1').querySelectorAll('rect')[1];
      expect(header.getAttribute('fill')).not.toBe('#f8fafc');
      expect(header.getAttribute('fill')).toBe('#e0e7ff');
    });

    it('las operaciones usan el mismo tamaño de fuente (12px) y el mismo ritmo (22px) que los atributos', async () => {
      addClass('n1', {
        name: 'Cliente',
        attributes: manyAttributes(2),
        operations: [SHORT_OPERATION, { ...SHORT_OPERATION, id: 'op2', name: 'registrar' }],
      });
      await mounted('n1', 2);

      const attrRows = Array.from(nodeEl('n1').querySelectorAll('.uml-attr-row-bg'));
      const attrPitch =
        attrRows[1].getBoundingClientRect().top - attrRows[0].getBoundingClientRect().top;

      const opText = nodeEl('n1').querySelector('.uml-operations-text')!;
      const tspans = Array.from(nodeEl('n1').querySelectorAll('.uml-operations-text tspan'));
      const opPitch = tspans[1].getBoundingClientRect().top - tspans[0].getBoundingClientRect().top;

      expect(getComputedStyle(opText).fontSize).toBe('12px');
      expect(attrPitch).toBeCloseTo(22, 0);
      expect(opPitch).toBeCloseTo(attrPitch, 0);
    });
  });

  describe('el estilo de las filas sobrevive a las actualizaciones de la vista', () => {
    /**
     * X6 re-aplica los `attrs` del shape a todos los <text>/<rect> de la vista en cada
     * actualización completa. Si el shape hereda los defaults de `rect` (selectores CSS
     * `text`/`rect`), pisan las filas dibujadas a mano: fuente 14 Arial, text-anchor
     * middle, un transform al centro del nodo y borde gris en cada fondo de fila.
     */
    async function expectRowsKeepTheirStyle(): Promise<void> {
      const texts = Array.from(
        nodeEl('n1').querySelectorAll('.uml-attr-name, .uml-attr-type, .uml-operations-text'),
      );
      expect(texts.length).toBeGreaterThan(5);
      for (const t of texts) {
        expect(t.getAttribute('font-size')).toBe('12');
        expect(t.getAttribute('font-family')).toContain('JetBrains Mono');
        expect(t.hasAttribute('transform')).toBeFalse();
      }
      const names = Array.from(
        nodeEl('n1').querySelectorAll('.uml-attr-name, .uml-operations-text'),
      );
      for (const t of names) expect(t.getAttribute('text-anchor')).toBe('start');
      for (const bg of Array.from(nodeEl('n1').querySelectorAll('.uml-attr-row-bg'))) {
        expect(bg.getAttribute('fill')).toBe('transparent');
        expect(bg.hasAttribute('stroke')).toBeFalse();
      }
    }

    it('resaltar una fila (clic en un atributo u operación) no desarma las filas', async () => {
      addClass('n1', {
        name: 'Cliente',
        attributes: manyAttributes(3),
        operations: [SHORT_OPERATION, LONG_OPERATION],
      });
      await mounted('n1', 3);

      graphService.setRowHighlight('n1', 62, 22);
      await sleep(150);
      await expectRowsKeepTheirStyle();

      graphService.clearRowHighlight('n1');
      await sleep(150);
      await expectRowsKeepTheirStyle();
    });

    it('cambiar el tamaño del nodo no desarma las filas', async () => {
      addClass('n1', {
        name: 'Cliente',
        attributes: manyAttributes(3),
        operations: [SHORT_OPERATION, LONG_OPERATION],
      });
      await mounted('n1', 3);

      const node = graphService.rawGraph!.getCellById('n1') as ReturnType<
        typeof graphService.addNode
      >;
      node.resize(340, 320);
      await sleep(150);
      await expectRowsKeepTheirStyle();
    });
  });

  describe('hit-testing alineado con lo dibujado', () => {
    it('un clic en el centro de cada línea de operación resuelve a esa operación (también las envueltas)', async () => {
      addClass('n1', {
        name: 'Facturador',
        attributes: manyAttributes(2),
        operations: [
          SHORT_OPERATION,
          LONG_OPERATION,
          { ...SHORT_OPERATION, id: 'op3', name: 'registrar' },
        ],
      });
      await mounted('n1', 2);

      const node = graphService.rawGraph!.getCellById('n1') as ReturnType<
        typeof graphService.addNode
      >;
      const texts = Array.from(nodeEl('n1').querySelectorAll('.uml-operations-text'));
      expect(texts.length).toBe(3);

      const expectedIds = ['op-short', 'op-long', 'op3'];
      texts.forEach((text, i) => {
        for (const tspan of Array.from(text.querySelectorAll('tspan'))) {
          const r = tspan.getBoundingClientRect();
          const hit = graphService.resolveSemanticTarget(
            node,
            r.left + r.width / 2,
            r.top + r.height / 2,
          );
          expect(hit?.type).toBe('operation');
          expect(hit?.elementId).toBe(expectedIds[i]);
        }
      });
    });

    it('un clic en el encabezado, aunque sea de varias líneas, resuelve a la clase', async () => {
      const veryLong = `${LONG_NAME}ParaFacturacionElectronicaDeExportacionAlExterior`;
      addClass('n1', {
        name: veryLong,
        attributes: manyAttributes(1),
        operations: [SHORT_OPERATION],
      });
      await mounted('n1', 1);

      const node = graphService.rawGraph!.getCellById('n1') as ReturnType<
        typeof graphService.addNode
      >;
      const header = nodeEl('n1').querySelectorAll('rect')[1].getBoundingClientRect();
      const hit = graphService.resolveSemanticTarget(node, header.left + 20, header.bottom - 3);
      expect(hit?.type).toBe('class');
    });
  });
});
