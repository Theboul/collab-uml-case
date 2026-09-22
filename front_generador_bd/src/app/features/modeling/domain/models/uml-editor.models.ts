/**
 * Modelos canónicos para el módulo de modelado UML (SchemaCraft).
 * Fuente de verdad: AGENTS.md sección 4 y core/uml_domain.
 * Regla dura: X6 Graph JSON != ModeloUML.
 */

export type EditorMode = 'SELECT' | 'CREATE_CLASS' | 'CREATE_RELATION';

export type UmlRelationType =
  | 'ASSOCIATION'
  | 'AGGREGATION'
  | 'COMPOSITION'
  | 'DEPENDENCY'
  | 'GENERALIZATION';

export type UmlMultiplicity = '1' | '0..1' | '*' | '0..*' | '1..*';

export type VisibilityKind = '+' | '-' | '#' | '~';

export interface UmlParameter {
  id: string;
  name: string;
  type: string;
  direction?: 'in' | 'out' | 'inout' | 'return';
  defaultValue?: string;
}

export interface UmlAttribute {
  id: string;
  name: string;
  type: string;
  visibility: VisibilityKind;
  isStatic?: boolean;
}

export interface UmlOperation {
  id: string;
  name: string;
  returnType: string;
  visibility: VisibilityKind;
  parameters?: UmlParameter[] | string;
  isStatic?: boolean;
  isAbstract?: boolean;
}

export interface UmlClassDto {
  id: string;
  name: string;
  isAbstract: boolean;
  attributes: UmlAttribute[];
  operations: UmlOperation[];
}

export interface UmlRelationDto {
  id: string;
  name?: string | null;
  type: UmlRelationType;
  sourceClassId: string;
  targetClassId: string;
  sourceRole?: string | null;
  targetRole?: string | null;
  sourceMultiplicity: string;
  targetMultiplicity: string;
}

export interface ModeloUML {
  classes: UmlClassDto[];
  relations: UmlRelationDto[];
}

export interface NodeLayout {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DiagramLayout {
  viewport: {
    zoom: number;
    panX: number;
    panY: number;
  };
  nodes: Record<string, NodeLayout>;
  links: Record<
    string,
    {
      vertices?: Array<{ x: number; y: number }>;
      sourcePort?: string;
      targetPort?: string;
    }
  >;
}

export interface LienzoDetailDto {
  id: string;
  name: string;
  description: string | null;
  version: number;
  ownerId?: string | null;
  roomName?: string | null;
  role?: 'ANFITRION' | 'COLABORADOR' | 'INVITADO';
  visualLayout: DiagramLayout;
  model: ModeloUML;
}

export interface JoinCanvasResponse {
  workspaceId: string;
  canvasId: string;
  roomName: string;
  role: 'ANFITRION' | 'COLABORADOR' | 'INVITADO';
  joined: boolean;
}

export interface CommandResponseDto {
  accepted: boolean;
  version: number;
  operationId?: string;
  canvas?: LienzoDetailDto;
  undoPayload?: any;
  message?: string;
}

export const UML_NODE_DIMENSIONS = {
  HEADER_HEIGHT: 32,
  TITLE_Y: 16,
  ATTR_START_Y: 42,
  /** Alto de una fila de operación de una sola línea — igual a ATTR_ROW_HEIGHT para que
   *  ambos compartimentos tengan el mismo ritmo vertical. */
  LINE_HEIGHT: 22,
  SEP_PADDING: 10,
  BOTTOM_PADDING: 12,
  MIN_WIDTH: 180,
  /** Tope del ancho que el nodo toma solo según su contenido; más allá, el texto se envuelve. */
  MAX_WIDTH: 340,
  MIN_HEIGHT: 110,
  /** Alto de fila real de atributo (Fase 2) con fuente 12px y lugar para el ícono de eliminar. */
  ATTR_ROW_HEIGHT: 22,
  ATTR_FONT_SIZE: 12,
  /** Misma fuente que los atributos: los tres compartimentos comparten tamaño de texto. */
  OP_FONT_SIZE: 12,
  TITLE_FONT_SIZE: 13,
  TITLE_LINE_HEIGHT: 18,
  TITLE_PADDING_X: 16,
  /** Padding vertical total del encabezado (arriba + abajo) alrededor de las líneas del título. */
  HEADER_PADDING_Y: 14,
  /** Filas envueltas (atributo u operación con más de una línea): alto por línea y padding vertical.
   *  Una fila de una línea da 16 + 6 = ATTR_ROW_HEIGHT. */
  WRAP_LINE_HEIGHT: 16,
  ROW_V_PADDING: 6,
  /** Sangría de las líneas de continuación de una fila envuelta. */
  WRAP_INDENT: 12,
  ATTR_PADDING_X: 8,
  /** Espacio reservado a la derecha de la fila de atributo para el ícono de eliminar. */
  ATTR_ICON_RESERVE: 25,
  ATTR_NAME_TYPE_GAP: 8,
  OP_PADDING_X: 10,
} as const;

export interface SubElementSelection {
  type: 'attribute' | 'operation';
  classId: string;
  elementId: string;
}

export interface UmlNodeSubElementEvent {
  classId: string;
  type: 'class' | 'attribute' | 'operation';
  elementId?: string;
  name?: string;
  typeOrReturn?: string;
  visibility?: string;
  itemRelY: number;
  nodeBBox: { x: number; y: number; width: number; height: number };
  clientX: number;
  clientY: number;
}

/** CU9: resultado de validar el modelo persistido de un lienzo (UMLValidator real, no IA). */
export interface ValidationIssueDto {
  code: string;
  message: string;
  severity: 'ERROR' | 'WARNING';
  elementId: string | null;
}

export interface ValidationResponseDto {
  valid: boolean;
  errors: ValidationIssueDto[];
  warnings: ValidationIssueDto[];
}


