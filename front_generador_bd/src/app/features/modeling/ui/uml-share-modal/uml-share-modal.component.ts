import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { UmlEditorFacade } from '../../application/uml-editor.facade';
import { ScButtonComponent } from '../../../../shared/ui/button/button.component';
import { ScIconComponent } from '../../../../shared/ui/icon/icon.component';

@Component({
  selector: 'app-uml-share-modal',
  standalone: true,
  imports: [CommonModule, ScButtonComponent, ScIconComponent],
  templateUrl: './uml-share-modal.component.html',
  styleUrl: './uml-share-modal.component.css',
})
export class UmlShareModalComponent {
  readonly facade = inject(UmlEditorFacade);
  readonly copied = signal(false);

  readonly shareUrl = computed(() => {
    const room = this.facade.roomName();
    if (typeof window === 'undefined') return '';
    return `${window.location.origin}/diagram/${room || ''}`;
  });

  copyText(text: string): void {
    if (!text) return;
    navigator.clipboard?.writeText(text).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 2000);
    });
  }
}
