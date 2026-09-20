import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ToastService } from './toast.service';
import { ScIconComponent } from '../icon/icon.component';

@Component({
  selector: 'sc-toast-container',
  standalone: true,
  imports: [CommonModule, ScIconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      class="fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none max-w-sm w-full"
      aria-live="polite"
    >
      @for (toast of toastService.toasts(); track toast.id) {
        <div
          class="pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-lg shadow-xl border text-xs font-medium backdrop-blur transition-all animate-in fade-in slide-in-from-bottom-2 duration-200"
          [ngClass]="{
            'bg-surface-container-high/95 text-neutral-100 border-neutral-700':
              toast.type === 'info',
            'bg-amber-950/90 text-amber-200 border-amber-800/80': toast.type === 'warning',
            'bg-rose-950/90 text-rose-200 border-rose-800/80': toast.type === 'error',
            'bg-emerald-950/90 text-emerald-200 border-emerald-800/80': toast.type === 'success',
          }"
        >
          <sc-icon
            [name]="iconFor(toast.type)"
            [size]="18"
            class="shrink-0"
            [ngClass]="{
              'text-primary-400': toast.type === 'info',
              'text-amber-400': toast.type === 'warning',
              'text-rose-400': toast.type === 'error',
              'text-emerald-400': toast.type === 'success',
            }"
          />
          <span class="flex-1 leading-snug">{{ toast.text }}</span>
          <button
            type="button"
            (click)="toastService.dismiss(toast.id)"
            class="p-0.5 rounded text-neutral-400 hover:text-neutral-200 cursor-pointer"
            aria-label="Cerrar notificación"
          >
            <sc-icon name="close" [size]="14" />
          </button>
        </div>
      }
    </div>
  `,
})
export class ScToastContainerComponent {
  readonly toastService = inject(ToastService);

  iconFor(type: string): string {
    switch (type) {
      case 'warning':
        return 'warning';
      case 'error':
        return 'error';
      case 'success':
        return 'check_circle';
      default:
        return 'info';
    }
  }
}
