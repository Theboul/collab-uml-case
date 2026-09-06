import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

export type AvatarSize = 'xs' | 'sm' | 'md';

@Component({
  selector: 'sc-avatar-stack',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './avatar-stack.component.html',
  styleUrl: './avatar-stack.component.css',
})
export class ScAvatarStackComponent {
  @Input() avatars: string[] = [];
  @Input() max: number = 3;
  @Input() size: AvatarSize = 'sm';
  @Input() customClass: string = '';

  get visibleAvatars(): string[] {
    return (this.avatars || []).slice(0, this.max);
  }

  get remainingCount(): number {
    return Math.max(0, (this.avatars || []).length - this.max);
  }

  get sizeClasses(): string {
    switch (this.size) {
      case 'xs':
        return 'w-5 h-5 text-[9px]';
      case 'md':
        return 'w-8 h-8 text-xs';
      default:
        return 'w-6 h-6 text-[10px]';
    }
  }

  getInitials(name: string): string {
    if (!name) return '?';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  }
}
