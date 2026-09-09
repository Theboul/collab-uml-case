import { UmlMultiplicity, UmlParameter, UmlRelationType, VisibilityKind } from '../models/uml-editor.models';

export type EditorCommandType =
  | 'CREATE_CLASS'
  | 'UPDATE_CLASS_NAME'
  | 'DELETE_ELEMENTS'
  | 'RESTORE_ELEMENTS'
  | 'ADD_ATTRIBUTE'
  | 'UPDATE_ATTRIBUTE'
  | 'DELETE_ATTRIBUTE'
  | 'ADD_OPERATION'
  | 'UPDATE_OPERATION'
  | 'DELETE_OPERATION'
  | 'ADD_PARAMETER'
  | 'UPDATE_PARAMETER'
  | 'DELETE_PARAMETER'
  | 'MOVE_ELEMENT'
  | 'RESIZE_ELEMENT'
  | 'CREATE_RELATION'
  | 'UPDATE_RELATION'
  | 'UPDATE_MULTIPLICITY'
  | 'DELETE_ELEMENT'
  | 'DELETE_RELATION'
  | 'UPDATE_VIEWPORT'
  | 'UPDATE_RELATION_LAYOUT'
  | 'UPDATE_RELATION_VERTICES';

export interface EditorCommand<T = any> {
  operationId: string;
  expectedVersion: number;
  type: EditorCommandType | string;
  payload: T;
}

export interface CreateClassPayload {
  classId?: string;
  name: string;
  isAbstract?: boolean;
  x: number;
  y: number;
  width?: number;
  height?: number;
}

export interface MoveElementPayload {
  elementId: string;
  x: number;
  y: number;
}

export interface ResizeElementPayload {
  elementId: string;
  width: number;
  height: number;
  x?: number;
  y?: number;
}

export interface CreateRelationPayload {
  relationId?: string;
  type: UmlRelationType;
  sourceClassId: string;
  targetClassId: string;
  sourceRole?: string | null;
  targetRole?: string | null;
  sourceMultiplicity?: UmlMultiplicity | string;
  targetMultiplicity?: UmlMultiplicity | string;
  name?: string | null;
}

export interface UpdateRelationPayload {
  relationId: string;
  type?: UmlRelationType;
  sourceMultiplicity?: UmlMultiplicity | string;
  targetMultiplicity?: UmlMultiplicity | string;
  sourceRole?: string | null;
  targetRole?: string | null;
  name?: string | null;
}

export interface UpdateMultiplicityPayload {
  relationId: string;
  sourceMultiplicity?: UmlMultiplicity | string;
  targetMultiplicity?: UmlMultiplicity | string;
}

export interface DeleteElementPayload {
  elementId: string;
}

export interface UpdateClassNamePayload {
  classId: string;
  name: string;
  isAbstract?: boolean;
}

export interface DeleteElementsPayload {
  classIds: string[];
}

export interface RestoreElementsPayload {
  classes?: any[];
  relations?: any[];
  generalizations?: any[];
  layouts?: any[];
}

export interface AddAttributePayload {
  classId: string;
  attributeId?: string;
  id?: string;
  name: string;
  type: string;
  visibility?: VisibilityKind | string;
  isStatic?: boolean;
}

export interface UpdateAttributePayload {
  classId: string;
  attributeId: string;
  name?: string;
  type?: string;
  visibility?: VisibilityKind | string;
  isStatic?: boolean;
}

export interface DeleteAttributePayload {
  classId: string;
  attributeId: string;
}

export interface AddOperationPayload {
  classId: string;
  operationId?: string;
  id?: string;
  name: string;
  returnType: string;
  visibility?: VisibilityKind | string;
  parameters?: UmlParameter[];
  isStatic?: boolean;
  isAbstract?: boolean;
}

export interface UpdateOperationPayload {
  classId: string;
  operationId: string;
  name?: string;
  returnType?: string;
  visibility?: VisibilityKind | string;
  isStatic?: boolean;
  isAbstract?: boolean;
}

export interface DeleteOperationPayload {
  classId: string;
  operationId: string;
}

export interface AddParameterPayload {
  classId: string;
  operationId: string;
  parameterId?: string;
  id?: string;
  name: string;
  type: string;
}

export interface UpdateParameterPayload {
  classId: string;
  operationId: string;
  parameterId: string;
  name?: string;
  type?: string;
}

export interface DeleteParameterPayload {
  classId: string;
  operationId: string;
  parameterId: string;
}

export interface DeleteRelationPayload {
  relationId: string;
}

export interface UpdateViewportPayload {
  zoom: number;
  panX: number;
  panY: number;
}

export interface UpdateRelationLayoutPayload {
  relationId: string;
  sourcePort?: string;
  targetPort?: string;
}

export interface UpdateRelationVerticesPayload {
  relationId: string;
  vertices: Array<{ x: number; y: number }>;
}
