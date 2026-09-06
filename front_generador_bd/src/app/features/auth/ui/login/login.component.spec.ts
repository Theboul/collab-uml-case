import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { Router } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ScLoginComponent } from './login.component';
import { AuthService } from '../../../../core/auth';

describe('ScLoginComponent', () => {
  let component: ScLoginComponent;
  let fixture: ComponentFixture<ScLoginComponent>;
  let routerSpy: jasmine.SpyObj<Router>;
  let authServiceSpy: jasmine.SpyObj<AuthService>;

  beforeEach(async () => {
    routerSpy = jasmine.createSpyObj('Router', ['navigate']);
    authServiceSpy = jasmine.createSpyObj('AuthService', [
      'login',
      'register',
      'loginWithGoogle',
      'getAuthConfig',
    ]);
    authServiceSpy.getAuthConfig.and.returnValue(
      of({ googleClientId: 'mock-google-client-id' })
    );

    await TestBed.configureTestingModule({
      imports: [ScLoginComponent],
      providers: [
        provideZonelessChangeDetection(),
        { provide: Router, useValue: routerSpy },
        { provide: AuthService, useValue: authServiceSpy },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ScLoginComponent);
    component = fixture.componentInstance;
  });

  it('should create the login component', () => {
    expect(component).toBeTruthy();
    expect(component.mode).toBe('login');
  });

  it('should toggle auth mode between login and register', () => {
    component.toggleMode('register');
    expect(component.mode).toBe('register');
    expect(component.generalError).toBeNull();

    component.toggleMode('login');
    expect(component.mode).toBe('login');
  });

  it('should validate invalid email and short password', () => {
    component.email = 'invalido';
    component.password = '123';

    const isValid = component.validateForm();
    expect(isValid).toBeFalse();
    expect(component.errors.email).toBe('Ingresa un correo electrónico válido.');
    expect(component.errors.password).toBe('La contraseña debe tener al menos 6 caracteres.');
  });

  it('should require fullName in register mode', () => {
    component.mode = 'register';
    component.email = 'usuario@empresa.com';
    component.password = '123456';
    component.fullName = '';

    const isValid = component.validateForm();
    expect(isValid).toBeFalse();
    expect(component.errors.fullName).toBe('Ingresa tu nombre completo.');
  });

  describe('Authentication API flows', () => {
    it('should navigate to dashboard upon successful login', () => {
      authServiceSpy.login.and.returnValue(
        of({
          accessToken: 'token',
          tokenType: 'Bearer',
          expiresIn: 900,
          user: { id: '1', email: 'dev@empresa.com', fullName: 'Dev' },
        })
      );

      component.mode = 'login';
      component.email = 'dev@empresa.com';
      component.password = 'secreto123';

      component.onSubmit();

      expect(authServiceSpy.login).toHaveBeenCalledWith({
        email: 'dev@empresa.com',
        password: 'secreto123',
      });
      expect(component.loading).toBeFalse();
      expect(routerSpy.navigate).toHaveBeenCalledWith(['/dashboard']);
    });

    it('should display error message upon login failure', () => {
      authServiceSpy.login.and.returnValue(
        throwError(() => ({
          error: { code: 'AUTH_INVALID_CREDENTIALS', message: 'Credenciales inválidas' },
        }))
      );

      component.mode = 'login';
      component.email = 'dev@empresa.com';
      component.password = 'secreto123';

      component.onSubmit();

      expect(component.loading).toBeFalse();
      expect(component.generalError).toBe('Correo o contraseña incorrectos.');
      expect(routerSpy.navigate).not.toHaveBeenCalled();
    });

    it('should register and navigate to dashboard upon successful register', () => {
      authServiceSpy.register.and.returnValue(
        of({
          accessToken: 'token',
          tokenType: 'Bearer',
          expiresIn: 900,
          user: { id: '1', email: 'new@empresa.com', fullName: 'New Dev' },
        })
      );

      component.mode = 'register';
      component.fullName = 'New Dev';
      component.email = 'new@empresa.com';
      component.password = 'secreto123';

      component.onSubmit();

      expect(authServiceSpy.register).toHaveBeenCalledWith({
        fullName: 'New Dev',
        email: 'new@empresa.com',
        password: 'secreto123',
      });
      expect(component.loading).toBeFalse();
      expect(routerSpy.navigate).toHaveBeenCalledWith(['/dashboard']);
    });

    it('should authenticate with google credential and navigate to dashboard', () => {
      authServiceSpy.loginWithGoogle.and.returnValue(
        of({
          accessToken: 'token',
          tokenType: 'Bearer',
          expiresIn: 900,
          user: { id: '1', email: 'google@empresa.com', fullName: 'Google User' },
        })
      );

      component.handleGoogleCredential({ credential: 'mock-google-credential' });

      expect(authServiceSpy.loginWithGoogle).toHaveBeenCalledWith('mock-google-credential');
      expect(component.loading).toBeFalse();
      expect(routerSpy.navigate).toHaveBeenCalledWith(['/dashboard']);
    });
  });
});
