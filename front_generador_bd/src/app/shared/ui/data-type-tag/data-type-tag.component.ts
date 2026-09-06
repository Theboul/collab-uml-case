import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

export type SqlDataTypeCategory = 'string' | 'number' | 'boolean' | 'datetime' | 'id' | 'json' | 'other';

@Component({
  selector: 'sc-data-type-tag',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './data-type-tag.component.html',
  styleUrl: './data-type-tag.component.css',
})
export class ScDataTypeTagComponent {
  @Input({ required: true }) type!: string;
  @Input() precision?: number;
  @Input() scale?: number;
  @Input() length?: number;
  @Input() customClass: string = '';

  get displayType(): string {
    const raw = (this.type || '').toUpperCase();
    if (this.length) {
      return `${raw}(${this.length})`;
    }
    if (this.precision !== undefined && this.scale !== undefined) {
      return `${raw}(${this.precision},${this.scale})`;
    }
    if (this.precision !== undefined) {
      return `${raw}(${this.precision})`;
    }
    return raw;
  }

  get category(): SqlDataTypeCategory {
    const t = (this.type || '').toUpperCase();
    if (t.includes('UUID')) return 'id';
    if (t.includes('CHAR') || t.includes('TEXT') || t.includes('STRING')) return 'string';
    if (t.includes('INT') || t.includes('NUMERIC') || t.includes('DECIMAL') || t.includes('FLOAT') || t.includes('DOUBLE') || t.includes('SERIAL')) return 'number';
    if (t.includes('BOOL')) return 'boolean';
    if (t.includes('TIME') || t.includes('DATE')) return 'datetime';
    if (t.includes('JSON')) return 'json';
    return 'other';
  }

  get categoryClasses(): string {
    switch (this.category) {
      case 'id':
        return 'bg-purple-500/10 text-purple-300 border-purple-500/20';
      case 'string':
        return 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20';
      case 'number':
        return 'bg-sky-500/10 text-sky-300 border-sky-500/20';
      case 'boolean':
        return 'bg-pink-500/10 text-pink-300 border-pink-500/20';
      case 'datetime':
        return 'bg-amber-500/10 text-amber-300 border-amber-500/20';
      case 'json':
        return 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20';
      default:
        return 'bg-neutral-800/80 text-neutral-300 border-neutral-700/60';
    }
  }
}
