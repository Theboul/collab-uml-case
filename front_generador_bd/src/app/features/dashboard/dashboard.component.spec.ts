import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { provideRouter, Router } from '@angular/router';
import { of, throwError } from 'rxjs';
import { DashboardComponent } from './dashboard.component';
import { DashboardService, ProjectDto } from './dashboard.service';
import { AuthService } from '../../core/auth';
import { UmlApiService } from '../modeling/application/uml-api.service';

describe('DashboardComponent', () => {
  let component: DashboardComponent;
  let fixture: ComponentFixture<DashboardComponent>;
  let router: Router;
  let dashboardServiceSpy: jasmine.SpyObj<DashboardService>;
  let umlApiSpy: jasmine.SpyObj<UmlApiService>;

  const mockProjects: ProjectDto[] = [
    {
      id: 'p1',
      name: 'E-commerce Multi-vendor',
      description: 'Marketplace',
      roomName: 'ecommerce-room',
      engine: 'postgresql',
      tableCount: 8,
      relationCount: 6,
      updatedAt: '2026-09-05T13:48:00Z',
      lastOpenedAt: '2026-09-05T13:48:00Z',
    },
    {
      id: 'p2',
      name: 'Mobile Telemetry',
      description: 'IoT metrics',
      roomName: 'telemetry-room',
      engine: 'mysql',
      tableCount: 14,
      relationCount: 10,
      updatedAt: '2026-09-04T13:48:00Z',
      lastOpenedAt: '2026-09-04T13:48:00Z',
    },
  ];

  beforeEach(async () => {
    dashboardServiceSpy = jasmine.createSpyObj('DashboardService', [
      'getMetrics',
      'getRecentProjects',
      'getAllProjects',
      'createProject',
      'joinProjectByRoomCode',
      'deleteProject',
      'duplicateProject',
    ]);

    dashboardServiceSpy.getMetrics.and.returnValue(
      of({
        totalEntities: 22,
        activeProjects: 2,
        referentialIntegrity: 98,
      }),
    );
    dashboardServiceSpy.getRecentProjects.and.returnValue(of([mockProjects[0]]));
    dashboardServiceSpy.getAllProjects.and.returnValue(of(mockProjects));

    const authServiceSpy = jasmine.createSpyObj('AuthService', ['logout'], {
      currentUser: signal<any>({
        id: 'usr-1',
        email: 'alex@schemacraft.dev',
        fullName: 'Alex Rivera',
      }),
    });

    // El componente inyecta UmlApiService (import XMI), que a su vez necesita HttpClient:
    // se sustituye por un spy para que el test no toque la red ni exija provideHttpClient.
    umlApiSpy = jasmine.createSpyObj('UmlApiService', ['importXmi']);

    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        provideZonelessChangeDetection(),
        provideRouter([]),
        { provide: DashboardService, useValue: dashboardServiceSpy },
        { provide: AuthService, useValue: authServiceSpy },
        { provide: UmlApiService, useValue: umlApiSpy },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(DashboardComponent);
    component = fixture.componentInstance;
    router = TestBed.inject(Router);
    spyOn(router, 'navigate');
  });

  it('should create the dashboard component', () => {
    expect(component).toBeTruthy();
  });

  it('should load metrics and projects on initialization', () => {
    component.ngOnInit();

    expect(dashboardServiceSpy.getMetrics).toHaveBeenCalled();
    expect(dashboardServiceSpy.getRecentProjects).toHaveBeenCalledWith(3);
    expect(dashboardServiceSpy.getAllProjects).toHaveBeenCalled();
    expect(component.metrics().totalEntities).toBe(22);
    expect(component.allProjects().length).toBe(2);
    expect(component.filteredProjects().length).toBe(2);
  });

  it('should filter projects by text search query', () => {
    component.allProjects.set(mockProjects);
    component.onSearchChange('telemetry');

    expect(component.filteredProjects().length).toBe(1);
    expect(component.filteredProjects()[0].name).toBe('Mobile Telemetry');
  });

  it('should filter projects by database engine', () => {
    component.allProjects.set(mockProjects);
    component.setEngineFilter('postgresql');

    expect(component.filteredProjects().length).toBe(1);
    expect(component.filteredProjects()[0].engine).toBe('postgresql');
  });

  it('should navigate to diagram when opening a project', () => {
    component.openProject(mockProjects[0]);
    expect(router.navigate).toHaveBeenCalledWith(['/diagram', 'ecommerce-room']);
  });

  it('should open new project modal', () => {
    component.openNewProjectModal();
    expect(component.isNewModalOpen).toBeTrue();
  });

  it('should open join modal', () => {
    component.openJoinModal();
    expect(component.isJoinModalOpen).toBeTrue();
  });

  describe('importXmiFile', () => {
    const fileEvent = (file: File | null): Event => {
      const input = { files: file ? [file] : [], value: 'model.xmi' };
      return { target: input } as unknown as Event;
    };

    it('should navigate to the imported canvas room on success', () => {
      const file = new File(['<xmi/>'], 'model.xmi');
      umlApiSpy.importXmi.and.returnValue(
        of({ canvas: { roomName: 'imported-room' } }) as unknown as ReturnType<
          UmlApiService['importXmi']
        >,
      );
      const event = fileEvent(file);

      component.importXmiFile(event);

      expect(umlApiSpy.importXmi).toHaveBeenCalledWith(file);
      expect(router.navigate).toHaveBeenCalledWith(['/diagram', 'imported-room']);
      expect(component.isImportingXmi).toBeFalse();
      expect((event.target as HTMLInputElement).value).toBe('');
    });

    it('should do nothing when no file is selected', () => {
      component.importXmiFile(fileEvent(null));

      expect(umlApiSpy.importXmi).not.toHaveBeenCalled();
      expect(component.isImportingXmi).toBeFalse();
    });

    it('should reset the importing state and alert when the import fails', () => {
      const alertSpy = spyOn(window, 'alert');
      umlApiSpy.importXmi.and.returnValue(
        throwError(() => ({ error: { message: 'XMI inválido' } })),
      );

      component.importXmiFile(fileEvent(new File(['x'], 'bad.xmi')));

      expect(component.isImportingXmi).toBeFalse();
      expect(alertSpy).toHaveBeenCalledWith('Error de importación: XMI inválido');
      expect(router.navigate).not.toHaveBeenCalled();
    });
  });
});
