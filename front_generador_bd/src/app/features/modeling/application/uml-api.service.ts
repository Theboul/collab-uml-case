import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import {
  CommandResponseDto,
  JoinCanvasResponse,
  LienzoDetailDto,
  ModeloUML,
  UmlRelationDto,
  UmlRelationType,
  ValidationResponseDto,
} from '../domain/models/uml-editor.models';
import { EditorCommand } from '../domain/commands/editor-commands';

interface RawMultiplicity {
  lowerBound: number;
  upperBound: number | null;
}

interface RawAssociationEnd {
  classId: string;
  roleName?: string | null;
  aggregationKind?: 'none' | 'shared' | 'composite';
  multiplicity: RawMultiplicity;
}

interface RawAssociation {
  id: string;
  name?: string | null;
  memberEnds: [RawAssociationEnd, RawAssociationEnd];
}

interface RawGeneralization {
  id: string;
  specificClassId: string;
  generalClassId: string;
}

interface RawDependency {
  id: string;
  clientClassId: string;
  supplierClassId: string;
}

@Injectable({
  providedIn: 'root',
})
export class UmlApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v2/canvases';

  getCanvas(canvasId: string): Observable<LienzoDetailDto> {
    return this.http
      .get<any>(`${this.baseUrl}/${canvasId}`)
      .pipe(map((raw) => this.normalizeCanvas(raw)));
  }

  getCanvasByRoom(roomName: string): Observable<LienzoDetailDto> {
    return this.http
      .get<any>(`${this.baseUrl}/by-room/${roomName}`)
      .pipe(map((raw) => this.normalizeCanvas(raw)));
  }

  joinCanvas(accessCode: string): Observable<JoinCanvasResponse> {
    return this.http.post<JoinCanvasResponse>(`${this.baseUrl}/join`, { accessCode });
  }

  createCanvas(name: string, description?: string): Observable<LienzoDetailDto> {
    return this.http
      .post<any>(this.baseUrl, { name, description })
      .pipe(map((raw) => this.normalizeCanvas(raw)));
  }

  sendCommand<T>(canvasId: string, command: EditorCommand<T>): Observable<CommandResponseDto> {
    return this.http.post<any>(`${this.baseUrl}/${canvasId}/commands`, command).pipe(
      map((raw) => ({
        ...raw,
        canvas: raw.canvas ? this.normalizeCanvas(raw.canvas) : raw.canvas,
      }))
    );
  }

  /** CU6: interpreta una instrucción de texto/voz y la aplica como comandos reales validados. */
  sendTextCommand(canvasId: string, prompt: string, expectedVersion: number): Observable<CommandResponseDto> {
    return this.http
      .post<any>(`${this.baseUrl}/${canvasId}/assistant/text-command`, { prompt, expectedVersion })
      .pipe(
        map((raw) => ({
          ...raw,
          canvas: raw.canvas ? this.normalizeCanvas(raw.canvas) : raw.canvas,
        }))
      );
  }

  /** CU7: interpreta una imagen del diagrama y la aplica como comandos reales validados. */
  sendImageCommand(canvasId: string, image: File, expectedVersion: number): Observable<CommandResponseDto> {
    const formData = new FormData();
    formData.append('image', image, image.name);
    formData.append('expectedVersion', String(expectedVersion));
    return this.http
      .post<any>(`${this.baseUrl}/${canvasId}/assistant/image-command`, formData)
      .pipe(
        map((raw) => ({
          ...raw,
          canvas: raw.canvas ? this.normalizeCanvas(raw.canvas) : raw.canvas,
        }))
      );
  }

  listCanvases(): Observable<any[]> {
    return this.http.get<any[]>(this.baseUrl);
  }

  /** CU9: valida el modelo persistido del lienzo contra el motor real (UMLValidator), no IA. */
  validateCanvas(canvasId: string): Observable<ValidationResponseDto> {
    return this.http.post<ValidationResponseDto>(`${this.baseUrl}/${canvasId}/validate`, {});
  }

  /** CU8: importa un archivo XMI 1.1/UML 1.3 de Enterprise Architect creando un nuevo lienzo persistido. */
  importXmi(file: File): Observable<{ canvas: LienzoDetailDto; validation: ValidationResponseDto }> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    return this.http
      .post<{ canvas: any; validation: ValidationResponseDto }>(`${this.baseUrl}/import`, formData)
      .pipe(
        map((res) => ({
          canvas: this.normalizeCanvas(res.canvas),
          validation: res.validation,
        }))
      );
  }

  /** CU8: descarga el modelo persistido en formato XMI 1.1/UML 1.3 de Enterprise Architect. */
  exportXmi(canvasId: string): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/${canvasId}/export/xmi`, {
      responseType: 'blob',
    });
  }

  /**
   * El backend expone el modelo con `associations`/`generalizations`/`dependencies`
   * separados (contrato `UmlModelSchema`), pero el dominio canónico del frontend
   * (`ModeloUML`) usa un único arreglo `relations`. Sin esta normalización en la
   * frontera HTTP, `model.relations` siempre llega `undefined` y las relaciones se
   * pierden al recargar el lienzo (aunque sí están persistidas en el backend).
   */
  /** Público: también lo usa RemoteCanvasSyncService para normalizar snapshots recibidos por WS. */
  normalizeCanvas(raw: any): LienzoDetailDto {
    return { ...raw, model: this.normalizeModel(raw.model) };
  }

  private normalizeModel(rawModel: any): ModeloUML {
    const relations: UmlRelationDto[] = [
      ...(rawModel?.associations || []).map((a: RawAssociation) => this.associationToRelation(a)),
      ...(rawModel?.generalizations || []).map((g: RawGeneralization) => this.generalizationToRelation(g)),
      ...(rawModel?.dependencies || []).map((d: RawDependency) => this.dependencyToRelation(d)),
    ];
    return { classes: rawModel?.classes || [], relations };
  }

  private associationToRelation(a: RawAssociation): UmlRelationDto {
    const [source, target] = a.memberEnds;
    const type: UmlRelationType =
      source.aggregationKind === 'composite' || target.aggregationKind === 'composite'
        ? 'COMPOSITION'
        : source.aggregationKind === 'shared' || target.aggregationKind === 'shared'
          ? 'AGGREGATION'
          : 'ASSOCIATION';

    return {
      id: a.id,
      name: a.name,
      type,
      sourceClassId: source.classId,
      targetClassId: target.classId,
      sourceRole: source.roleName,
      targetRole: target.roleName,
      sourceMultiplicity: this.formatMultiplicity(source.multiplicity),
      targetMultiplicity: this.formatMultiplicity(target.multiplicity),
    };
  }

  private generalizationToRelation(g: RawGeneralization): UmlRelationDto {
    return {
      id: g.id,
      type: 'GENERALIZATION',
      sourceClassId: g.specificClassId,
      targetClassId: g.generalClassId,
      sourceMultiplicity: '',
      targetMultiplicity: '',
    };
  }

  private dependencyToRelation(d: RawDependency): UmlRelationDto {
    return {
      id: d.id,
      type: 'DEPENDENCY',
      sourceClassId: d.clientClassId,
      targetClassId: d.supplierClassId,
      sourceMultiplicity: '',
      targetMultiplicity: '',
    };
  }

  private formatMultiplicity(m: RawMultiplicity): string {
    if (m.upperBound === null || m.upperBound === undefined) {
      return m.lowerBound === 0 ? '*' : `${m.lowerBound}..*`;
    }
    if (m.lowerBound === m.upperBound) {
      return `${m.lowerBound}`;
    }
    return `${m.lowerBound}..${m.upperBound}`;
  }
}

