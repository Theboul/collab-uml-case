import { AfterViewInit, ChangeDetectionStrategy, Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { v4 as uuid } from 'uuid';
import {
  ScButtonComponent,
  ScIconComponent,
  ScInputComponent,
} from '../../../../shared/ui';

import { AuthService } from '../../../../core/auth';

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
export class ScLoginComponent implements AfterViewInit {
  mode: AuthMode = 'login';

  fullName: string = '';
  email: string = '';
  password: string = '';
  rememberMe: boolean = true;

  loading: boolean = false;
  generalError: string | null = null;
  errors: AuthErrors = {};

  private googleClientId: string | null = null;

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private authService: AuthService
  ) {}

  private navigateAfterAuth(): void {
    const returnUrl = this.route.snapshot.queryParams['returnUrl'] || '/dashboard';
    this.router.navigateByUrl(returnUrl);
  }

  ngAfterViewInit(): void {
    if (typeof window !== 'undefined') {
      this.initGoogleAuth();
    }
  }

  private initGoogleAuth(): void {
    this.authService.getAuthConfig().subscribe({
      next: (config) => {
        this.googleClientId = config.googleClientId;
        if (!this.googleClientId) return;
        this.renderGoogleButton();
      },
      error: () => {},
    });
  }

  private renderGoogleButton(): void {
    if (!this.googleClientId || typeof window === 'undefined') return;

    const win = window as any;
    const checkGsi = () => {
      if (win && win.google?.accounts?.id) {
        try {
          win.google.accounts.id.initialize({
            client_id: this.googleClientId,
            callback: (res: { credential?: string }) => this.handleGoogleCredential(res),
          });

          const container = document.getElementById('google-btn-container');
          if (container) {
            container.innerHTML = '';
            win.google.accounts.id.renderButton(container, {
              theme: 'outline',
              size: 'large',
              text: 'continue_with',
              shape: 'rectangular',
              logo_alignment: 'left',
              width: '380',
            });
          }
        } catch (e) {
          console.warn('Error inicializando Google GIS:', e);
        }
      } else {
        setTimeout(checkGsi, 200);
      }
    };

    checkGsi();
  }

  handleGoogleCredential(res: { credential?: string }): void {
    if (res && res.credential) {
      this.loading = true;
      this.generalError = null;
      this.authService.loginWithGoogle(res.credential).subscribe({
        next: () => {
          this.loading = false;
          this.navigateAfterAuth();
        },
        error: (err) => {
          this.loading = false;
          const msg = err.error?.message || 'Error al autenticar con Google.';
          this.generalError = msg;
        },
      });
    }
  }

  toggleMode(newMode: AuthMode): void {
    this.mode = newMode;
    this.errors = {};
    this.generalError = null;
    setTimeout(() => this.renderGoogleButton(), 50);
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
    this.generalError = null;

    if (this.mode === 'register') {
      this.authService
        .register({
          email: this.email,
          password: this.password,
          fullName: this.fullName,
        })
        .subscribe({
          next: () => {
            this.loading = false;
            this.navigateAfterAuth();
          },
          error: (err) => {
            this.loading = false;
            const errBody = err.error;
            if (errBody?.code === 'AUTH_EMAIL_ALREADY_EXISTS') {
              this.errors.email = 'Ya existe una cuenta con este correo.';
            } else {
              this.generalError =
                errBody?.message || 'Error al registrar la cuenta. Inténtalo nuevamente.';
            }
          },
        });
    } else {
      this.authService
        .login({
          email: this.email,
          password: this.password,
        })
        .subscribe({
          next: () => {
            this.loading = false;
            this.navigateAfterAuth();
          },
          error: (err) => {
            this.loading = false;
            const errBody = err.error;
            if (errBody?.code === 'AUTH_INVALID_CREDENTIALS') {
              this.generalError = 'Correo o contraseña incorrectos.';
            } else {
              this.generalError =
                errBody?.message || 'Error al iniciar sesión. Verifica tus credenciales.';
            }
          },
        });
    }
  }

  loginWithGoogle(): void {
    this.generalError = null;
    const win = typeof window !== 'undefined' ? (window as any) : null;
    if (win && win.google?.accounts?.id) {
      this.loading = true;
      try {
        win.google.accounts.id.prompt((notification: any) => {
          this.loading = false;
          if (notification.isNotDisplayed()) {
            const reason = notification.getNotDisplayedReason ? notification.getNotDisplayedReason() : 'bloqueado';
            this.generalError =
              `No se pudo abrir Google One Tap (${reason}). Haz clic en el botón oficial de Google o asegúrate de que http://localhost:4200 esté autorizado en Google Cloud Console.`;
          }
        });
      } catch (e: any) {
        this.loading = false;
        this.generalError = 'Error al invocar Google: ' + (e?.message || e);
      }
    } else {
      this.initGoogleAuth();
    }
  }

  forgotPassword(): void {
    alert('Recuperación de contraseña: Por favor contacta al administrador o ingresa con Google.');
  }
}
