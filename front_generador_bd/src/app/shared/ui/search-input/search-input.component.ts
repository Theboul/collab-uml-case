import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ScIconComponent } from '../icon/icon.component';

@Component({
  selector: 'sc-search-input',
  standalone: true,
  imports: [CommonModule, ScIconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './search-input.component.html',
  styleUrl: './search-input.component.css',
})
export class ScSearchInputComponent {
  @Input() placeholder: string = 'Buscar...';
  @Input() value: string = '';
  @Input() shortcut?: string;
  @Input() customClass: string = '';

  @Output() searchChange = new EventEmitter<string>();
  @Output() onEnter = new EventEmitter<string>();

  onInputChange(event: Event): void {
    const val = (event.target as HTMLInputElement).value;
    this.value = val;
    this.searchChange.emit(val);
  }

  clear(): void {
    this.value = '';
    this.searchChange.emit('');
  }
}
