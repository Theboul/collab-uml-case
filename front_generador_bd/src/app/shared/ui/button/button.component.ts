import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ScIconComponent } from '../icon/icon.component';

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'success';
export type ButtonSize = 'xs' | 'sm' | 'md' | 'lg' | 'icon';

@Component({
  selector: 'sc-button',
  standalone: true,
  imports: [CommonModule, ScIconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './button.component.html',
  styleUrl: './button.component.css',
})
export class ScButtonComponent {
  @Input() variant: ButtonVariant = 'primary';
  @Input() size: ButtonSize = 'md';
  @Input() type: 'button' | 'submit' | 'reset' = 'button';
  @Input() disabled: boolean = false;
  @Input() loading: boolean = false;
  @Input() icon?: string;
  @Input() trailingIcon?: string;
  @Input() ariaLabel?: string;
  @Input() customClass: string = '';
  @Input() hasContent: boolean = true;

  @Output() onClick = new EventEmitter<MouseEvent>();

  handleClick(event: MouseEvent): void {
    if (!this.disabled && !this.loading) {
      this.onClick.emit(event);
    }
  }

  get iconSize(): 14 | 16 | 18 | 20 {
    switch (this.size) {
      case 'xs':
        return 14;
      case 'sm':
        return 16;
      case 'lg':
        return 20;
      default:
        return 18;
    }
  }

  get variantClasses(): string {
    switch (this.variant) {
      case 'primary':
        return 'bg-primary hover:bg-primary-hover text-white shadow-sm shadow-primary-500/25 active:scale-[0.98] border border-primary-400/20';
      case 'secondary':
        return 'bg-surface-container hover:bg-surface-container-high text-neutral-200 hover:text-white border border-neutral-700/60 active:scale-[0.98]';
      case 'outline':
        return 'bg-transparent hover:bg-surface-container/60 text-neutral-300 hover:text-white border border-neutral-700/80 active:scale-[0.98]';
      case 'ghost':
        return 'bg-transparent hover:bg-surface-container/60 text-neutral-400 hover:text-neutral-100 active:scale-[0.98]';
      case 'danger':
        return 'bg-danger-500/10 hover:bg-danger-500 text-danger-400 hover:text-white border border-danger-500/30 active:scale-[0.98]';
      case 'success':
        return 'bg-tertiary-500 hover:bg-tertiary-600 text-white shadow-sm shadow-tertiary-500/25 active:scale-[0.98]';
      default:
        return '';
    }
  }

  get sizeClasses(): string {
    switch (this.size) {
      case 'xs':
        return 'h-6 px-2 text-xs gap-1';
      case 'sm':
        return 'h-8 px-3 text-xs gap-1.5';
      case 'md':
        return 'h-9 px-3.5 text-sm gap-2';
      case 'lg':
        return 'h-11 px-5 text-base gap-2.5';
      case 'icon':
        return 'h-9 w-9 p-0';
      default:
        return 'h-9 px-3.5 text-sm';
    }
  }
}
