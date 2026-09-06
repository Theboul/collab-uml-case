import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { UmlToolbarComponent } from './uml-toolbar/uml-toolbar.component';
import { UmlPaletteComponent } from './uml-palette/uml-palette.component';
import { UmlCanvasComponent } from './uml-canvas/uml-canvas.component';
import { RelationContextMenuComponent } from './relation-context-menu/relation-context-menu.component';
import { PropertiesPanelComponent } from './properties-panel/properties-panel.component';
import { UmlShareModalComponent } from './uml-share-modal/uml-share-modal.component';
import { UmlEditorFacade } from '../application/uml-editor.facade';
import { ScButtonComponent, ScIconComponent } from '../../../shared/ui';


@Component({
  selector: 'app-uml-editor',
  standalone: true,
  imports: [
    CommonModule,
    UmlToolbarComponent,
    UmlPaletteComponent,
    UmlCanvasComponent,
    RelationContextMenuComponent,
    PropertiesPanelComponent,
    UmlShareModalComponent,
    ScButtonComponent,
    ScIconComponent,
  ],
  templateUrl: './uml-editor.component.html',
  styleUrl: './uml-editor.component.css',
})
export class UmlEditorComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly facade = inject(UmlEditorFacade);

  currentRoomId = 'default-room';

  ngOnInit(): void {
    this.currentRoomId = this.route.snapshot.paramMap.get('roomId') || 'default-room';
    this.loadCurrentCanvas();
  }

  loadCurrentCanvas(): void {
    this.facade.loadCanvas(this.currentRoomId).subscribe({
      next: (canvas) => {
        console.log(`[UmlEditor] Lienzo cargado exitosamente: ${canvas.name} (v${canvas.version})`);
      },
      error: (err) => {
        console.error('[UmlEditor] Error al cargar snapshot del lienzo:', err);
      },
    });
  }

  retryLoad(): void {
    this.loadCurrentCanvas();
  }

  goToDashboard(): void {
    this.router.navigate(['/dashboard']);
  }
}

