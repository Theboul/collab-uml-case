// features/dashboard/dashboard.service.ts
//
// Servicio del Dashboard — SchemaCraft
// Por ahora devuelve datos MOCK (Observable simulado con delay).
// Cuando exista el backend real, solo se reemplaza el cuerpo de cada método
// por una llamada HttpClient — la forma de ProjectDto y la interfaz pública
// del servicio (los nombres de método y lo que retornan) NO deberían cambiar,
// para que el componente que ya lo consume no se vea afectado.

import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, delay, map, of } from 'rxjs';

// ─────────────────────────────────────────────────────────
// Contratos (basados 1:1 en el diseño de datos real: tabla `projects`)
// ─────────────────────────────────────────────────────────

export type DbEngine = 'postgresql' | 'mysql' | 'sqlite';

export interface ProjectDto {
  id: string;
  name: string;
  description: string | null;
  roomName: string;
  engine: DbEngine;
  tableCount: number;      // derivado de model_json.classes.length
  relationCount: number;   // derivado de model_json.relations.length
  updatedAt: string;       // ISO date
  lastOpenedAt: string;    // ISO date
}

export interface DashboardMetrics {
  totalEntities: number;      // suma de tableCount de todos los proyectos
  activeProjects: number;     // count de proyectos no archivados
  referentialIntegrity: number; // % de relaciones válidas (0-100)
}

export type ProjectSortBy = 'updatedAt' | 'name' | 'tableCount';

// ─────────────────────────────────────────────────────────
// Datos Mock de respaldo (desarrollo local / offline)
// ─────────────────────────────────────────────────────────

const MOCK_PROJECTS: ProjectDto[] = [
  {
    id: '1a2b3c4d-0001-4000-8000-000000000001',
    name: 'E-Commerce Core',
    description: 'Diagrama principal de órdenes, pagos e inventario',
    roomName: 'room-ecom01',
    engine: 'postgresql',
    tableCount: 12,
    relationCount: 18,
    updatedAt: new Date(Date.now() - 1000 * 60 * 25).toISOString(),
    lastOpenedAt: new Date(Date.now() - 1000 * 60 * 25).toISOString(),
  },
  {
    id: '1a2b3c4d-0002-4000-8000-000000000002',
    name: 'Auth & Multi-tenancy',
    description: 'Esquema de identidades, roles, permisos y sesiones',
    roomName: 'room-auth02',
    engine: 'postgresql',
    tableCount: 6,
    relationCount: 7,
    updatedAt: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
    lastOpenedAt: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
  },
];

function calculateMockMetrics(projects: ProjectDto[]): DashboardMetrics {
  const totalEntities = projects.reduce((sum, p) => sum + p.tableCount, 0);
  const activeProjects = projects.length;
  const referentialIntegrity = 98; // mock fijo, hasta tener el cálculo real

  return { totalEntities, activeProjects, referentialIntegrity };
}

// ─────────────────────────────────────────────────────────
// Servicio
// ─────────────────────────────────────────────────────────

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly http = inject(HttpClient);

  /** Proyectos recientes, ordenados por último acceso. Máx. 3 para la sección "Recientes". */
  getRecentProjects(limit = 3): Observable<ProjectDto[]> {
    return this.getAllProjects().pipe(
      map((projs) => projs.slice(0, limit))
    );
  }

  /** Todos los proyectos del usuario desde /api/v2/canvases con fallback mock. */
  getAllProjects(sortBy: ProjectSortBy = 'updatedAt', search = ''): Observable<ProjectDto[]> {
    return this.http.get<any[]>('/api/v2/canvases').pipe(
      map((canvases) => {
        if (!Array.isArray(canvases) || canvases.length === 0) {
          return MOCK_PROJECTS;
        }
        return canvases.map((c) => ({
          id: c.id,
          name: c.name,
          description: c.description ?? null,
          roomName: c.roomName || c.room_name || `room-${c.id.slice(0, 8)}`,
          engine: 'postgresql' as DbEngine,
          tableCount: c.tableCount ?? 0,
          relationCount: c.relationCount ?? 0,
          updatedAt: c.updated_at || new Date().toISOString(),
          lastOpenedAt: c.updated_at || new Date().toISOString(),
        }));
      }),
      map((projects) => {
        let result = [...projects];
        if (search.trim()) {
          const q = search.toLowerCase();
          result = result.filter((p) => p.name.toLowerCase().includes(q));
        }
        result.sort((a, b) => {
          if (sortBy === 'name') return a.name.localeCompare(b.name);
          if (sortBy === 'tableCount') return b.tableCount - a.tableCount;
          return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
        });
        return result;
      }),
      catchError(() => of(MOCK_PROJECTS))
    );
  }

  /** Métricas agregadas para el banner de bienvenida. */
  getMetrics(): Observable<DashboardMetrics> {
    return this.getAllProjects().pipe(
      map((projs) => calculateMockMetrics(projs))
    );
  }

  /** Crea un proyecto nuevo vacío y devuelve su id para navegar al editor. */
  createProject(name: string, engine: DbEngine): Observable<ProjectDto> {
    return this.http.post<any>('/api/v2/canvases', { name }).pipe(
      map((res) => ({
        id: res.id,
        name: res.name,
        description: res.description,
        roomName: res.roomName || res.room_name || `room-${res.id.slice(0, 8)}`,
        engine,
        tableCount: res.model?.classes?.length ?? 0,
        relationCount: res.model?.associations?.length ?? 0,
        updatedAt: res.updated_at || new Date().toISOString(),
        lastOpenedAt: new Date().toISOString(),
      })),
      catchError(() => {
        const fallbackRoom = `room-${crypto.randomUUID().slice(0, 8)}`;
        return of({
          id: crypto.randomUUID(),
          name,
          description: null,
          roomName: fallbackRoom,
          engine,
          tableCount: 0,
          relationCount: 0,
          updatedAt: new Date().toISOString(),
          lastOpenedAt: new Date().toISOString(),
        });
      })
    );
  }

  /** Unirse a un proyecto compartido mediante su room_name (UUID/código de sala). */
  joinProjectByRoomCode(roomCode: string): Observable<ProjectDto | null> {
    return this.http.get<any>(`/api/v2/canvases/by-room/${roomCode}`).pipe(
      map((res) => ({
        id: res.id,
        name: res.name,
        description: res.description ?? null,
        roomName: res.roomName || res.room_name || roomCode,
        engine: 'postgresql' as DbEngine,
        tableCount: res.model?.classes?.length ?? 0,
        relationCount: res.model?.associations?.length ?? 0,
        updatedAt: res.updated_at || new Date().toISOString(),
        lastOpenedAt: new Date().toISOString(),
      })),
      catchError(() => {
        const found = MOCK_PROJECTS.find((p) => p.roomName === roomCode) ?? null;
        return of(found);
      })
    );
  }

  deleteProject(projectId: string): Observable<void> {
    return of(undefined).pipe(delay(300));
    // return this.http.delete<void>(`/api/projects/${projectId}`);
  }

  duplicateProject(projectId: string): Observable<ProjectDto> {
    const original = MOCK_PROJECTS.find(p => p.id === projectId);
    const copy: ProjectDto = {
      ...original!,
      id: crypto.randomUUID(),
      name: `${original!.name} (copia)`,
      roomName: `${original!.roomName}-copy-${Math.random().toString(36).slice(2, 6)}`,
      updatedAt: new Date().toISOString(),
      lastOpenedAt: new Date().toISOString(),
    };
    return of(copy).pipe(delay(300));
    // return this.http.post<ProjectDto>(`/api/projects/${projectId}/duplicate`, {});
  }
}
