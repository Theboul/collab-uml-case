import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { UmlEditorFacade } from '../../application/uml-editor.facade';
import { UmlRelationType } from '../../domain/models/uml-editor.models';
import { ScButtonComponent } from '../../../../shared/ui/button/button.component';
import { ScIconComponent } from '../../../../shared/ui/icon/icon.component';

@Component({
  selector: 'app-uml-toolbar',
  standalone: true,
  imports: [CommonModule, ScButtonComponent, ScIconComponent],
  templateUrl: './uml-toolbar.component.html',
  styleUrl: './uml-toolbar.component.css',
})
export class UmlToolbarComponent {
  readonly facade = inject(UmlEditorFacade);

  onRelationTypeChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.facade.setDefaultRelationType(select.value as UmlRelationType);
  }

  copyRoomCode(room: string): void {
    navigator.clipboard?.writeText(room);
  }
}
