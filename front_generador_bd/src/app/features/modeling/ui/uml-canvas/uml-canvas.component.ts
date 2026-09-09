import {
  AfterViewInit,
  Component,
  ElementRef,
  HostListener,
  Inject,
  OnDestroy,
  PLATFORM_ID,
  ViewChild,
  inject,
} from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { UmlGraphService } from '../../infrastructure/x6/uml-graph.service';
import { UmlEditorFacade } from '../../application/uml-editor.facade';

export interface InlineEditState {
  visible: boolean;
  targetType: 'class' | 'attribute' | 'operation';
  nodeId: string;
  targetId?: string;
  name: string;
  type?: string;
  originalName: string;
  originalType?: string;
  x: number;
  y: number;
  width: number;
}

@Component({
  selector: 'app-uml-canvas',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './uml-canvas.component.html',
  styleUrl: './uml-canvas.component.css',
})
export class UmlCanvasComponent implements AfterViewInit, OnDestroy {
  @ViewChild('canvasContainer', { static: true })
  containerRef!: ElementRef<HTMLDivElement>;

  @ViewChild('inlineInput')
  inlineInputRef?: ElementRef<HTMLInputElement>;

  readonly facade = inject(UmlEditorFacade);
  readonly graphService = inject(UmlGraphService);

  isSpacePressed = false;
  isPanningActive = false;

  inlineEditState: InlineEditState | null = null;
  private dblClickSub?: Subscription;
  private focusOutTimer?: ReturnType<typeof setTimeout>;

  constructor(@Inject(PLATFORM_ID) private platformId: Object) {}

  ngAfterViewInit(): void {
    if (isPlatformBrowser(this.platformId)) {
      this.graphService.initGraph(this.containerRef.nativeElement);
      this.facade.renderLoadedModel();

      this.dblClickSub = this.graphService.nodeDblClick$.subscribe((event) => {
        const graph = this.graphService.rawGraph;
        if (!graph) return;
        const node = graph.getCellById(event.nodeId);
        if (!node || !node.isNode()) return;

        const bbox = node.getBBox();
        const clientPos = graph.localToClient(bbox.x, bbox.y + event.itemRelY);
        const containerRect = this.containerRef.nativeElement.getBoundingClientRect();
        const zoom = graph.zoom() || 1;

        const left = Math.max(10, clientPos.x - containerRect.left + (8 * zoom));
        const top = Math.max(10, clientPos.y - containerRect.top);
        const width = Math.max(160, (bbox.width - 16) * zoom);

        clearTimeout(this.focusOutTimer);
        this.inlineEditState = {
          visible: true,
          targetType: event.targetType,
          nodeId: event.nodeId,
          targetId: event.targetId,
          name: event.name,
          type: event.type,
          originalName: event.name,
          originalType: event.type,
          x: left,
          y: top,
          width,
        };

        setTimeout(() => {
          this.inlineInputRef?.nativeElement?.focus();
          this.inlineInputRef?.nativeElement?.select();
        }, 35);
      });
    }
  }

  commitInlineEdit(): void {
    clearTimeout(this.focusOutTimer);
    if (!this.inlineEditState) return;
    const { targetType, nodeId, targetId, name, type, originalName, originalType } = this.inlineEditState;
    const trimmedName = (name || '').trim();
    const trimmedType = (type || '').trim();
    this.inlineEditState = null;

    if (!trimmedName) return;

    if (targetType === 'class') {
      if (trimmedName !== originalName) {
        this.facade.updateClassName(nodeId, trimmedName);
      }
    } else if (targetType === 'attribute' && targetId) {
      if (trimmedName !== originalName || trimmedType !== (originalType || '')) {
        this.facade.updateAttribute(nodeId, targetId, {
          name: trimmedName,
          type: trimmedType || 'String',
        });
      }
    } else if (targetType === 'operation' && targetId) {
      if (trimmedName !== originalName || trimmedType !== (originalType || '')) {
        this.facade.updateOperation(nodeId, targetId, {
          name: trimmedName,
          returnType: trimmedType || 'void',
        });
      }
    }
  }

