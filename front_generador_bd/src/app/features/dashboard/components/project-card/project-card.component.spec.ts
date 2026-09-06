import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ScProjectCardComponent } from './project-card.component';
import { ProjectDto } from '../../dashboard.service';

describe('ScProjectCardComponent', () => {
  let component: ScProjectCardComponent;
  let fixture: ComponentFixture<ScProjectCardComponent>;

  const mockProject: ProjectDto = {
    id: 'p-123',
    name: 'E-commerce Store',
    description: 'Tienda en línea',
    roomName: 'ecommerce-room',
    engine: 'postgresql',
    tableCount: 10,
    relationCount: 8,
    updatedAt: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
    lastOpenedAt: new Date().toISOString(),
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ScProjectCardComponent],
      providers: [provideZonelessChangeDetection()],
    }).compileComponents();

    fixture = TestBed.createComponent(ScProjectCardComponent);
    component = fixture.componentInstance;
    component.project = mockProject;
  });

  it('should create the project card', () => {
    expect(component).toBeTruthy();
  });

  it('should emit onOpen event when card is clicked', () => {
    spyOn(component.onOpen, 'emit');
    component.onOpen.emit(mockProject);
    expect(component.onOpen.emit).toHaveBeenCalledWith(mockProject);
  });

  it('should toggle menu and emit action', () => {
    spyOn(component.onAction, 'emit');
    component.toggleMenu();
    expect(component.menuOpen).toBeTrue();

    component.handleAction('duplicate');
    expect(component.menuOpen).toBeFalse();
    expect(component.onAction.emit).toHaveBeenCalledWith({
      action: 'duplicate',
      project: mockProject,
    });
  });

  it('should calculate relative time', () => {
    expect(component.relativeTime).toContain('min');
  });
});
