import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ScDataTypeTagComponent } from './data-type-tag.component';

describe('ScDataTypeTagComponent', () => {
  let component: ScDataTypeTagComponent;
  let fixture: ComponentFixture<ScDataTypeTagComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ScDataTypeTagComponent],
      providers: [provideZonelessChangeDetection()],
    }).compileComponents();

    fixture = TestBed.createComponent(ScDataTypeTagComponent);
    component = fixture.componentInstance;
  });

  it('should create the data-type-tag component', () => {
    expect(component).toBeTruthy();
  });

  it('should display formatted VARCHAR with length', async () => {
    fixture.componentRef.setInput('type', 'VARCHAR');
    fixture.componentRef.setInput('length', 255);
    await fixture.whenStable();

    expect(component.displayType).toBe('VARCHAR(255)');
    expect(component.category).toBe('string');
    expect(component.categoryClasses).toContain('bg-emerald-500/10');
  });

  it('should classify UUID under id category', async () => {
    fixture.componentRef.setInput('type', 'UUID');
    await fixture.whenStable();

    expect(component.category).toBe('id');
    expect(component.categoryClasses).toContain('bg-purple-500/10');
  });

  it('should display NUMERIC with precision and scale', async () => {
    fixture.componentRef.setInput('type', 'NUMERIC');
    fixture.componentRef.setInput('precision', 10);
    fixture.componentRef.setInput('scale', 2);
    await fixture.whenStable();

    expect(component.displayType).toBe('NUMERIC(10,2)');
    expect(component.category).toBe('number');
  });
});
