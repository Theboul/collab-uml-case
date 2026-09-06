import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ScNewProjectModalComponent } from './new-project-modal.component';

describe('ScNewProjectModalComponent', () => {
  let component: ScNewProjectModalComponent;
  let fixture: ComponentFixture<ScNewProjectModalComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ScNewProjectModalComponent],
      providers: [provideZonelessChangeDetection()],
    }).compileComponents();

    fixture = TestBed.createComponent(ScNewProjectModalComponent);
    component = fixture.componentInstance;
  });

  it('should create the new project modal', () => {
    expect(component).toBeTruthy();
  });

  it('should validate short or empty name on submit', () => {
    component.name = 'ab';
    component.submit();

    expect(component.nameError).toBe('El nombre debe tener al menos 3 caracteres.');

    component.name = '';
    component.submit();
    expect(component.nameError).toBe('El nombre del proyecto es obligatorio.');
  });

  it('should emit onCreate with name and selected engine', () => {
    spyOn(component.onCreate, 'emit');
    component.name = 'Sistema Logística';
    component.engine = 'mysql';

    component.submit();
    expect(component.nameError).toBeNull();
    expect(component.onCreate.emit).toHaveBeenCalledWith({
      name: 'Sistema Logística',
      engine: 'mysql',
    });
  });

  it('should reset fields on close()', () => {
    spyOn(component.onClose, 'emit');
    component.name = 'Test';
    component.nameError = 'Some error';

    component.close();
    expect(component.name).toBe('');
    expect(component.nameError).toBeNull();
    expect(component.onClose.emit).toHaveBeenCalled();
  });
});
