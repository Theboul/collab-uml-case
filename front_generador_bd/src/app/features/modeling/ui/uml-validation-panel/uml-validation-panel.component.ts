import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { UmlEditorFacade } from '../../application/uml-editor.facade';
import { ValidationIssueDto } from '../../domain/models/uml-editor.models';
import { ScButtonComponent } from '../../../../shared/ui/button/button.component';
import { ScIconComponent } from '../../../../shared/ui/icon/icon.component';

/**
 * CU9: panel de resultados de validación semántica del modelo (UMLValidator
 * real, vía POST /canvases/{id}/validate) — reemplaza al panel legacy que en
 * realidad consultaba a Gemini por WebSocket (ver auditoría CU9, hallazgo #1).
 * Sin resaltado avanzado en esta fase a propósito: prioridad a mostrar
 * resultados reales antes que UX pulida.
 */
@Component({
  selector: 'app-uml-validation-panel',
  standalone: true,
  imports: [CommonModule, ScButtonComponent, ScIconComponent],
  templateUrl: './uml-validation-panel.component.html',
  styleUrl: './uml-validation-panel.component.css',
})
export class UmlValidationPanelComponent {
  readonly facade = inject(UmlEditorFacade);

  closePanel(): void {
    this.facade.toggleValidationPanel();
  }

  revalidate(): void {
    this.facade.validateModel();
  }

  onIssueClick(issue: ValidationIssueDto): void {
    this.facade.focusIssue(issue.elementId);
  }
}
