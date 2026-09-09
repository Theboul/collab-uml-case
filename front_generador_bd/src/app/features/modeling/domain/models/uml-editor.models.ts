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
}

export const UML_NODE_DIMENSIONS = {
  HEADER_HEIGHT: 32,
  TITLE_Y: 16,
  ATTR_START_Y: 42,
  LINE_HEIGHT: 16,
  SEP_PADDING: 10,
  BOTTOM_PADDING: 12,
  MIN_WIDTH: 180,
  MIN_HEIGHT: 110,
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


