import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ProjectDto } from '../../dashboard.service';
import {
  ScIconComponent,
  ScTableCardComponent,
  ScAvatarStackComponent,
  TableCardColumn,
} from '../../../../shared/ui';

export type ProjectCardVariant = 'recent' | 'grid';
export type ProjectActionType = 'rename' | 'duplicate' | 'export-sql' | 'delete';

@Component({
  selector: 'sc-project-card',
  standalone: true,
  imports: [
    CommonModule,
    ScIconComponent,
    ScTableCardComponent,
    ScAvatarStackComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './project-card.component.html',
  styleUrl: './project-card.component.css',
})
export class ScProjectCardComponent {
  @Input({ required: true }) project!: ProjectDto;
  @Input() variant: ProjectCardVariant = 'grid';

  @Output() onOpen = new EventEmitter<ProjectDto>();
  @Output() onAction = new EventEmitter<{ action: ProjectActionType; project: ProjectDto }>();

  menuOpen: boolean = false;

  // Mock mini-preview data for schematic representation
  previewTableA: { name: string; cols: TableCardColumn[] } = {
    name: 'users',
    cols: [
      { name: 'id', type: 'UUID', isPk: true },
      { name: 'email', type: 'VARCHAR' },
    ],
  };

  previewTableB: { name: string; cols: TableCardColumn[] } = {
    name: 'orders',
    cols: [
      { name: 'id', type: 'UUID', isPk: true },
      { name: 'user_id', type: 'UUID', isFk: true },
    ],
  };

  get relativeTime(): string {
    if (!this.project?.updatedAt) return 'recientemente';
    const diffMs = Date.now() - new Date(this.project.updatedAt).getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 60) return `${Math.max(1, mins)} min`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours} h`;
    const days = Math.floor(hours / 24);
    return `${days} d`;
  }

  toggleMenu(): void {
    this.menuOpen = !this.menuOpen;
  }

  handleAction(action: ProjectActionType): void {
    this.menuOpen = false;
    this.onAction.emit({ action, project: this.project });
  }
}
