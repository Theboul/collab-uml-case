import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { UmlGraphService } from '../../infrastructure/x6/uml-graph.service';
import { UmlEditorFacade } from '../../application/uml-editor.facade';
import { ScIconComponent } from '../../../../shared/ui/icon/icon.component';
import { ScButtonComponent } from '../../../../shared/ui/button/button.component';
import { ScBadgeComponent } from '../../../../shared/ui/badge/badge.component';

@Component({
  selector: 'app-uml-palette',
  standalone: true,
  imports: [CommonModule, ScIconComponent, ScButtonComponent, ScBadgeComponent],
  templateUrl: './uml-palette.component.html',
  styleUrl: './uml-palette.component.css',
})
export class UmlPaletteComponent {
  private readonly graphService = inject(UmlGraphService);
  private readonly facade = inject(UmlEditorFacade);
  private readonly router = inject(Router);

  isImporting = false;

  startDragClass(event: MouseEvent): void {
    const target = event.currentTarget as HTMLElement;
    this.graphService.startDnd(target, event, `Clase_${Math.floor(Math.random() * 900 + 100)}`);
  }

  onClickClass(): void {
    this.facade.setMode('CREATE_CLASS');
  }

  exportXmi(): void {
    this.facade.exportXmi();
  }

  onImportFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    this.isImporting = true;
    this.facade.importXmi(file).subscribe({
      next: (res) => {
        this.isImporting = false;
        input.value = '';
        if (res.canvas.roomName) {
          this.router.navigate(['/diagram', res.canvas.roomName]);
        }
      },
      error: (err) => {
        this.isImporting = false;
        input.value = '';
        const msg = err?.error?.message || 'Error al importar el archivo XMI.';
        alert(`Error de importación: ${msg}`);
      },
    });
  }
}
