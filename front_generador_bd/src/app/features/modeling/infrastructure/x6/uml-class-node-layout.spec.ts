import {
  computeUmlClassLayout,
  computeUmlClassMinWidth,
  operationIndexAtY,
  operationRowRect,
  attributeRowRect,
  UmlClassLayoutInput,
} from './uml-class-node-layout';
import { wrapText } from './uml-text-measure';

/** Medidor determinista: 7px por carácter, sin depender de fuentes ni de canvas. */
const CHAR = 7;
const measure = (text: string): number => text.length * CHAR;

function cls(over: Partial<UmlClassLayoutInput> = {}): UmlClassLayoutInput {
  return { name: 'Cliente', isAbstract: false, attributes: [], operations: [], ...over };
}

const attr = (name: string, type = 'String') => ({ name, type, visibility: '-' });
const op = (name: string, returnType = 'void', parameters = '') => ({
  name,
  returnType,
  visibility: '+',
  parameters,
});

const LONG_PARAMS = 'cliente: String, monto: double, moneda: String, ref: String';

describe('wrapText', () => {
  const font = 'irrelevante';

  it('no envuelve un texto que entra', () => {
    expect(wrapText('hola mundo', 200, 200, font, measure)).toEqual(['hola mundo']);
  });

  it('corta en espacios y no deja espacios colgando', () => {
    const lines = wrapText('uno dos tres cuatro', 8 * CHAR, 8 * CHAR, font, measure);
    expect(lines.length).toBeGreaterThan(1);
    for (const l of lines) expect(l).toBe(l.trim());
    expect(lines.join(' ')).toBe('uno dos tres cuatro');
  });

  it('un nombre CamelCase sin espacios se corta entre palabras, no a mitad de palabra', () => {
    const lines = wrapText('GestorDeFacturacionElectronica', 20 * CHAR, 20 * CHAR, font, measure);
    expect(lines).toEqual(['GestorDeFacturacion', 'Electronica']);
  });

  it('un tramo que no entra ni solo se corta por caracteres', () => {
    const lines = wrapText('a'.repeat(30), 10 * CHAR, 10 * CHAR, font, measure);
    expect(lines.length).toBeGreaterThanOrEqual(3);
    expect(lines.join('')).toBe('a'.repeat(30));
    for (const l of lines) expect(measure(l)).toBeLessThanOrEqual(10 * CHAR);
  });

  it('las líneas de continuación usan su propio ancho (sangría)', () => {
    const lines = wrapText('aaaa bbbb cccc dddd', 9 * CHAR, 5 * CHAR, font, measure);
    for (const l of lines.slice(1)) expect(measure(l)).toBeLessThanOrEqual(5 * CHAR);
  });
});

