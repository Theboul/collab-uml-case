import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ScIconComponent } from '../icon/icon.component';

export type ScModalShellSize = 'md' | 'lg';

/**
 * Shell reutilizable de modal (AGENTS.md §4.4): backdrop + tarjeta + header
 * (ícono, título, subtítulo opcional, botón cerrar). El cuerpo y el pie de
 * acciones quedan como contenido proyectado — varían demasiado entre
 * consumidores (formulario de proyecto nuevo vs. unirse a sala) para forzar
 * un slot genérico con solo dos consumidores reales.
 *
 * Extraído de `sc-new-project-modal` y `sc-join-project-modal`, que tenían
 * el backdrop/tarjeta/header duplicados byte a byte. `uml-share-modal`
 * queda afuera a propósito: usa un tema claro distinto (fondo blanco,
 * texto oscuro) al tema oscuro de este shell — forzarlo acá exigiría
 * soporte de variante de tema para un solo consumidor real, que es
 * exactamente la abstracción prematura que el proyecto evita.
 */
@Component({
  selector: 'sc-modal-shell',
  standalone: true,
  imports: [CommonModule, ScIconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './modal-shell.component.html',
  styleUrl: './modal-shell.component.css',
})
export class ScModalShellComponent {
  @Input() isOpen = false;
  @Input() icon = '';
  @Input() title = '';
  @Input() subtitle: string | null = null;
  @Input() size: ScModalShellSize = 'md';

  @Output() closed = new EventEmitter<void>();

  close(): void {
    this.closed.emit();
  }
}
