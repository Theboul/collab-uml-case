import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { provideRouter, Router } from '@angular/router';
import { of } from 'rxjs';
import { ScAppShellComponent } from './app-shell.component';
import { AuthService, UserDto } from '../../core/auth';

describe('ScAppShellComponent', () => {
  let component: ScAppShellComponent;
  let fixture: ComponentFixture<ScAppShellComponent>;
  let router: Router;
  let authServiceSpy: jasmine.SpyObj<AuthService>;

  beforeEach(async () => {
    authServiceSpy = jasmine.createSpyObj('AuthService', ['logout'], {
      currentUser: signal<UserDto | null>({
        id: 'usr-1',
        email: 'alex.rivera@ejemplo.com',
        fullName: 'Alex Rivera',
      }),
    });
    authServiceSpy.logout.and.returnValue(of(undefined));

    await TestBed.configureTestingModule({
      imports: [ScAppShellComponent],
      providers: [
        provideZonelessChangeDetection(),
        provideRouter([]),
        { provide: AuthService, useValue: authServiceSpy },
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

  it('should initialize user name from authService currentUser signal', () => {
    component.ngOnInit();
    expect(component.userName).toBe('Alex Rivera');
    expect(component.userEmail).toBe('alex.rivera@ejemplo.com');
  });

  it('should compute user initials properly', () => {
    component.userName = 'Alex Rivera';
    expect(component.userInitials).toBe('AR');

    component.userName = 'Carlos';
    expect(component.userInitials).toBe('CA');
  });

  it('should call authService.logout and navigate to /login on logout', () => {
    component.logout();
    expect(authServiceSpy.logout).toHaveBeenCalled();
    expect(router.navigate).toHaveBeenCalledWith(['/login']);
  });
});
