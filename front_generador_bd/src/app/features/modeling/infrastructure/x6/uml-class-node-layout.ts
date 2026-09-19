import { UML_NODE_DIMENSIONS as D, UmlParameter } from '../../domain/models/uml-editor.models';
import { FIT_MARGIN, TextMeasure, UML_FONTS, measureTextWidth, wrapText } from './uml-text-measure';

/**
 * Geometría del nodo de clase UML, calculada como función pura de su contenido y de
 * su ancho. Es la única fuente de verdad para: el alto y el ancho mínimos del nodo,
 * cómo se envuelve cada texto, dónde cae cada fila y a qué elemento corresponde un
 * clic. El render (`UmlAttributeRowsService`), el hit-testing (`UmlInteractionService`)
 * y el resaltado de fila (`EditorSelectionService`) leen todos de acá, así lo dibujado
 * y lo clicable no pueden desalinearse.
 *
 * El nodo se adapta al contenido (ancho hasta `MAX_WIDTH`) y, lo que aun así no entra,
 * se envuelve en varias líneas que se suman al alto — sin scroll ni recorte.
 */
export interface UmlClassLayoutInput {
  name: string;
  isAbstract: boolean;
  attributes: { name: string; type: string; visibility: string }[];
  operations: {
    name: string;
    returnType: string;
    visibility: string;
    parameters?: UmlParameter[] | string;
  }[];
}

/** Fila de texto con su posición y alto. `y` es relativo al inicio de su compartimento. */
export interface UmlRowLayout {
  lines: string[];
  y: number;
  height: number;
}

export interface UmlAttributeRowLayout extends UmlRowLayout {
  /** true → columnas nombre (izquierda) | tipo (derecha); false → texto único envuelto. */
  twoColumns: boolean;
  /** Solo si `twoColumns`: nombre y tipo por separado. */
  name: string;
  type: string;
}

export interface UmlClassLayout {
  /** Ancho final del nodo: el pedido, o el mínimo por contenido si es mayor. */
  width: number;
  /** Ancho mínimo por contenido (entre MIN_WIDTH y MAX_WIDTH). */
  minWidth: number;
  titleLines: string[];
  headerHeight: number;
  attrRows: UmlAttributeRowLayout[];
  /** Alto del compartimento de atributos (al menos una fila, también vacío). */
  attrBlockHeight: number;
  sep2Y: number;
  opsStartY: number;
  opRows: UmlRowLayout[];
  /** Alto del compartimento de operaciones (al menos una fila, también vacío). */
  opsBlockHeight: number;
  /** Alto mínimo del nodo para mostrar todo el contenido. */
  minHeight: number;
}

export function formatOperationParams(parameters: UmlParameter[] | string | undefined): string {
  if (Array.isArray(parameters)) {
    return parameters.map((p) => `${p.name}: ${p.type}`).join(', ');
  }
  if (typeof parameters === 'string') {
    return parameters;
  }
  return '';
}

export function umlClassTitleText(input: Pick<UmlClassLayoutInput, 'name' | 'isAbstract'>): string {
  return input.name + (input.isAbstract ? ' {abstract}' : '');
}

function operationText(op: UmlClassLayoutInput['operations'][number]): string {
  return `${op.visibility || '+'} ${op.name}(${formatOperationParams(op.parameters)}) : ${op.returnType || 'void'}`;
}

function rowHeight(lineCount: number): number {
  return lineCount * D.WRAP_LINE_HEIGHT + D.ROW_V_PADDING;
}

/** Ancho que necesitaría el contenido sin envolver nada, acotado a [MIN_WIDTH, MAX_WIDTH]. */
function contentMinWidth(input: UmlClassLayoutInput, measure: TextMeasure): number {
  let needed = measure(umlClassTitleText(input), UML_FONTS.title) + 2 * D.TITLE_PADDING_X;

  for (const a of input.attributes) {
    const w =
      measure(`${a.visibility} ${a.name}`, UML_FONTS.mono) +
      D.ATTR_NAME_TYPE_GAP +
      measure(`: ${a.type}`, UML_FONTS.mono) +
      D.ATTR_PADDING_X +
      D.ATTR_ICON_RESERVE;
    needed = Math.max(needed, w);
  }
  for (const op of input.operations) {
    needed = Math.max(needed, measure(operationText(op), UML_FONTS.mono) + 2 * D.OP_PADDING_X);
  }
  // FIT_MARGIN: el mismo margen con el que `wrapText` decide si una línea entra; sin él, un
  // texto que justo cabe en el ancho mínimo se envolvería igual.
  return Math.min(D.MAX_WIDTH, Math.max(D.MIN_WIDTH, Math.ceil(needed + FIT_MARGIN)));
}

