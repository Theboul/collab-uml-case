import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ScIconComponent } from './icon.component';

describe('ScIconComponent', () => {
  let component: ScIconComponent;
  let fixture: ComponentFixture<ScIconComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ScIconComponent],
      providers: [provideZonelessChangeDetection()],
    }).compileComponents();

    fixture = TestBed.createComponent(ScIconComponent);
    component = fixture.componentInstance;
    component.name = 'database';
  });

  it('should create the icon component', () => {
    expect(component).toBeTruthy();
  });

  it('should render the icon name in the span', async () => {
    fixture.componentRef.setInput('name', 'table_chart');
    await fixture.whenStable();

    const spanElement: HTMLElement = fixture.nativeElement.querySelector('span');
    expect(spanElement.textContent?.trim()).toBe('table_chart');
  });

  it('should compute font-variation-settings correctly with filled state', () => {
    component.filled = true;
    component.size = 24;
    expect(component.fontVariation).toContain("'FILL' 1");
    expect(component.fontVariation).toContain("'opsz' 24");
  });
});
