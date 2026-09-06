import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ScEmptyStateComponent } from './empty-state.component';

describe('ScEmptyStateComponent', () => {
  let component: ScEmptyStateComponent;
  let fixture: ComponentFixture<ScEmptyStateComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ScEmptyStateComponent],
      providers: [provideZonelessChangeDetection()],
    }).compileComponents();

    fixture = TestBed.createComponent(ScEmptyStateComponent);
    component = fixture.componentInstance;
  });

  it('should create the empty state component', () => {
    expect(component).toBeTruthy();
  });

  it('should render title and description', async () => {
    fixture.componentRef.setInput('title', 'Sin coincidencias');
    fixture.componentRef.setInput('description', 'Prueba con otro término de búsqueda');
    await fixture.whenStable();

    const titleEl: HTMLElement = fixture.nativeElement.querySelector('h3');
    const descEl: HTMLElement = fixture.nativeElement.querySelector('p');
    expect(titleEl.textContent?.trim()).toBe('Sin coincidencias');
    expect(descEl.textContent?.trim()).toBe('Prueba con otro término de búsqueda');
  });

  it('should emit onAction when button is clicked', () => {
    spyOn(component.onAction, 'emit');
    component.actionLabel = 'Nuevo Proyecto';
    component.onAction.emit();

    expect(component.onAction.emit).toHaveBeenCalled();
  });
});
