import { ChangeDetectionStrategy, Component, EventEmitter, OnInit, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { ScIconComponent, ScButtonComponent, ScSearchInputComponent } from '../../shared/ui';
import { AuthService } from '../../core/auth';

@Component({
  selector: 'sc-app-shell',
  standalone: true,
  imports: [CommonModule, RouterModule, ScIconComponent, ScButtonComponent, ScSearchInputComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app-shell.component.html',
  styleUrl: './app-shell.component.css',
})
export class ScAppShellComponent implements OnInit {
  userName: string = 'Alex Rivera';
  userEmail: string = 'alex.rivera@ejemplo.com';

  @Output() onImportSql = new EventEmitter<void>();
  @Output() onGlobalSearch = new EventEmitter<string>();
  @Output() onNavigateRecent = new EventEmitter<void>();
  @Output() onNavigateAll = new EventEmitter<void>();

  constructor(
    private router: Router,
    private authService: AuthService
  ) {}

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
    return (this.userName || 'AR').slice(0, 2).toUpperCase();
  }

  logout(): void {
    this.authService.logout().subscribe(() => {
      this.router.navigate(['/login']);
    });
  }
}
