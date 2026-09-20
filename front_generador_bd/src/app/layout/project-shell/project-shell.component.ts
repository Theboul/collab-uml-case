import { ChangeDetectionStrategy, Component, Input, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { ScIconComponent } from '../../shared/ui';
import { AuthService } from '../../core/auth';
import { PresencePeer } from '../../features/modeling/domain/models/collaboration.models';

/**
 * Shell único para toda vista dentro de un proyecto abierto (AGENTS.md §4.3).
 * Hoy solo existe una vista real ("Lienzo" / Canvas Designer) — el sidebar
 * refleja eso a propósito, sin entradas para SQL Editor/Tables/Migrations
 * que todavía no existen. El toolbar propio de cada feature (ej.
 * UmlToolbarComponent) se sigue proyectando como contenido, no se absorbe
 * acá: no tiene un segundo consumidor real todavía.
 */
@Component({
  selector: 'sc-project-shell',
  standalone: true,
  imports: [CommonModule, RouterModule, ScIconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './project-shell.component.html',
  styleUrl: './project-shell.component.css',
})
export class ProjectShellComponent implements OnInit {
  @Input() projectName: string | null = null;
  @Input() peers: PresencePeer[] = [];

  private readonly router = inject(Router);
  private readonly authService = inject(AuthService);

  userName = '';
  userEmail = '';

  get visiblePeers(): PresencePeer[] {
    return (this.peers || []).slice(0, 3);
  }

  get overflowCount(): number {
    return Math.max(0, (this.peers || []).length - 3);
  }

  ngOnInit(): void {
    const user = this.authService.currentUser();
    if (user) {
      this.userName = user.fullName || user.email;
      this.userEmail = user.email;
    }
  }

  get userInitials(): string {
    const parts = (this.userName || '').trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return (this.userName || '?').slice(0, 2).toUpperCase();
  }

  logout(): void {
    this.authService.logout().subscribe(() => {
      this.router.navigate(['/login']);
    });
  }
}
