import { Injectable, signal } from '@angular/core';

export interface ToastMessage {
  id: string;
  text: string;
  type: 'info' | 'warning' | 'error' | 'success';
  durationMs: number;
}

@Injectable({
  providedIn: 'root',
})
export class ToastService {
  private readonly _toasts = signal<ToastMessage[]>([]);
  readonly toasts = this._toasts.asReadonly();

  private counter = 0;

  show(
    text: string,
    type: 'info' | 'warning' | 'error' | 'success' = 'info',
    durationMs = 4000,
  ): string {
    const id = `toast-${Date.now()}-${++this.counter}`;
    const message: ToastMessage = { id, text, type, durationMs };
    this._toasts.update((current) => [...current, message]);

    if (durationMs > 0) {
      setTimeout(() => {
        this.dismiss(id);
      }, durationMs);
    }

    return id;
  }

  dismiss(id: string): void {
    this._toasts.update((current) => current.filter((t) => t.id !== id));
  }
}
