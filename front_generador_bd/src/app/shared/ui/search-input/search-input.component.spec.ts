import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ScSearchInputComponent } from './search-input.component';

describe('ScSearchInputComponent', () => {
  let component: ScSearchInputComponent;
  let fixture: ComponentFixture<ScSearchInputComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ScSearchInputComponent],
      providers: [provideZonelessChangeDetection()],
    }).compileComponents();

    fixture = TestBed.createComponent(ScSearchInputComponent);
    component = fixture.componentInstance;
  });

  it('should create the search input', () => {
    expect(component).toBeTruthy();
  });

  it('should emit searchChange on input event', () => {
    spyOn(component.searchChange, 'emit');
    const mockEvent = {
      target: { value: 'ecommerce' } as unknown as HTMLInputElement,
    } as unknown as Event;

    component.onInputChange(mockEvent);
    expect(component.value).toBe('ecommerce');
    expect(component.searchChange.emit).toHaveBeenCalledWith('ecommerce');
  });

  it('should clear value and emit empty string on clear()', () => {
    spyOn(component.searchChange, 'emit');
    component.value = 'query';
    component.clear();

    expect(component.value).toBe('');
    expect(component.searchChange.emit).toHaveBeenCalledWith('');
  });
});
