import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ScIconComponent } from '../icon/icon.component';
import { ScButtonComponent } from '../button/button.component';

@Component({
  selector: 'sc-empty-state',
  standalone: true,
  imports: [CommonModule, ScIconComponent, ScButtonComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './empty-state.component.html',
  styleUrl: './empty-state.component.css',
})
export class ScEmptyStateComponent {
  @Input() icon: string = 'folder_open';
  @Input() title: string = 'No hay proyectos aún';
  @Input() description: string = 'Comienza creando tu primer esquema o importando un archivo SQL DDL existente.';
  @Input() actionLabel?: string = 'Crear tu primer proyecto';

  @Output() onAction = new EventEmitter<void>();
}
