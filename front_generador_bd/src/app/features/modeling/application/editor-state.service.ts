import { Injectable, signal } from '@angular/core';
import {
  DiagramLayout,
  EditorMode,
  LienzoDetailDto,
  ModeloUML,
  UmlClassDto,
  UmlRelationDto,
  UmlRelationType,
} from '../domain/models/uml-editor.models';

export interface ContextMenuState {
  visible: boolean;
  edgeId: string;
  x: number;
  y: number;
}

@Injectable({
  providedIn: 'root',
})
export class EditorStateService {
  readonly canvasId = signal<string | null>(null);
  readonly canvasName = signal<string>('Diagrama Sin Título');
  readonly roomName = signal<string | null>(null);
  readonly role = signal<'ANFITRION' | 'COLABORADOR' | 'INVITADO'>('COLABORADOR');
  readonly version = signal<number>(1);
  readonly mode = signal<EditorMode>('SELECT');
  readonly defaultRelationType = signal<UmlRelationType>('ASSOCIATION');

  readonly isLoading = signal<boolean>(true);
  readonly loadError = signal<string | null>(null);
  readonly isSaving = signal<boolean>(false);
  readonly lastSaved = signal<Date | null>(null);
  readonly isShareModalOpen = signal<boolean>(false);

  readonly model = signal<ModeloUML>({ classes: [], relations: [] });
  readonly layout = signal<DiagramLayout>({
    viewport: { zoom: 1, panX: 0, panY: 0 },
    nodes: {},
    links: {},
  });

  readonly contextMenu = signal<ContextMenuState | null>(null);

  setCanvasMetadata(dto: LienzoDetailDto): void {
    this.canvasId.set(dto.id);
    this.canvasName.set(dto.name);
    this.roomName.set(dto.roomName ?? null);
    this.role.set(dto.role || 'COLABORADOR');
    this.version.set(dto.version);
  }

  setSnapshot(model: ModeloUML, layout: DiagramLayout): void {
    this.model.set(model);
    this.layout.set(layout);
  }

  setMode(mode: EditorMode): void {
    this.mode.set(mode);
  }

  setDefaultRelationType(type: UmlRelationType): void {
    this.defaultRelationType.set(type);
  }

  setSaving(saving: boolean): void {
    this.isSaving.set(saving);
    if (!saving) {
      this.lastSaved.set(new Date());
    }
  }

  setVersion(ver: number): void {
    this.version.set(ver);
  }

  openShareModal(): void {
    this.isShareModalOpen.set(true);
  }

  closeShareModal(): void {
    this.isShareModalOpen.set(false);
  }

  openContextMenu(edgeId: string, x: number, y: number): void {
    this.contextMenu.set({ visible: true, edgeId, x, y });
  }

  closeContextMenu(): void {
    this.contextMenu.set(null);
  }

  updateClasses(updater: (classes: UmlClassDto[]) => UmlClassDto[]): void {
    const current = this.model();
    this.model.set({
      ...current,
      classes: updater(current.classes),
    });
  }

  updateRelations(updater: (relations: UmlRelationDto[]) => UmlRelationDto[]): void {
    const current = this.model();
    this.model.set({
      ...current,
      relations: updater(current.relations),
    });
  }
}
