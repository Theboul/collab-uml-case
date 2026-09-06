import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

export type BadgeType = 'PK' | 'FK' | 'UQ' | 'NN' | 'CHK' | 'DEFAULT';
export type BadgeSize = 'xs' | 'sm';

@Component({
  selector: 'sc-badge',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './badge.component.html',
  styleUrl: './badge.component.css',
})
export class ScBadgeComponent {
  @Input({ required: true }) type: BadgeType = 'DEFAULT';
  @Input() label?: string;
  @Input() size: BadgeSize = 'xs';
  @Input() customClass: string = '';

  get tooltipText(): string {
    switch (this.type) {
      case 'PK':
        return 'Primary Key';
      case 'FK':
        return 'Foreign Key';
      case 'UQ':
        return 'Unique Constraint';
      case 'NN':
        return 'Not Null';
      case 'CHK':
        return 'Check Constraint';
      default:
        return this.label || '';
    }
  }

  get typeClasses(): string {
    switch (this.type) {
      case 'PK':
        return 'bg-amber-500/15 text-amber-300 border-amber-500/30';
      case 'FK':
        return 'bg-sky-500/15 text-sky-300 border-sky-500/30';
      case 'UQ':
        return 'bg-purple-500/15 text-purple-300 border-purple-500/30';
      case 'NN':
        return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
      case 'CHK':
        return 'bg-orange-500/15 text-orange-300 border-orange-500/30';
      default:
        return 'bg-neutral-800 text-neutral-300 border-neutral-700';
    }
  }

  get sizeClasses(): string {
    switch (this.size) {
      case 'xs':
        return 'text-[9px] leading-tight px-1 py-0.5 min-w-[20px]';
      case 'sm':
        return 'text-[11px] leading-tight px-1.5 py-0.5 min-w-[24px]';
      default:
        return 'text-[9px] px-1 py-0.5';
    }
  }
}
