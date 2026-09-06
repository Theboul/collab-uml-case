import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { UmlToolbarComponent } from './uml-toolbar/uml-toolbar.component';
import { UmlPaletteComponent } from './uml-palette/uml-palette.component';
import { UmlCanvasComponent } from './uml-canvas/uml-canvas.component';
import { RelationContextMenuComponent } from './relation-context-menu/relation-context-menu.component';
import { PropertiesPanelComponent } from './properties-panel/properties-panel.component';
import { UmlShareModalComponent } from './uml-share-modal/uml-share-modal.component';
import { UmlEditorFacade } from '../application/uml-editor.facade';

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
  ],
  templateUrl: './uml-editor.component.html',
  styleUrl: './uml-editor.component.css',
})
export class UmlEditorComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  readonly facade = inject(UmlEditorFacade);

  ngOnInit(): void {
    const roomId = this.route.snapshot.paramMap.get('roomId') || 'default-room';
    this.facade.loadCanvas(roomId).subscribe({
      next: (canvas) => {
        console.log(`[UmlEditor] Lienzo cargado exitosamente: ${canvas.name} (v${canvas.version})`);
      },
      error: (err) => {
        console.error('[UmlEditor] Error al cargar lienzo:', err);
      },
    });
  }
}
