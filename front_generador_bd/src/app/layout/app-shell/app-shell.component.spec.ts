import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { provideRouter, Router } from '@angular/router';
import { ScAppShellComponent } from './app-shell.component';

describe('ScAppShellComponent', () => {
  let component: ScAppShellComponent;
  let fixture: ComponentFixture<ScAppShellComponent>;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ScAppShellComponent],
      providers: [
        provideZonelessChangeDetection(),
        provideRouter([]),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ScAppShellComponent);
    component = fixture.componentInstance;
    router = TestBed.inject(Router);
    spyOn(router, 'navigate');
  });

  it('should create the app shell component', () => {
    expect(component).toBeTruthy();
  });

  it('should compute user initials properly', () => {
    component.userName = 'Alex Rivera';
    expect(component.userInitials).toBe('AR');

    component.userName = 'Carlos';
    expect(component.userInitials).toBe('CA');
  });

  it('should clear storage and navigate to /login on logout', () => {
    component.logout();
    expect(router.navigate).toHaveBeenCalledWith(['/login']);
  });
});
