import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DbEngine } from '../../dashboard.service';
import { ScIconComponent, ScButtonComponent, ScInputComponent } from '../../../../shared/ui';

@Component({
  selector: 'sc-new-project-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, ScIconComponent, ScButtonComponent, ScInputComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './new-project-modal.component.html',
  styleUrl: './new-project-modal.component.css',
})
export class ScNewProjectModalComponent {
  @Input() isOpen: boolean = false;
  @Input() loading: boolean = false;

  @Output() onClose = new EventEmitter<void>();
  @Output() onCreate = new EventEmitter<{ name: string; engine: DbEngine }>();

  name: string = '';
  engine: DbEngine = 'postgresql';
  nameError: string | null = null;

  close(): void {
    this.name = '';
    this.engine = 'postgresql';
    this.nameError = null;
    this.onClose.emit();
  }

  submit(): void {
    const trimmed = this.name.trim();
    if (!trimmed) {
      this.nameError = 'El nombre del proyecto es obligatorio.';
      return;
    }
    if (trimmed.length < 3) {
      this.nameError = 'El nombre debe tener al menos 3 caracteres.';
      return;
    }

    this.nameError = null;
    this.onCreate.emit({ name: trimmed, engine: this.engine });
  }
}
