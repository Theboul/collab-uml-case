import { ChangeDetectionStrategy, Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NavigationEnd, Router } from '@angular/router';
import { filter, Subscription } from 'rxjs';
import { ScAppShellComponent } from '../../layout/app-shell/app-shell.component';
import {
  DashboardMetrics,
  DashboardService,
  DbEngine,
  ProjectDto,
  ProjectSortBy,
} from './dashboard.service';
import {
  ScButtonComponent,
  ScIconComponent,
  ScSearchInputComponent,
  ScEmptyStateComponent,
} from '../../shared/ui';
import {
  ProjectActionType,
  ScProjectCardComponent,
} from './components/project-card/project-card.component';
import { ScJoinProjectModalComponent } from './components/join-project-modal/join-project-modal.component';
import { ScNewProjectModalComponent } from './components/new-project-modal/new-project-modal.component';

import { AuthService } from '../../core/auth';

@Component({
  selector: 'sc-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    ScAppShellComponent,
    ScButtonComponent,
    ScIconComponent,
    ScSearchInputComponent,
    ScEmptyStateComponent,
    ScProjectCardComponent,
    ScJoinProjectModalComponent,
    ScNewProjectModalComponent,
  ],
  changeDetection: ChangeDetectionStrategy.Default,
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit, OnDestroy {
  userName: string = 'Desarrollador';

  metrics: DashboardMetrics = {
    totalEntities: 0,
    activeProjects: 0,
    referentialIntegrity: 100,
  };

  recentProjects: ProjectDto[] = [];
  allProjects: ProjectDto[] = [];
  filteredProjects: ProjectDto[] = [];

  searchQuery: string = '';
  selectedEngine: 'all' | DbEngine = 'all';
  currentSort: ProjectSortBy = 'updatedAt';

  isJoinModalOpen: boolean = false;
  isJoining: boolean = false;
  joinError: string | null = null;

  isNewModalOpen: boolean = false;

  isCreating: boolean = false;

  private navSub?: Subscription;

  constructor(
    private dashboardService: DashboardService,
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadUserData();
    this.refreshDashboard();

    this.navSub = this.router.events
      .pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd))
      .subscribe(() => {
        this.refreshDashboard();
      });
  }

  ngOnDestroy(): void {
    this.navSub?.unsubscribe();
  }

  refreshDashboard(): void {
    this.loadMetrics();
    this.loadRecentProjects();
    this.loadAllProjects();
  }

  loadUserData(): void {
    const user = this.authService.currentUser();
    if (user) {
      const full = user.fullName || user.email || 'Desarrollador';
      this.userName = full.split(' ')[0] || 'Desarrollador';
      return;
    }

    if (typeof window !== 'undefined' && window.localStorage) {
      try {
        const stored = localStorage.getItem('sc_user_profile') || localStorage.getItem('sc_user');
        if (stored) {
          const u = JSON.parse(stored);
          const full = u.fullName || u.email || 'Desarrollador';
          this.userName = full.split(' ')[0] || 'Desarrollador';
        }
      } catch {
        this.userName = 'Desarrollador';
      }
    }
  }

  loadMetrics(): void {
    this.dashboardService.getMetrics().subscribe(m => {
      this.metrics = m;
    });
  }

  loadRecentProjects(): void {
    this.dashboardService.getRecentProjects(3).subscribe(projects => {
      this.recentProjects = projects;
    });
  }

  loadAllProjects(): void {
    this.dashboardService.getAllProjects(this.currentSort, this.searchQuery).subscribe(projects => {
      this.allProjects = projects;
      this.applyLocalFilters();
    });
  }

  applyLocalFilters(): void {
    let result = [...this.allProjects];

    if (this.selectedEngine !== 'all') {
      result = result.filter(p => p.engine === this.selectedEngine);
    }

    if (this.searchQuery.trim()) {
      const q = this.searchQuery.toLowerCase();
      result = result.filter(p =>
        p.name.toLowerCase().includes(q) ||
        (p.description && p.description.toLowerCase().includes(q))
      );
    }

    this.filteredProjects = result;
  }

  onSearchChange(query: string): void {
    this.searchQuery = query;
    this.applyLocalFilters();
  }

  onGlobalSearch(query: string): void {
    this.searchQuery = query;
    this.applyLocalFilters();
    this.scrollToSection('all-projects-section');
  }

  setEngineFilter(engine: 'all' | DbEngine): void {
    this.selectedEngine = engine;
    this.applyLocalFilters();
  }

  onSortChange(event: Event): void {
    const val = (event.target as HTMLSelectElement).value as ProjectSortBy;
    this.currentSort = val;
    this.loadAllProjects();
  }

  openProject(project: ProjectDto): void {
    // Redirigir al lienzo interactivo
    this.router.navigate(['/diagram', project.roomName]);
  }

  openJoinModal(): void {
    this.joinError = null;
    this.isJoinModalOpen = true;
  }

  joinProject(roomCode: string): void {
    this.isJoining = true;
    this.joinError = null;
    this.dashboardService.joinProjectByRoomCode(roomCode).subscribe({
      next: (res) => {
        this.isJoining = false;
        this.isJoinModalOpen = false;
        if (res?.roomName) {
          this.router.navigate(['/diagram', res.roomName]);
        }
      },
      error: (err) => {
        this.isJoining = false;
        this.joinError = err?.error?.message || 'Código de acceso inválido o el lienzo no existe.';
      },
    });
  }

  openNewProjectModal(): void {
    this.isNewModalOpen = true;
  }

  createNewProject(payload: { name: string; engine: DbEngine }): void {
    this.isCreating = true;
    this.dashboardService.createProject(payload.name, payload.engine).subscribe({
      next: (newProj) => {
        this.isCreating = false;
        this.isNewModalOpen = false;
        this.router.navigate(['/diagram', newProj.roomName]);
      },
      error: () => {
        this.isCreating = false;
      }
    });
  }

  onProjectAction(event: { action: ProjectActionType; project: ProjectDto }): void {
    switch (event.action) {
      case 'duplicate':
        this.dashboardService.duplicateProject(event.project.id).subscribe(() => {
          this.loadAllProjects();
          this.loadRecentProjects();
          this.loadMetrics();
        });
        break;
      case 'delete':
        if (confirm(`¿Estás seguro de eliminar el proyecto "${event.project.name}"?`)) {
          this.dashboardService.deleteProject(event.project.id).subscribe(() => {
            this.allProjects = this.allProjects.filter(p => p.id !== event.project.id);
            this.recentProjects = this.recentProjects.filter(p => p.id !== event.project.id);
            this.applyLocalFilters();
          });
        }
        break;
      case 'export-sql':
        alert(`Generando exportación SQL para "${event.project.name}" (${event.project.engine})...`);
        break;
      case 'rename':
        const newName = prompt('Nuevo nombre para el proyecto:', event.project.name);
        if (newName && newName.trim()) {
          event.project.name = newName.trim();
        }
        break;
    }
  }

  handleEmptyStateAction(): void {
    if (this.searchQuery || this.selectedEngine !== 'all') {
      this.searchQuery = '';
      this.selectedEngine = 'all';
      this.applyLocalFilters();
    } else {
      this.openNewProjectModal();
    }
  }

  importSql(): void {
    alert('Función de importación SQL: Selecciona un archivo .sql o pega tu esquema DDL.');
  }

  scrollToSection(sectionId: string): void {
    if (typeof document !== 'undefined') {
      const el = document.getElementById(sectionId);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' });
      }
    }
  }
}
