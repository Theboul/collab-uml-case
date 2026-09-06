import { ChangeDetectionStrategy, Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { v4 as uuid } from 'uuid';
import {
  ScButtonComponent,
  ScIconComponent,
  ScInputComponent,
} from '../../../../shared/ui';

export type AuthMode = 'login' | 'register';

export interface AuthErrors {
  fullName?: string | null;
  email?: string | null;
  password?: string | null;
}

@Component({
  selector: 'sc-login',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ScButtonComponent,
    ScInputComponent,
    ScIconComponent,
  ],
  changeDetection: ChangeDetectionStrategy.Default,
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
})
export class ScLoginComponent {
  mode: AuthMode = 'login';

  fullName: string = '';
  email: string = '';
  password: string = '';
  rememberMe: boolean = true;

  loading: boolean = false;
  generalError: string | null = null;
  errors: AuthErrors = {};

  constructor(private router: Router) {}

  toggleMode(newMode: AuthMode): void {
    this.mode = newMode;
    this.errors = {};
    this.generalError = null;
  }

  validateForm(): boolean {
    this.errors = {};
    this.generalError = null;

    if (!this.email || !this.email.includes('@')) {
      this.errors.email = 'Ingresa un correo electrónico válido.';
    }

    if (!this.password || this.password.length < 6) {
      this.errors.password = 'La contraseña debe tener al menos 6 caracteres.';
    }

    if (this.mode === 'register' && (!this.fullName || this.fullName.trim().length < 2)) {
      this.errors.fullName = 'Ingresa tu nombre completo.';
    }

    return !this.errors.email && !this.errors.password && !this.errors.fullName;
  }

  onSubmit(): void {
    if (!this.validateForm()) {
      return;
    }

    this.loading = true;

    setTimeout(() => {
      this.loading = false;
      const fakeToken = 'sc_session_' + uuid();
      localStorage.setItem('sc_auth_token', fakeToken);
      localStorage.setItem(
        'sc_user',
        JSON.stringify({
          email: this.email,
          fullName: this.mode === 'register' ? this.fullName : (this.email.split('@')[0] || 'Desarrollador'),
        })
      );

      // Redirigir al lienzo o dashboard
      const defaultRoomId = uuid();
      this.router.navigate(['/diagram', defaultRoomId]);
    }, 600);
  }

  loginWithGoogle(): void {
    this.loading = true;
    setTimeout(() => {
      this.loading = false;
      const fakeToken = 'sc_google_' + uuid();
      localStorage.setItem('sc_auth_token', fakeToken);
      localStorage.setItem(
        'sc_user',
        JSON.stringify({
          email: 'google.user@ejemplo.com',
          fullName: 'Google User',
        })
      );
      const defaultRoomId = uuid();
      this.router.navigate(['/diagram', defaultRoomId]);
    }, 500);
  }

  forgotPassword(): void {
    alert('Recuperación de contraseña: Por favor contacta al administrador o ingresa con Google.');
  }
}
