import { InjectionToken } from '@angular/core';
import { Observable, of } from 'rxjs';
import { EditorCommand } from '../domain/commands/editor-commands';

export interface CollaborationGateway {
  connect(roomId: string): void;
  disconnect(): void;
  broadcastCommand(command: EditorCommand): void;
  remoteCommands$: Observable<EditorCommand>;
  presence$: Observable<any>;
}

export class NoOpCollaborationGateway implements CollaborationGateway {
  readonly remoteCommands$: Observable<EditorCommand> = of();
  readonly presence$: Observable<any> = of();

  connect(_roomId: string): void {
    // No-op en CU1 (reservado para CU5)
  }

  disconnect(): void {
    // No-op en CU1
  }

  broadcastCommand(_command: EditorCommand): void {
    // No-op en CU1
  }
}

export const COLLABORATION_GATEWAY = new InjectionToken<CollaborationGateway>(
  'COLLABORATION_GATEWAY',
  {
    providedIn: 'root',
    factory: () => new NoOpCollaborationGateway(),
  }
);