describe('computeUmlClassLayout', () => {
  it('sin contenido usa el ancho y alto mínimos', () => {
    const layout = computeUmlClassLayout(cls(), 0, measure);
    expect(layout.width).toBe(180);
    expect(layout.headerHeight).toBe(32);
    expect(layout.minHeight).toBeGreaterThanOrEqual(110);
  });

  it('el ancho mínimo sigue a la línea más larga (atributo o firma)', () => {
    const short = computeUmlClassMinWidth(cls({ attributes: [attr('id')] }), measure);
    const longAttr = computeUmlClassMinWidth(
      cls({ attributes: [attr('nombreCompletoDelCliente')] }),
      measure,
    );
    const longOp = computeUmlClassMinWidth(
      cls({ operations: [op('registrarNuevoClienteEnSistema')] }),
      measure,
    );
    expect(longAttr).toBeGreaterThan(short);
    expect(longOp).toBeGreaterThan(short);
  });

  it('un texto que justo cabe en el ancho mínimo por contenido no se envuelve (título, atributo ni firma)', () => {
    const layout = computeUmlClassLayout(
      cls({
        name: 'NombreDeClaseMedianamenteLargoParaProbar',
        attributes: [attr('nombreCompletoDelCliente', 'BigDecimal')],
        operations: [op('registrarCliente', 'void', 'a: int')],
      }),
      0,
      measure,
    );
    expect(layout.width).toBeLessThan(340);
    expect(layout.titleLines.length).toBe(1);
    expect(layout.attrRows[0].twoColumns).toBeTrue();
    expect(layout.opRows[0].lines.length).toBe(1);
  });

  it('el ancho por contenido nunca supera el máximo (340)', () => {
    expect(computeUmlClassMinWidth(cls({ name: 'X'.repeat(200) }), measure)).toBe(340);
  });

  it('respeta un ancho pedido mayor que el del contenido', () => {
    expect(computeUmlClassLayout(cls(), 500, measure).width).toBe(500);
  });

  it('todas las filas cuentan para el alto: no hay tope de filas', () => {
    const many = (n: number) => Array.from({ length: n }, (_, i) => attr(`a${i}`));
    const five = computeUmlClassLayout(cls({ attributes: many(5) }), 0, measure);
    const twenty = computeUmlClassLayout(cls({ attributes: many(20) }), 0, measure);
    expect(twenty.attrRows.length).toBe(20);
    expect(twenty.attrBlockHeight).toBe(20 * 22);
    expect(twenty.minHeight - five.minHeight).toBe(15 * 22);
  });

  it('una firma que no entra en el ancho máximo se envuelve y suma alto', () => {
    const one = computeUmlClassLayout(cls({ operations: [op('corta')] }), 0, measure);
    const wrapped = computeUmlClassLayout(
      cls({ operations: [op('emitirComprobanteFiscal', 'String', LONG_PARAMS)] }),
      0,
      measure,
    );
    expect(wrapped.width).toBe(340);
    expect(wrapped.opRows[0].lines.length).toBeGreaterThan(1);
    expect(wrapped.opRows[0].height).toBe(wrapped.opRows[0].lines.length * 16 + 6);
    expect(wrapped.minHeight).toBeGreaterThan(one.minHeight);
    for (const line of wrapped.opRows[0].lines) expect(measure(line)).toBeLessThanOrEqual(340 - 20);
  });

  it('un nombre más largo que el máximo agranda el encabezado con varias líneas', () => {
    const layout = computeUmlClassLayout(
      cls({ name: 'FacturacionElectronica'.repeat(4) }),
      0,
      measure,
    );
    expect(layout.titleLines.length).toBeGreaterThan(1);
    expect(layout.headerHeight).toBe(layout.titleLines.length * 18 + 14);
  });

  it('un atributo que entra queda en dos columnas; uno que no, se envuelve', () => {
    const layout = computeUmlClassLayout(
      cls({
        attributes: [
          attr('id', 'Long'),
          attr('atributoConNombreExtremadamenteLargoParaProbar', 'BigDecimalPrecisionExtendida'),
        ],
      }),
      0,
      measure,
    );
    expect(layout.attrRows[0].twoColumns).toBeTrue();
    expect(layout.attrRows[0].height).toBe(22);
    expect(layout.attrRows[1].twoColumns).toBeFalse();
    expect(layout.attrRows[1].lines.length).toBeGreaterThan(1);
  });

  it('las filas y los compartimentos se apilan sin huecos ni solapes', () => {
    const layout = computeUmlClassLayout(
      cls({ attributes: [attr('a'), attr('b'), attr('c')], operations: [op('x'), op('y')] }),
      0,
      measure,
    );
    layout.attrRows.forEach((r, i) => {
      if (i > 0) expect(r.y).toBe(layout.attrRows[i - 1].y + layout.attrRows[i - 1].height);
    });
    expect(layout.sep2Y).toBe(layout.headerHeight + 10 + layout.attrBlockHeight + 6);
    expect(layout.opsStartY).toBe(layout.sep2Y + 10);
    expect(layout.minHeight).toBe(layout.opsStartY + layout.opsBlockHeight + 12);
    expect(layout.opRows[1].y).toBe(22);
  });
});

describe('hit-testing por geometría', () => {
  const layout = computeUmlClassLayout(
    cls({
      attributes: [attr('a')],
      operations: [op('corta'), op('emitirComprobanteFiscal', 'String', LONG_PARAMS), op('ultima')],
    }),
    0,
    measure,
  );

  it('cada línea de una fila (envuelta o no) resuelve a su operación', () => {
    expect(layout.opRows[1].lines.length).toBeGreaterThan(1);
    layout.opRows.forEach((_, i) => {
      const rect = operationRowRect(layout, i)!;
      expect(operationIndexAtY(layout, rect.y + 1)).toBe(i);
      expect(operationIndexAtY(layout, rect.y + rect.height - 1)).toBe(i);
    });
  });

  it('bajo la última fila resuelve a la última; sin operaciones no resuelve nada', () => {
    expect(operationIndexAtY(layout, layout.minHeight)).toBe(layout.opRows.length - 1);
    expect(operationIndexAtY(computeUmlClassLayout(cls(), 0, measure), 200)).toBe(-1);
  });

  it('el rect de una fila de atributo parte debajo del encabezado', () => {
    expect(attributeRowRect(layout, 0)!.y).toBe(layout.headerHeight + 10);
    expect(attributeRowRect(layout, 5)).toBeNull();
  });
});
