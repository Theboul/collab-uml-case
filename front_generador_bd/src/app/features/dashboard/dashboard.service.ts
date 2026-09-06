// features/dashboard/dashboard.service.ts
//
// Servicio del Dashboard — SchemaCraft
// Por ahora devuelve datos MOCK (Observable simulado con delay).
// Cuando exista el backend real, solo se reemplaza el cuerpo de cada método
// por una llamada HttpClient — la forma de ProjectDto y la interfaz pública
// del servicio (los nombres de método y lo que retornan) NO deberían cambiar,
// para que el componente que ya lo consume no se vea afectado.

import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { delay } from 'rxjs/operators';

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
// Datos MOCK — reemplazar por respuestas reales del backend
// ─────────────────────────────────────────────────────────

const MOCK_PROJECTS: ProjectDto[] = [
  {
    id: 'a1b2c3d4-0001',
    name: 'E-commerce Multi-vendor',
    description: 'Modelo de marketplace con vendedores y comisiones',
    roomName: 'ecommerce-multivendor-8f3k',
    engine: 'postgresql',
    tableCount: 8,
    relationCount: 6,
    updatedAt: '2026-09-05T13:48:00Z',
    lastOpenedAt: '2026-09-05T13:48:00Z',
  },
  {
    id: 'a1b2c3d4-0002',
    name: 'SaaS Billing & Subscriptions',
    description: 'Suscripciones, planes y facturación recurrente',
    roomName: 'saas-billing-x92p',
    engine: 'postgresql',
    tableCount: 11,
    relationCount: 9,
    updatedAt: '2026-09-05T11:10:00Z',
    lastOpenedAt: '2026-09-05T11:10:00Z',
  },
  {
    id: 'a1b2c3d4-0003',
    name: 'Analytics Warehouse',
    description: 'Modelo estrella para métricas de producto',
    roomName: 'analytics-warehouse-q71z',
    engine: 'postgresql',
    tableCount: 19,
    relationCount: 14,
    updatedAt: '2026-09-04T16:00:00Z',
    lastOpenedAt: '2026-09-04T16:00:00Z',
  },
  {
    id: 'a1b2c3d4-0004',
    name: 'IAM & Auth Core',
    description: 'Usuarios, roles y permisos',
    roomName: 'iam-auth-core-r55t',
    engine: 'postgresql',
    tableCount: 6,
    relationCount: 5,
    updatedAt: '2026-09-03T09:20:00Z',
    lastOpenedAt: '2026-09-03T09:20:00Z',
  },
];

// Simula la validez referencial contando relaciones "sanas" vs. totales.
// En el backend real esto lo calcularía uml_domain al validar model_json.
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

  /** Proyectos recientes, ordenados por último acceso. Máx. 3 para la sección "Recientes". */
  getRecentProjects(limit = 3): Observable<ProjectDto[]> {
    const sorted = [...MOCK_PROJECTS].sort(
      (a, b) => new Date(b.lastOpenedAt).getTime() - new Date(a.lastOpenedAt).getTime()
    );
    return of(sorted.slice(0, limit)).pipe(delay(300));

    // Backend real (referencia):
    // return this.http.get<ProjectDto[]>(`/api/projects/recent?limit=${limit}`);
  }

  /** Todos los proyectos del usuario, con orden y filtro opcional por nombre. */
  getAllProjects(sortBy: ProjectSortBy = 'updatedAt', search = ''): Observable<ProjectDto[]> {
    let result = [...MOCK_PROJECTS];

    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(p => p.name.toLowerCase().includes(q));
    }

    result.sort((a, b) => {
      if (sortBy === 'name') return a.name.localeCompare(b.name);
      if (sortBy === 'tableCount') return b.tableCount - a.tableCount;
      return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
    });

    return of(result).pipe(delay(300));

    // Backend real (referencia):
    // return this.http.get<ProjectDto[]>(`/api/projects?sortBy=${sortBy}&search=${search}`);
  }

  /** Métricas agregadas para el banner de bienvenida. */
  getMetrics(): Observable<DashboardMetrics> {
    return of(calculateMockMetrics(MOCK_PROJECTS)).pipe(delay(300));

    // Backend real (referencia):
    // return this.http.get<DashboardMetrics>('/api/dashboard/metrics');
  }

  /** Crea un proyecto nuevo vacío y devuelve su id para navegar al editor. */
  createProject(name: string, engine: DbEngine): Observable<ProjectDto> {
    const newProject: ProjectDto = {
      id: crypto.randomUUID(),
      name,
      description: null,
      roomName: `${name.toLowerCase().replace(/\s+/g, '-')}-${Math.random().toString(36).slice(2, 6)}`,
      engine,
      tableCount: 0,
      relationCount: 0,
      updatedAt: new Date().toISOString(),
      lastOpenedAt: new Date().toISOString(),
    };
    return of(newProject).pipe(delay(300));

    // Backend real (referencia):
    // return this.http.post<ProjectDto>('/api/projects', { name, engine });
  }

  /** Unirse a un proyecto compartido mediante su room_name (UUID/código de sala). */
  joinProjectByRoomCode(roomCode: string): Observable<ProjectDto | null> {
    const found = MOCK_PROJECTS.find(p => p.roomName === roomCode) ?? null;
    return of(found).pipe(delay(300));

    // Backend real (referencia):
    // return this.http.get<ProjectDto>(`/api/projects/by-room/${roomCode}`);
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
