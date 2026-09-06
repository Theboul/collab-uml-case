import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output, forwardRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ControlValueAccessor, FormsModule, NG_VALUE_ACCESSOR } from '@angular/forms';
import { ScIconComponent } from '../icon/icon.component';

@Component({
  selector: 'sc-input',
  standalone: true,
  imports: [CommonModule, FormsModule, ScIconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => ScInputComponent),
      multi: true,
    },
  ],
  templateUrl: './input.component.html',
  styleUrl: './input.component.css',
})
export class ScInputComponent implements ControlValueAccessor {
  @Input({ required: true }) inputId!: string;
  @Input() label?: string;
  @Input() type: 'text' | 'email' | 'password' | 'number' = 'text';
  @Input() placeholder: string = '';
  @Input() hint?: string;
  @Input() error?: string | null;
  @Input() icon?: string;
  @Input() required: boolean = false;
  @Input() disabled: boolean = false;
  @Input() customClass: string = '';

  @Output() valueChange = new EventEmitter<string>();

  value: string = '';
  showPassword: boolean = false;

  onChange: (value: string) => void = () => {};
  onTouched: () => void = () => {};

  get actualType(): string {
    if (this.type === 'password') {
      return this.showPassword ? 'text' : 'password';
    }
    return this.type;
  }

  togglePasswordVisibility(): void {
    this.showPassword = !this.showPassword;
  }

  onInputChange(event: Event): void {
    const val = (event.target as HTMLInputElement).value;
    this.value = val;
    this.onChange(val);
    this.valueChange.emit(val);
  }

  onBlur(): void {
    this.onTouched();
  }

  writeValue(val: string): void {
    this.value = val || '';
  }

  registerOnChange(fn: (val: string) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }
}
