import { UmlMultiplicity, UmlRelationType } from '../models/uml-editor.models';

export interface EditorCommand<T = any> {
  operationId: string;
  expectedVersion: number;
  type:
    | 'CREATE_CLASS'
    | 'MOVE_ELEMENT'
    | 'RESIZE_ELEMENT'
    | 'CREATE_RELATION'
    | 'UPDATE_RELATION'
    | 'UPDATE_MULTIPLICITY'
    | 'DELETE_ELEMENT'
    | 'DELETE_RELATION'
    | 'UPDATE_VIEWPORT';
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

export interface DeleteRelationPayload {
  relationId: string;
}

export interface UpdateViewportPayload {
  zoom: number;
  panX: number;
  panY: number;
}