  cancelInlineEdit(): void {
    clearTimeout(this.focusOutTimer);
    this.inlineEditState = null;
  }

  onInlineFocusOut(event: FocusEvent): void {
    const container = event.currentTarget as HTMLElement;
    const nextTarget = event.relatedTarget as HTMLElement | null;
    if (nextTarget && container.contains(nextTarget)) {
      return;
    }
    clearTimeout(this.focusOutTimer);
    this.focusOutTimer = setTimeout(() => {
      if (document.activeElement && container.contains(document.activeElement)) {
        return;
      }
      this.commitInlineEdit();
    }, 150);
  }

  @HostListener('window:keydown', ['$event'])
  handleKeyDown(event: KeyboardEvent): void {
    // Si estamos en edición inline
    if (this.inlineEditState?.visible) {
      if (event.key === 'Enter') {
        event.preventDefault();
        this.commitInlineEdit();
        return;
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        this.cancelInlineEdit();
        return;
      }
      return;
    }

    // Guard exhaustivo: nunca capturar teclas si el foco está en un control de entrada o edición
    const target = event.target as HTMLElement | null;
    const activeEl = document.activeElement as HTMLElement | null;
    const isInteractive =
      (target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable ||
          target.closest('input, textarea, select, [contenteditable="true"]') !== null)) ||
      (activeEl &&
        (activeEl.tagName === 'INPUT' ||
          activeEl.tagName === 'TEXTAREA' ||
          activeEl.tagName === 'SELECT' ||
          activeEl.isContentEditable ||
          activeEl.closest('input, textarea, select, [contenteditable="true"]') !== null));

    if (isInteractive) {
      return;
    }

    // Mantener espacio -> Activa modo paneo y bloquea selección
    if (event.code === 'Space' && !this.isSpacePressed) {
      this.isSpacePressed = true;
      this.isPanningActive = true;
      this.graphService.setPanning(true);
      event.preventDefault();
      return;
    }

    // Escape -> Prioridad: deseleccionar subelemento; si no hay, modo SELECT y cerrar menú contextual
    if (event.key === 'Escape') {
      if (this.facade.selectedSubElement()) {
        this.facade.clearSubElement();
        return;
      }
      this.facade.setMode('SELECT');
      this.facade.closeContextMenu();
      return;
    }

    // Delete / Backspace -> Prioridad: eliminar subelemento seleccionado (Atributo u Operación) sin borrar la clase
    if (event.key === 'Delete' || event.key === 'Backspace') {
      event.preventDefault();
      const sub = this.facade.selectedSubElement();
      if (sub) {
        if (sub.type === 'attribute') {
          this.facade.deleteAttribute(sub.classId, sub.elementId);
        } else if (sub.type === 'operation') {
          this.facade.deleteOperation(sub.classId, sub.elementId);
        }
        this.facade.clearSubElement();
        return;
      }
      this.facade.deleteSelected();
      return;
    }

    // Undo: Ctrl/Cmd + Z
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z' && !event.shiftKey) {
      event.preventDefault();
      this.facade.undo();
      return;
    }

    // Redo: Ctrl/Cmd + Shift + Z  o  Ctrl + Y
    if (
      ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z' && event.shiftKey) ||
      ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y')
    ) {
      event.preventDefault();
      this.facade.redo();
      return;
    }
  }

  @HostListener('window:keyup', ['$event'])
  handleKeyUp(event: KeyboardEvent): void {
    if (event.code === 'Space') {
      this.isSpacePressed = false;
      this.isPanningActive = false;
      this.graphService.setPanning(false);
    }
  }

  ngOnDestroy(): void {
    clearTimeout(this.focusOutTimer);
    this.dblClickSub?.unsubscribe();
    if (isPlatformBrowser(this.platformId)) {
      this.graphService.dispose();
    }
  }
}
