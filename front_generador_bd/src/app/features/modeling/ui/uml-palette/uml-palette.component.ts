import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { UmlGraphService } from '../../infrastructure/x6/uml-graph.service';
import { UmlEditorFacade } from '../../application/uml-editor.facade';
import { ScIconComponent } from '../../../../shared/ui/icon/icon.component';
import { ScBadgeComponent } from '../../../../shared/ui/badge/badge.component';

@Component({
  selector: 'app-uml-palette',
  standalone: true,
  imports: [CommonModule, ScIconComponent, ScBadgeComponent],
  templateUrl: './uml-palette.component.html',
  styleUrl: './uml-palette.component.css',
})
export class UmlPaletteComponent {
  private readonly graphService = inject(UmlGraphService);
  private readonly facade = inject(UmlEditorFacade);

  startDragClass(event: MouseEvent): void {
    const target = event.currentTarget as HTMLElement;
    this.graphService.startDnd(target, event, `Clase_${Math.floor(Math.random() * 900 + 100)}`);
  }

  onClickClass(): void {
    this.facade.setMode('CREATE_CLASS');
  }
}
