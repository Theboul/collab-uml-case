import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

export type IconSize = 14 | 16 | 18 | 20 | 24 | 32;

@Component({
  selector: 'sc-icon',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './icon.component.html',
  styleUrl: './icon.component.css',
})
export class ScIconComponent {
  @Input({ required: true }) name!: string;
  @Input() size: IconSize = 20;
  @Input() filled: boolean = false;
  @Input() customClass: string = '';

  get fontVariation(): string {
    return `'FILL' ${this.filled ? 1 : 0}, 'wght' 400, 'GRAD' 0, 'opsz' ${this.size}`;
  }
}
