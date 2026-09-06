import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ScInputComponent } from './input.component';

describe('ScInputComponent', () => {
  let component: ScInputComponent;
  let fixture: ComponentFixture<ScInputComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ScInputComponent],
      providers: [provideZonelessChangeDetection()],
    }).compileComponents();

    fixture = TestBed.createComponent(ScInputComponent);
    component = fixture.componentInstance;
    component.inputId = 'test-input';
  });

  it('should create the input component', () => {
    expect(component).toBeTruthy();
  });

  it('should toggle password visibility between password and text', () => {
    component.type = 'password';
    expect(component.actualType).toBe('password');

    component.togglePasswordVisibility();
    expect(component.showPassword).toBeTrue();
    expect(component.actualType).toBe('text');

    component.togglePasswordVisibility();
    expect(component.showPassword).toBeFalse();
    expect(component.actualType).toBe('password');
  });

  it('should propagate value changes through ControlValueAccessor', () => {
    const spy = jasmine.createSpy('onChangeSpy');
    component.registerOnChange(spy);

    const inputEvent = {
      target: { value: 'test@example.com' } as unknown as HTMLInputElement,
    } as unknown as Event;

    component.onInputChange(inputEvent);
    expect(component.value).toBe('test@example.com');
    expect(spy).toHaveBeenCalledWith('test@example.com');
  });

  it('should display error message when error input is provided', async () => {
    fixture.componentRef.setInput('error', 'Campo obligatorio');
    await fixture.whenStable();

    const errorEl: HTMLElement = fixture.nativeElement.querySelector('.error-message');
    expect(errorEl.textContent?.trim()).toBe('Campo obligatorio');
  });
});
