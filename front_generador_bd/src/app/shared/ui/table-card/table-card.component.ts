import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ScIconComponent } from '../icon/icon.component';
import { ScBadgeComponent } from '../badge/badge.component';
import { ScDataTypeTagComponent } from '../data-type-tag/data-type-tag.component';

export interface TableCardColumn {
  name: string;
  type: string;
  isPk?: boolean;
  isFk?: boolean;
}

@Component({
  selector: 'sc-table-card',
  standalone: true,
  imports: [CommonModule, ScIconComponent, ScBadgeComponent, ScDataTypeTagComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './table-card.component.html',
  styleUrl: './table-card.component.css',
})
export class ScTableCardComponent {
  @Input({ required: true }) tableName!: string;
  @Input() columns: TableCardColumn[] = [];
  @Input() isCompact: boolean = false;
  @Input() maxCompactColumns: number = 2;
  @Input() customClass: string = '';

  get visibleColumns(): TableCardColumn[] {
    if (this.isCompact) {
      return (this.columns || []).slice(0, this.maxCompactColumns);
    }
    return this.columns || [];
  }

  get remainingColumnsCount(): number {
    return Math.max(0, (this.columns || []).length - this.maxCompactColumns);
  }
}
