import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ScBadgeComponent } from './badge.component';

describe('ScBadgeComponent', () => {
  let component: ScBadgeComponent;
  let fixture: ComponentFixture<ScBadgeComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ScBadgeComponent],
      providers: [provideZonelessChangeDetection()],
    }).compileComponents();

    fixture = TestBed.createComponent(ScBadgeComponent);
    component = fixture.componentInstance;
  });

  it('should create the badge component', () => {
    expect(component).toBeTruthy();
  });

  it('should render PK badge with Primary Key tooltip', async () => {
    fixture.componentRef.setInput('type', 'PK');
    await fixture.whenStable();

    const badgeSpan: HTMLElement = fixture.nativeElement.querySelector('span');
    expect(badgeSpan.textContent?.trim()).toBe('PK');
    expect(badgeSpan.getAttribute('title')).toBe('Primary Key');
    expect(component.typeClasses).toContain('bg-amber-500/15');
  });

  it('should render custom label when provided', async () => {
    fixture.componentRef.setInput('type', 'FK');
    fixture.componentRef.setInput('label', 'REF');
    await fixture.whenStable();

    const badgeSpan: HTMLElement = fixture.nativeElement.querySelector('span');
    expect(badgeSpan.textContent?.trim()).toBe('REF');
    expect(badgeSpan.getAttribute('title')).toBe('Foreign Key');
  });
});