export function computeUmlClassMinWidth(
  input: UmlClassLayoutInput,
  measure: TextMeasure = measureTextWidth,
): number {
  return contentMinWidth(input, measure);
}

export function computeUmlClassLayout(
  input: UmlClassLayoutInput,
  requestedWidth = 0,
  measure: TextMeasure = measureTextWidth,
): UmlClassLayout {
  const minWidth = contentMinWidth(input, measure);
  const width = Math.max(requestedWidth, minWidth);

  const titleAvail = width - 2 * D.TITLE_PADDING_X;
  const titleLines = wrapText(
    umlClassTitleText(input),
    titleAvail,
    titleAvail,
    UML_FONTS.title,
    measure,
  );
  const headerHeight = Math.max(
    D.HEADER_HEIGHT,
    titleLines.length * D.TITLE_LINE_HEIGHT + D.HEADER_PADDING_Y,
  );

  const attrAvail = width - D.ATTR_PADDING_X - D.ATTR_ICON_RESERVE;
  let attrY = 0;
  const attrRows: UmlAttributeRowLayout[] = input.attributes.map((a) => {
    const name = `${a.visibility} ${a.name}`;
    const type = `: ${a.type}`;
    const twoColumns =
      measure(name, UML_FONTS.mono) + D.ATTR_NAME_TYPE_GAP + measure(type, UML_FONTS.mono) <=
      attrAvail;
    const lines = twoColumns
      ? [name]
      : wrapText(`${name} ${type}`, attrAvail, attrAvail - D.WRAP_INDENT, UML_FONTS.mono, measure);
    const height = twoColumns ? D.ATTR_ROW_HEIGHT : rowHeight(lines.length);
    const row: UmlAttributeRowLayout = { lines, y: attrY, height, twoColumns, name, type };
    attrY += height;
    return row;
  });
  const attrBlockHeight = Math.max(D.ATTR_ROW_HEIGHT, attrY);

  const opAvail = width - 2 * D.OP_PADDING_X;
  let opY = 0;
  const opRows: UmlRowLayout[] = input.operations.map((op) => {
    const lines = wrapText(
      operationText(op),
      opAvail,
      opAvail - D.WRAP_INDENT,
      UML_FONTS.mono,
      measure,
    );
    const row: UmlRowLayout = { lines, y: opY, height: rowHeight(lines.length) };
    opY += row.height;
    return row;
  });
  const opsBlockHeight = Math.max(D.LINE_HEIGHT, opY);

  const sep2Y = headerHeight + D.SEP_PADDING + attrBlockHeight + 6;
  const opsStartY = sep2Y + D.SEP_PADDING;
  const minHeight = Math.max(D.MIN_HEIGHT, opsStartY + opsBlockHeight + D.BOTTOM_PADDING);

  return {
    width,
    minWidth,
    titleLines,
    headerHeight,
    attrRows,
    attrBlockHeight,
    sep2Y,
    opsStartY,
    opRows,
    opsBlockHeight,
    minHeight,
  };
}

/** Rectángulo vertical (relativo al borde superior del nodo) de la fila de atributo `index`. */
export function attributeRowRect(
  layout: UmlClassLayout,
  index: number,
): { y: number; height: number } | null {
  const row = layout.attrRows[index];
  return row ? { y: layout.headerHeight + D.SEP_PADDING + row.y, height: row.height } : null;
}

/** Rectángulo vertical (relativo al borde superior del nodo) de la fila de operación `index`. */
export function operationRowRect(
  layout: UmlClassLayout,
  index: number,
): { y: number; height: number } | null {
  const row = layout.opRows[index];
  return row ? { y: layout.opsStartY + row.y, height: row.height } : null;
}

/**
 * Índice de la operación que ocupa la altura `relY` (relativa al borde superior del
 * nodo). Un clic en el padding entre filas o bajo la última resuelve a la más cercana.
 * -1 si la clase no tiene operaciones.
 */
export function operationIndexAtY(layout: UmlClassLayout, relY: number): number {
  if (layout.opRows.length === 0) return -1;
  const local = relY - layout.opsStartY;
  for (let i = 0; i < layout.opRows.length; i++) {
    const row = layout.opRows[i];
    if (local < row.y + row.height) return i;
  }
  return layout.opRows.length - 1;
}
