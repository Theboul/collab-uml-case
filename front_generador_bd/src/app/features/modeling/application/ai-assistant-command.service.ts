import { Injectable, inject } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { UmlApiService } from './uml-api.service';
import { EditorStateService } from './editor-state.service';
import { EditorCommandService } from './editor-command.service';
import { EditorHistoryService } from './editor-history.service';

/**
 * CU6: envía una instrucción de texto (tipeada o dictada por voz vía Web
 * Speech API, que entra por el mismo input) al endpoint que la traduce a
 * comandos reales del editor y los valida contra core/uml_domain. No aplica
 * nada al modelo local hasta que el backend confirma -- si el backend
 * rechaza la instrucción (ambigua, edición/eliminación no soportada, o
 * choque de versión), el lienzo local queda intacto y se muestra el motivo.
 */
@Injectable({
  providedIn: 'root',
})
export class AiAssistantCommandService {
  private readonly api = inject(UmlApiService);
  private readonly state = inject(EditorStateService);
  private readonly commandService = inject(EditorCommandService);
  private readonly history = inject(EditorHistoryService);

  sendPrompt(prompt: string): void {
    const canvasId = this.state.canvasId();
    if (!canvasId || !prompt.trim()) return;

    this.state.setAssistantError(null);
    this.state.setAssistantProcessing(true);

    this.api.sendTextCommand(canvasId, prompt.trim(), this.state.version()).subscribe({
      next: (res) => {
        this.state.setAssistantProcessing(false);
        if (res.canvas) {
          this.commandService.applyCanvasSnapshot(res.canvas);
        } else {
          this.state.setVersion(res.version);
        }
      },
      error: (err: HttpErrorResponse) => {
        this.state.setAssistantProcessing(false);
        const message =
          err.error?.message || 'No se pudo interpretar la instrucción. Intentá de nuevo.';
        this.state.setAssistantError(message);

        if (err.status === 409) {
          // Choque de versión concurrente: mismo tratamiento que el resto de comandos.
          this.history.clear();
          this.commandService.reloadSnapshot(canvasId);
        }
      },
    });
  }
}
