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
import { isPlatformBrowser } from '@angular/common';
import { UmlGraphService } from '../../infrastructure/x6/uml-graph.service';
import { UmlEditorFacade } from '../../application/uml-editor.facade';

@Component({
  selector: 'app-uml-canvas',
  standalone: true,
  templateUrl: './uml-canvas.component.html',
  styleUrl: './uml-canvas.component.css',
})
export class UmlCanvasComponent implements AfterViewInit, OnDestroy {
  @ViewChild('canvasContainer', { static: true })
  containerRef!: ElementRef<HTMLDivElement>;

  readonly facade = inject(UmlEditorFacade);
  readonly graphService = inject(UmlGraphService);

  isSpacePressed = false;
  isPanningActive = false;

  constructor(@Inject(PLATFORM_ID) private platformId: Object) {}

  ngAfterViewInit(): void {
    if (isPlatformBrowser(this.platformId)) {
      this.graphService.initGraph(this.containerRef.nativeElement);
      this.facade.renderLoadedModel();
    }
  }

  @HostListener('window:keydown', ['$event'])
  handleKeyDown(event: KeyboardEvent): void {
    const target = event.target as HTMLElement;
    if (
      target &&
      (target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable)
    ) {
      return;
    }

    // Mantener espacio -> Activa modo paneo
    if (event.code === 'Space' && !this.isSpacePressed) {
      this.isSpacePressed = true;
      this.graphService.setPanning(true);
      event.preventDefault();
      return;
    }

    // Escape -> Modo Selección y cerrar menú contextual
    if (event.key === 'Escape') {
      this.facade.setMode('SELECT');
      this.facade.closeContextMenu();
      return;
    }

    // Delete / Backspace -> Eliminar seleccionados
    if (event.key === 'Delete' || event.key === 'Backspace') {
      event.preventDefault();
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
    if (isPlatformBrowser(this.platformId)) {
      this.graphService.dispose();
    }
  }
}
