import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { Router } from '@angular/router';
import { ScLoginComponent } from './login.component';

describe('ScLoginComponent', () => {
  let component: ScLoginComponent;
  let fixture: ComponentFixture<ScLoginComponent>;
  let routerSpy: jasmine.SpyObj<Router>;

  beforeEach(async () => {
    routerSpy = jasmine.createSpyObj('Router', ['navigate']);

    await TestBed.configureTestingModule({
      imports: [ScLoginComponent],
      providers: [
        provideZonelessChangeDetection(),
        { provide: Router, useValue: routerSpy },
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

  describe('Asynchronous Authentication flows', () => {
    beforeEach(() => {
      jasmine.clock().install();
    });

    afterEach(() => {
      jasmine.clock().uninstall();
    });

    it('should navigate to diagram upon successful login', () => {
      component.mode = 'login';
      component.email = 'dev@empresa.com';
      component.password = 'secreto123';

      component.onSubmit();
      expect(component.loading).toBeTrue();

      jasmine.clock().tick(700);

      expect(component.loading).toBeFalse();
      expect(routerSpy.navigate).toHaveBeenCalledWith(['/dashboard']);
    });

    it('should navigate to diagram upon Google login', () => {
      component.loginWithGoogle();
      expect(component.loading).toBeTrue();

      jasmine.clock().tick(600);

      expect(component.loading).toBeFalse();
      expect(routerSpy.navigate).toHaveBeenCalledWith(['/dashboard']);
    });
  });
});
