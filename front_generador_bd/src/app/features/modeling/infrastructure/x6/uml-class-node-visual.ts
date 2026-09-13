import { UmlParameter, UML_NODE_DIMENSIONS } from '../../domain/models/uml-editor.models';

/**
 * Punto único de cálculo del contenido visual del nodo de clase (texto de encabezado,
 * operaciones y geometría derivada). Usado por `UmlGraphService.addNode`,
 * `UmlGraphService.updateNodeData`, `UmlDiagramAdapterService.modelToCells` y
 * `UmlGraphReconciliationService` — antes esta lógica estaba triplicada entre esos
 * archivos.
 *
 * Fase 2: el compartimento de atributos pasó de un `<text>` con `\n` a filas SVG
 * reales (ver `UmlAttributeRowsService`), por eso ya no expone `attrs.attributes` —
 * expone `attrBlockHeight` (con tope en ATTR_MAX_VISIBLE_ROWS) para que tanto el
 * renderer de filas como el resto de la geometría del nodo (separador, operaciones)
 * usen el mismo número.
 */
export interface UmlClassNodeVisualInput {
  name: string;
  isAbstract: boolean;
  attributes: { id?: string; name: string; type: string; visibility: string }[];
  operations: {
    id?: string;
    name: string;
    returnType: string;
    visibility: string;
    parameters?: UmlParameter[] | string;
  }[];
}

export interface UmlClassNodeVisualAttrs {
  title: { text: string };
  separator2: { y1: number; y2: number };
  operations: { text: string; refY: number };
  // Índice requerido para asignar directamente a `Cell.attrs` de X6 (Attr.CellAttrs
  // es `{ [selector: string]: ComplexAttrs }`); las claves de arriba ya cubren
  // el contrato real, esto solo satisface la firma estructural de X6.
  [selector: string]: Record<string, string | number>;
}

export interface UmlClassNodeVisual {
  attrs: UmlClassNodeVisualAttrs;
  minHeight: number;
  /**
   * Alto del compartimento de atributos con tope en ATTR_MAX_VISIBLE_ROWS filas
   * (Fase 2 — filas reales con scroll interno, ver UmlAttributeRowsService). A
   * partir de ese tope el nodo deja de crecer con más atributos.
   */
  attrBlockHeight: number;
}

/** Cuántas filas de atributo se ven sin hacer scroll, para una cantidad de atributos dada. */
export function visibleAttributeRowCount(attributeCount: number): number {
  return Math.min(Math.max(1, attributeCount), UML_NODE_DIMENSIONS.ATTR_MAX_VISIBLE_ROWS);
}

function formatOperationParams(parameters: UmlParameter[] | string | undefined): string {
  if (Array.isArray(parameters)) {
    return parameters.map((p) => `${p.name}: ${p.type}`).join(', ');
  }
  if (typeof parameters === 'string') {
    return parameters;
  }
  return '';
}

export function buildUmlClassNodeVisual(data: UmlClassNodeVisualInput): UmlClassNodeVisual {
  const titleText = data.name + (data.isAbstract ? ' {abstract}' : '');

  const attributes = data.attributes || [];
  const attrBlockHeight = visibleAttributeRowCount(attributes.length) * UML_NODE_DIMENSIONS.ATTR_ROW_HEIGHT;

  const operations = data.operations || [];
  const opsList =
    operations.length > 0
      ? operations
          .map(
            (o) =>
              `${o.visibility || '+'} ${o.name}(${formatOperationParams(o.parameters)}) : ${o.returnType || 'void'}`,
          )
          .join('\n')
      : '';

  const sep2Y =
    UML_NODE_DIMENSIONS.HEADER_HEIGHT + UML_NODE_DIMENSIONS.SEP_PADDING + attrBlockHeight + 6;
  const opY = sep2Y + UML_NODE_DIMENSIONS.SEP_PADDING;
  const opHeight = Math.max(1, operations.length) * UML_NODE_DIMENSIONS.LINE_HEIGHT;
  const minHeight = Math.max(
    UML_NODE_DIMENSIONS.MIN_HEIGHT,
    opY + opHeight + UML_NODE_DIMENSIONS.BOTTOM_PADDING,
  );

  return {
    attrs: {
      title: { text: titleText },
      separator2: { y1: sep2Y, y2: sep2Y },
      operations: { text: opsList, refY: opY },
    },
    minHeight,
    attrBlockHeight,
  };
}
