/**
 * Delta de un lienzo (contrato `contracts/canvas-delta.v1.json`, ADR-0003 Addendum): lo que cambió
 * entre dos versiones consecutivas, por elemento. Una clase o relación nueva o modificada viaja
 * completa (`upsert`, en la forma del cable) y una borrada viaja como id (`remove`).
 *
 * Todo este archivo es puro: `applyCanvasDelta` recibe el contenido actual y devuelve el nuevo,
 * sin tocar señales, X6 ni HTTP. Quien lo llama decide cuándo aplicarlo (ver RemoteCanvasSyncService).
 */

import {
  DiagramLayout,
  ModeloUML,
  UmlClassDto,
  UmlRelationDto,
  UmlRelationType,
} from './models/uml-editor.models';

export interface ElementChange<T> {
  upsert?: T[];
  remove?: string[];
}

export interface KeyedChange<T> {
  set?: Record<string, T>;
  remove?: string[];
}

/** Un elemento de relación tal como viaja por el cable (`UmlModelSchema`), aún sin normalizar. */
export interface WireElement {
  id: string;
}

export interface CanvasDelta {
  model?: {
    classes?: ElementChange<UmlClassDto>;
    associations?: ElementChange<WireElement>;
    generalizations?: ElementChange<WireElement>;
    realizations?: ElementChange<WireElement>;
    dependencies?: ElementChange<WireElement>;
  };
  layout?: {
    nodes?: KeyedChange<DiagramLayout['nodes'][string]>;
    links?: KeyedChange<DiagramLayout['links'][string]>;
    viewport?: DiagramLayout['viewport'] | null;
  };
}

/** El mensaje completo que difunde el servidor tras confirmar un cambio. */
export interface CanvasDeltaMessage {
  type: 'canvas_delta';
  fromVersion: number;
  toVersion: number;
  delta: CanvasDelta;
}

/** Lo que un delta modifica de un lienzo: el modelo semántico y su diseño visual. */
export interface CanvasContent {
  model: ModeloUML;
  layout: DiagramLayout;
}

/** Relaciones del cable agrupadas por tipo de elemento, como las lee `UmlApiService`. */
export interface WireRelations {
  associations?: WireElement[];
  generalizations?: WireElement[];
  dependencies?: WireElement[];
}

/** Convierte relaciones del cable al `UmlRelationDto` del dominio del editor. */
export type NormalizeRelations = (wire: WireRelations) => UmlRelationDto[];

type RelationGroup = keyof WireRelations;

const RELATION_GROUPS: readonly RelationGroup[] = [
  'associations',
  'generalizations',
  'dependencies',
];

const GROUP_OF_TYPE: Record<UmlRelationType, RelationGroup> = {
  ASSOCIATION: 'associations',
  AGGREGATION: 'associations',
  COMPOSITION: 'associations',
  GENERALIZATION: 'generalizations',
  DEPENDENCY: 'dependencies',
};

/** Solo un mensaje con versiones enteras y un delta objeto se puede aplicar o encadenar. */
export function isCanvasDeltaMessage(value: unknown): value is CanvasDeltaMessage {
  if (typeof value !== 'object' || value === null) return false;
  const message = value as Partial<CanvasDeltaMessage>;
  return (
    message.type === 'canvas_delta' &&
    Number.isInteger(message.fromVersion) &&
    Number.isInteger(message.toVersion) &&
    typeof message.delta === 'object' &&
    message.delta !== null
  );
}

/** Contenido resultante de aplicar `delta` a `current`. No muta `current`. */
export function applyCanvasDelta(
  current: CanvasContent,
  delta: CanvasDelta,
  normalizeRelations: NormalizeRelations,
): CanvasContent {
  return {
    model: applyModelChange(current.model, delta.model, normalizeRelations),
    layout: applyLayoutChange(current.layout, delta.layout),
  };
}

function applyModelChange(
  model: ModeloUML,
  change: CanvasDelta['model'],
  normalizeRelations: NormalizeRelations,
): ModeloUML {
  if (!change) return model;
  return {
    classes: change.classes ? applyElementChange(model.classes, change.classes) : model.classes,
    relations: applyRelationsChange(model.relations, change, normalizeRelations),
  };
}

function applyRelationsChange(
  relations: UmlRelationDto[],
  change: NonNullable<CanvasDelta['model']>,
  normalizeRelations: NormalizeRelations,
): UmlRelationDto[] {
  if (!RELATION_GROUPS.some((group) => change[group])) return relations;

  // El editor guarda las relaciones en una sola lista, pero el servidor las ordena por tipo
  // (asociaciones, generalizaciones, dependencias): se separan para aplicar cada cambio en su
  // grupo y se vuelven a juntar en ese orden. Las realizaciones no se muestran en el editor.
  const groups: Record<RelationGroup, UmlRelationDto[]> = {
    associations: [],
    generalizations: [],
    dependencies: [],
  };
  for (const relation of relations) groups[GROUP_OF_TYPE[relation.type]].push(relation);

  for (const group of RELATION_GROUPS) {
    const groupChange = change[group];
    if (!groupChange) continue;
    const upsert = groupChange.upsert?.length
      ? normalizeRelations({ [group]: groupChange.upsert })
      : [];
    groups[group] = applyElementChange(groups[group], { upsert, remove: groupChange.remove });
  }
  return RELATION_GROUPS.flatMap((group) => groups[group]);
}

/** Quita los `remove`, reemplaza en su sitio los `upsert` que ya existen y agrega al final los nuevos. */
function applyElementChange<T extends { id: string }>(items: T[], change: ElementChange<T>): T[] {
  const removed = new Set(change.remove ?? []);
  const result = items.filter((item) => !removed.has(item.id));
  const position = new Map(result.map((item, index) => [item.id, index]));
  for (const element of change.upsert ?? []) {
    const at = position.get(element.id);
    if (at === undefined) {
      position.set(element.id, result.length);
      result.push(element);
    } else {
      result[at] = element;
    }
  }
  return result;
}

function applyLayoutChange(layout: DiagramLayout, change: CanvasDelta['layout']): DiagramLayout {
  if (!change) return layout;
  return {
    viewport: change.viewport ?? layout.viewport,
    nodes: applyKeyedChange(layout.nodes, change.nodes),
    links: applyKeyedChange(layout.links, change.links),
  };
}

function applyKeyedChange<T>(items: Record<string, T>, change?: KeyedChange<T>): Record<string, T> {
  if (!change) return items;
  const removed = new Set(change.remove ?? []);
  // `fromEntries` crea propiedades propias: una clave como `__proto__` no toca el prototipo.
  return Object.fromEntries([
    ...Object.entries(items).filter(([key]) => !removed.has(key)),
    ...Object.entries(change.set ?? {}),
  ]);
}
