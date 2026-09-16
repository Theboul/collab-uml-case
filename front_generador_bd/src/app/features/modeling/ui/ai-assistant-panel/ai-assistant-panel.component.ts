import { Component, PLATFORM_ID, inject, signal } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { UmlEditorFacade } from '../../application/uml-editor.facade';
import { ScButtonComponent } from '../../../../shared/ui/button/button.component';
import { ScIconComponent } from '../../../../shared/ui/icon/icon.component';

/**
 * Formas mínimas de la Web Speech API (SpeechRecognition/webkitSpeechRecognition)
 * que este componente usa. No están en el lib.dom de este proyecto (API todavía
 * no estándar, solo con prefijo de proveedor), así que se declaran acá en vez de
 * recurrir a `any`.
 */
type SpeechRecognitionResultLike = Record<number, { transcript: string }>;
interface SpeechRecognitionEventLike {
  results: ArrayLike<SpeechRecognitionResultLike>;
}
interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start(): void;
  stop(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}
interface SpeechRecognitionWindow {
  webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  SpeechRecognition?: new () => SpeechRecognitionLike;
}

/**
 * CU6: panel de generación/ampliación del modelo por texto o voz. El botón de
 * micrófono usa la Web Speech API nativa del navegador (SpeechRecognition) --
 * mismo patrón ya probado en el chatbot legacy (side-panel.ts) -- para
 * transcribir voz a texto en el cliente; el texto transcripto entra por el
 * mismo textarea que si el usuario lo hubiera tipeado, sin ningún endpoint
 * de voz nuevo en el backend.
 */
@Component({
  selector: 'app-ai-assistant-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, ScButtonComponent, ScIconComponent],
  templateUrl: './ai-assistant-panel.component.html',
  styleUrl: './ai-assistant-panel.component.css',
})
export class AiAssistantPanelComponent {
  readonly facade = inject(UmlEditorFacade);
  private readonly platformId = inject(PLATFORM_ID);

  prompt = '';
  readonly recognizing = signal(false);
  readonly speechSupported: boolean;
  private recognition: SpeechRecognitionLike | null = null;

  constructor() {
    if (!isPlatformBrowser(this.platformId)) {
      // En SSR (y en el prerenderizado de ng serve) 'window' no existe -- no tocarlo acá.
      this.speechSupported = false;
      return;
    }

    const speechWindow = window as unknown as SpeechRecognitionWindow;
    const SpeechRecognitionCtor = speechWindow.webkitSpeechRecognition || speechWindow.SpeechRecognition;
    this.speechSupported = !!SpeechRecognitionCtor;

    if (SpeechRecognitionCtor) {
      this.recognition = new SpeechRecognitionCtor();
      this.configureVoiceRecognition(this.recognition);
    }
  }

  private configureVoiceRecognition(recognition: SpeechRecognitionLike): void {
    recognition.lang = 'es-ES';
    recognition.interimResults = true;
    // true: sigue escuchando a través de las pausas naturales del habla hasta que el
    // usuario apreta el mic de nuevo (o Generar). En false, el navegador corta el
    // reconocimiento solo ante el primer silencio, apagando el mic sin que el
    // usuario lo haya tocado.
    recognition.continuous = true;

    recognition.onresult = (event: SpeechRecognitionEventLike) => {
      this.prompt = Array.from(event.results)
        .map((result) => result[0].transcript)
        .join('');
    };
    recognition.onend = () => this.recognizing.set(false);
    recognition.onerror = () => this.recognizing.set(false);
  }

  toggleVoiceInput(): void {
    if (!this.recognition) return;
    if (this.recognizing()) {
      this.recognition.stop();
      this.recognizing.set(false);
    } else {
      this.recognition.start();
      this.recognizing.set(true);
    }
  }

  send(): void {
    if (!this.prompt.trim() || this.facade.isAssistantProcessing()) return;
    if (this.recognizing()) {
      this.recognition?.stop();
      this.recognizing.set(false);
    }
    this.facade.sendAssistantPrompt(this.prompt);
    this.prompt = '';
  }

  close(): void {
    if (this.recognizing()) {
      this.recognition?.stop();
      this.recognizing.set(false);
    }
    this.facade.closeAssistantPanel();
  }
}
