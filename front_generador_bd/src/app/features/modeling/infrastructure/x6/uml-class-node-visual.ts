import type { Node } from '@antv/x6';
import { UML_NODE_DIMENSIONS as D, UmlParameter } from '../../domain/models/uml-editor.models';
import { UmlClassLayout, computeUmlClassLayout } from './uml-class-node-layout';

/**
 * Punto único de cálculo del contenido visual del nodo de clase (texto de encabezado,
 * geometría de separadores y compartimentos). Usado por `UmlGraphService.addNode`,
 * `UmlGraphService.updateNodeData`, `UmlDiagramAdapterService.modelToCells` y
 * `UmlGraphReconciliationService`.
 *
 * Los atributos y las operaciones ya no son texto declarativo de X6: son filas SVG
 * reales que pinta `UmlAttributeRowsService` a partir de `layout` (ver
 * `uml-class-node-layout.ts`). Acá solo se traduce ese layout a los `attrs` del shape
 * registrado (encabezado, título, separadores y posición de cada compartimento).
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

/** `Cell.attrs` de X6 es `{ [selector]: { [attr]: valor } }`. */
export type UmlClassNodeVisualAttrs = Record<string, Record<string, string | number>>;

export interface UmlClassNodeVisual {
  attrs: UmlClassNodeVisualAttrs;
  layout: UmlClassLayout;
  /** Ancho final del nodo (el pedido, o el mínimo por contenido si es mayor). */
  width: number;
  /** Ancho mínimo por contenido, entre MIN_WIDTH y MAX_WIDTH. */
  minWidth: number;
  /** Alto mínimo del nodo para mostrar todo el contenido, en el `width` calculado. */
  minHeight: number;
}

/** Alto de los separadores: el 1 es el trazo fuerte bajo el encabezado; el 2, el tenue entre atributos y operaciones. */
const SEPARATOR1_THICKNESS = 1.5;
const SEPARATOR2_THICKNESS = 1.5;
/** Alto del rect que aplana las esquinas inferiores redondeadas del encabezado. */
const HEADER_CAP_HEIGHT = 4;

/**
 * @param requestedWidth ancho actual/persistido del nodo; el resultado nunca es menor
 *   que lo que pide el contenido (hasta MAX_WIDTH).
 */
export function buildUmlClassNodeVisual(
  data: UmlClassNodeVisualInput,
  requestedWidth = 0,
): UmlClassNodeVisual {
  const layout = computeUmlClassLayout(
    {
      name: data.name ?? '',
      isAbstract: !!data.isAbstract,
      attributes: data.attributes || [],
      operations: data.operations || [],
    },
    requestedWidth,
  );

  return {
    attrs: {
      title: { text: layout.titleLines.join('\n'), refY: layout.headerHeight / 2 },
      header: { height: layout.headerHeight },
      headerCap: { y: layout.headerHeight - HEADER_CAP_HEIGHT },
      separator1: { y: layout.headerHeight - SEPARATOR1_THICKNESS / 2 },
      attributeRows: { refY: layout.headerHeight + D.SEP_PADDING },
      separator2: { y: layout.sep2Y - SEPARATOR2_THICKNESS / 2 },
      operationRows: { refY: layout.opsStartY },
    },
    layout,
    width: layout.width,
    minWidth: layout.minWidth,
    minHeight: layout.minHeight,
  };
}

/** Aplica los `attrs` calculados a un nodo ya creado (misma escritura para todos los caminos de actualización). */
export function applyUmlClassVisual(node: Node, visual: UmlClassNodeVisual): void {
  for (const [selector, props] of Object.entries(visual.attrs)) {
    for (const [prop, value] of Object.entries(props)) {
      node.setAttrByPath(`${selector}/${prop}`, value);
    }
  }
}
