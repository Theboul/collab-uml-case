import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ScButtonComponent } from './button.component';

describe('ScButtonComponent', () => {
  let component: ScButtonComponent;
  let fixture: ComponentFixture<ScButtonComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ScButtonComponent],
      providers: [provideZonelessChangeDetection()],
    }).compileComponents();

    fixture = TestBed.createComponent(ScButtonComponent);
    component = fixture.componentInstance;
  });

  it('should create the button', () => {
    expect(component).toBeTruthy();
  });

  it('should emit onClick when clicked and not disabled/loading', () => {
    spyOn(component.onClick, 'emit');
    const mockEvent = new MouseEvent('click');

    component.handleClick(mockEvent);
    expect(component.onClick.emit).toHaveBeenCalledWith(mockEvent);
  });

  it('should NOT emit onClick when disabled', () => {
    spyOn(component.onClick, 'emit');
    component.disabled = true;

    component.handleClick(new MouseEvent('click'));
    expect(component.onClick.emit).not.toHaveBeenCalled();
  });

  it('should NOT emit onClick when loading', () => {
    spyOn(component.onClick, 'emit');
    component.loading = true;

    component.handleClick(new MouseEvent('click'));
    expect(component.onClick.emit).not.toHaveBeenCalled();
  });

  it('should calculate correct variant and size classes', () => {
    component.variant = 'primary';
    component.size = 'lg';
    expect(component.variantClasses).toContain('bg-primary');
    expect(component.sizeClasses).toContain('h-11');
  });
});
