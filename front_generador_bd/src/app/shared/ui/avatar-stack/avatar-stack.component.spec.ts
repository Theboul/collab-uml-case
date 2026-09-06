import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ScAvatarStackComponent } from './avatar-stack.component';

describe('ScAvatarStackComponent', () => {
  let component: ScAvatarStackComponent;
  let fixture: ComponentFixture<ScAvatarStackComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ScAvatarStackComponent],
      providers: [provideZonelessChangeDetection()],
    }).compileComponents();

    fixture = TestBed.createComponent(ScAvatarStackComponent);
    component = fixture.componentInstance;
  });

  it('should create the avatar stack', () => {
    expect(component).toBeTruthy();
  });

  it('should display visible avatars and compute remaining counter', async () => {
    fixture.componentRef.setInput('avatars', ['Alex Rivera', 'Maria Gomez', 'Carlos Soto', 'Lucia Paz']);
    fixture.componentRef.setInput('max', 2);
    await fixture.whenStable();

    expect(component.visibleAvatars.length).toBe(2);
    expect(component.remainingCount).toBe(2);

    const remainingEl: HTMLElement | null = fixture.nativeElement.querySelector('.font-mono');
    expect(remainingEl?.textContent?.trim()).toBe('+2');
  });

  it('should extract correct initials from full name', () => {
    expect(component.getInitials('Alex Rivera')).toBe('AR');
    expect(component.getInitials('Admin')).toBe('AD');
    expect(component.getInitials('')).toBe('?');
  });
});
