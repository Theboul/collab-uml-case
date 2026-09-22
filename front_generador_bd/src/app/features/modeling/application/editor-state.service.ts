import { Injectable, signal } from '@angular/core';
import {
  DiagramLayout,
  EditorMode,
  LienzoDetailDto,
  ModeloUML,
  UmlClassDto,
  UmlRelationDto,
  UmlRelationType,
  ValidationResponseDto,
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

  /** CU6: panel de asistente IA (texto/voz -> comandos reales). */
  readonly isAssistantPanelOpen = signal<boolean>(false);
  readonly isAssistantProcessing = signal<boolean>(false);
  readonly assistantError = signal<string | null>(null);
  readonly assistantMessage = signal<string | null>(null);

  readonly model = signal<ModeloUML>({ classes: [], relations: [] });
  readonly layout = signal<DiagramLayout>({
    viewport: { zoom: 1, panX: 0, panY: 0 },
    nodes: {},
    links: {},
  });

  readonly contextMenu = signal<ContextMenuState | null>(null);

  /** CU9: resultado de la última validación del modelo persistido (UMLValidator real). */
  readonly validationResult = signal<ValidationResponseDto | null>(null);
  readonly isValidating = signal<boolean>(false);
  readonly isValidationPanelOpen = signal<boolean>(false);

  /** CU10: generación real del backend Spring Boot a partir del modelo persistido. */
  readonly isGeneratingSpringBackend = signal<boolean>(false);
  readonly springGenerationError = signal<string | null>(null);

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

  setValidating(validating: boolean): void {
    this.isValidating.set(validating);
  }

  setValidationResult(result: ValidationResponseDto): void {
    this.validationResult.set(result);
    this.isValidationPanelOpen.set(true);
  }

  toggleValidationPanel(): void {
    this.isValidationPanelOpen.set(!this.isValidationPanelOpen());
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

  openAssistantPanel(): void {
    this.assistantError.set(null);
    this.assistantMessage.set(null);
    this.isAssistantPanelOpen.set(true);
  }

  closeAssistantPanel(): void {
    this.isAssistantPanelOpen.set(false);
  }

  toggleAssistantPanel(): void {
    if (this.isAssistantPanelOpen()) {
      this.closeAssistantPanel();
    } else {
      this.openAssistantPanel();
    }
  }

  setAssistantProcessing(processing: boolean): void {
    this.isAssistantProcessing.set(processing);
  }

  setAssistantError(message: string | null): void {
    this.assistantError.set(message);
  }

  setAssistantMessage(message: string | null): void {
    this.assistantMessage.set(message);
  }

  setGeneratingSpringBackend(generating: boolean): void {
    this.isGeneratingSpringBackend.set(generating);
  }

  setSpringGenerationError(message: string | null): void {
    this.springGenerationError.set(message);
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

  hasRelationBetween(classIdA: string, classIdB: string): boolean {
    const relations = this.model().relations || [];
    return relations.some((r) => {
      const src = r.sourceClassId;
      const tgt = r.targetClassId;
      return (src === classIdA && tgt === classIdB) || (src === classIdB && tgt === classIdA);
    });
  }
}
