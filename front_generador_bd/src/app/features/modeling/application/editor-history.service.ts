import { Injectable, signal } from '@angular/core';

export interface HistoryAction {
  description: string;
  forwardCommand: { type: string; payload: any };
  inverseCommand: { type: string; payload: any };
}

@Injectable({
  providedIn: 'root',
})
export class EditorHistoryService {
  private undoStack: HistoryAction[] = [];
  private redoStack: HistoryAction[] = [];

  readonly canUndo = signal<boolean>(false);
  readonly canRedo = signal<boolean>(false);

  pushAction(action: HistoryAction): void {
    this.undoStack.push(action);
    this.redoStack = [];
    this.updateSignals();
  }

  popUndo(): HistoryAction | undefined {
    const action = this.undoStack.pop();
    this.updateSignals();
    return action;
  }

  pushRedo(action: HistoryAction): void {
    this.redoStack.push(action);
    this.updateSignals();
  }

  popRedo(): HistoryAction | undefined {
    const action = this.redoStack.pop();
    this.updateSignals();
    return action;
  }

  peekUndo(): HistoryAction | undefined {
    return this.undoStack.length > 0 ? this.undoStack[this.undoStack.length - 1] : undefined;
  }

  peekRedo(): HistoryAction | undefined {
    return this.redoStack.length > 0 ? this.redoStack[this.redoStack.length - 1] : undefined;
  }

  pushUndo(action: HistoryAction): void {
    this.undoStack.push(action);
    this.updateSignals();
  }

  clear(): void {
    this.undoStack = [];
    this.redoStack = [];
    this.updateSignals();
  }

  private updateSignals(): void {
    this.canUndo.set(this.undoStack.length > 0);
    this.canRedo.set(this.redoStack.length > 0);
  }
}
