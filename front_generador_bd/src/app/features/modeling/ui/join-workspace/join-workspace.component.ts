import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { UmlApiService } from '../../application/uml-api.service';
import { ScButtonComponent, ScIconComponent, ScInputComponent } from '../../../../shared/ui';

export type JoinState = 'VALIDATING' | 'SUCCESS' | 'ERROR';

@Component({
  selector: 'sc-join-workspace',
  standalone: true,
  imports: [CommonModule, FormsModule, ScButtonComponent, ScIconComponent, ScInputComponent],
  templateUrl: './join-workspace.component.html',
  styleUrl: './join-workspace.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JoinWorkspaceComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly umlApi = inject(UmlApiService);

  readonly state = signal<JoinState>('VALIDATING');
  readonly errorMessage = signal<string>('');
  readonly currentCode = signal<string>('');
  manualCode = '';

  ngOnInit(): void {
    const code = this.route.snapshot.paramMap.get('accessCode');
    if (code && code.trim()) {
      this.currentCode.set(code.trim());
      this.manualCode = code.trim();
      this.joinWithCode(code.trim());
    } else {
      this.state.set('ERROR');
      this.errorMessage.set('No se proporcionó un código de acceso válido en el enlace.');
    }
  }

  joinWithCode(codeToJoin: string): void {
    const clean = codeToJoin.trim();
    if (!clean) {
      this.state.set('ERROR');
      this.errorMessage.set('Por favor ingresa un código de acceso.');
      return;
    }

    this.state.set('VALIDATING');
    this.errorMessage.set('');

    this.umlApi.joinCanvas(clean).subscribe({
      next: (res) => {
        this.state.set('SUCCESS');
        // Redirigir al editor con el roomName canónico recuperado
        setTimeout(() => {
          this.router.navigate(['/diagram', res.roomName]);
        }, 300);
      },
      error: (err) => {
        this.state.set('ERROR');
        const detail = err?.error?.message || 'El código de acceso no es válido o el lienzo ya no está disponible.';
        this.errorMessage.set(detail);
      },
    });
  }

  retry(): void {
    this.joinWithCode(this.manualCode);
  }

  goToDashboard(): void {
    this.router.navigate(['/dashboard']);
  }
}
