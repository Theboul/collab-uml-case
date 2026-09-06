import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { provideRouter, Router } from '@angular/router';
import { of } from 'rxjs';
import { DashboardComponent } from './dashboard.component';
import { DashboardService, ProjectDto } from './dashboard.service';
import { AuthService } from '../../core/auth';

describe('DashboardComponent', () => {
  let component: DashboardComponent;
  let fixture: ComponentFixture<DashboardComponent>;
  let router: Router;
  let dashboardServiceSpy: jasmine.SpyObj<DashboardService>;

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

    dashboardServiceSpy.getMetrics.and.returnValue(of({
      totalEntities: 22,
      activeProjects: 2,
      referentialIntegrity: 98,
    }));
    dashboardServiceSpy.getRecentProjects.and.returnValue(of([mockProjects[0]]));
    dashboardServiceSpy.getAllProjects.and.returnValue(of(mockProjects));

    const authServiceSpy = jasmine.createSpyObj('AuthService', ['logout'], {
      currentUser: signal<any>({
        id: 'usr-1',
        email: 'alex@schemacraft.dev',
        fullName: 'Alex Rivera',
      }),
    });

    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        provideZonelessChangeDetection(),
        provideRouter([]),
        { provide: DashboardService, useValue: dashboardServiceSpy },
        { provide: AuthService, useValue: authServiceSpy },
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
    expect(component.metrics.totalEntities).toBe(22);
    expect(component.allProjects.length).toBe(2);
    expect(component.filteredProjects.length).toBe(2);
  });

  it('should filter projects by text search query', () => {
    component.allProjects = mockProjects;
    component.onSearchChange('telemetry');

    expect(component.filteredProjects.length).toBe(1);
    expect(component.filteredProjects[0].name).toBe('Mobile Telemetry');
  });

  it('should filter projects by database engine', () => {
    component.allProjects = mockProjects;
    component.setEngineFilter('postgresql');

    expect(component.filteredProjects.length).toBe(1);
    expect(component.filteredProjects[0].engine).toBe('postgresql');
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
});
