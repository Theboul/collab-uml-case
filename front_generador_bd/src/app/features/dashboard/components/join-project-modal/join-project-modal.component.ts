import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ScIconComponent, ScButtonComponent, ScInputComponent } from '../../../../shared/ui';

@Component({
  selector: 'sc-join-project-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, ScIconComponent, ScButtonComponent, ScInputComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './join-project-modal.component.html',
  styleUrl: './join-project-modal.component.css',
})
export class ScJoinProjectModalComponent {
  @Input() isOpen: boolean = false;
  @Input() loading: boolean = false;

  @Output() onClose = new EventEmitter<void>();
  @Output() onJoin = new EventEmitter<string>();

  roomCode: string = '';
  errorMessage: string | null = null;

  close(): void {
    this.roomCode = '';
    this.errorMessage = null;
    this.onClose.emit();
  }

  submit(): void {
    const trimmed = this.roomCode.trim();
    if (!trimmed) {
      this.errorMessage = 'Por favor ingresa un código de sala válido.';
      return;
    }

    this.errorMessage = null;
    this.onJoin.emit(trimmed);
  }
}
