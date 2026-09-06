import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { CommandResponseDto, LienzoDetailDto } from '../domain/models/uml-editor.models';
import { EditorCommand } from '../domain/commands/editor-commands';

@Injectable({
  providedIn: 'root',
})
export class UmlApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v2/canvases';

  getCanvas(canvasId: string): Observable<LienzoDetailDto> {
    return this.http.get<LienzoDetailDto>(`${this.baseUrl}/${canvasId}`);
  }

  getCanvasByRoom(roomName: string): Observable<LienzoDetailDto> {
    return this.http.get<LienzoDetailDto>(`${this.baseUrl}/by-room/${roomName}`);
  }

  createCanvas(name: string, description?: string): Observable<LienzoDetailDto> {
    return this.http.post<LienzoDetailDto>(this.baseUrl, { name, description });
  }

  sendCommand<T>(canvasId: string, command: EditorCommand<T>): Observable<CommandResponseDto> {
    return this.http.post<CommandResponseDto>(`${this.baseUrl}/${canvasId}/commands`, command);
  }

  listCanvases(): Observable<any[]> {
    return this.http.get<any[]>(this.baseUrl);
  }
}
