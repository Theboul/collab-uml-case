import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { provideZonelessChangeDetection } from '@angular/core';
import { of, throwError } from 'rxjs';
import { authGuard } from './auth.guard';
import { AuthService } from './auth.service';

describe('authGuard', () => {
  let authServiceSpy: jasmine.SpyObj<AuthService>;
  let routerSpy: jasmine.SpyObj<Router>;

  beforeEach(() => {
    authServiceSpy = jasmine.createSpyObj('AuthService', [
      'isAuthenticated',
      'refreshSession',
    ]);
    routerSpy = jasmine.createSpyObj('Router', ['navigate']);

    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        { provide: AuthService, useValue: authServiceSpy },
        { provide: Router, useValue: routerSpy },
      ],
    });
  });

  it('should allow access if already authenticated', () => {
    authServiceSpy.isAuthenticated.and.returnValue(true);

    const result = TestBed.runInInjectionContext(() => authGuard({} as any, {} as any));
    expect(result).toBeTrue();
    expect(routerSpy.navigate).not.toHaveBeenCalled();
  });

  it('should allow access if refreshSession succeeds', (done) => {
    authServiceSpy.isAuthenticated.and.returnValue(false);
    authServiceSpy.refreshSession.and.returnValue(
      of({
        accessToken: 'token',
        tokenType: 'Bearer',
        expiresIn: 900,
        user: { id: '1', email: 'a@b.com', fullName: 'User' },
      })
    );

    const result$ = TestBed.runInInjectionContext(() => authGuard({} as any, {} as any));
    (result$ as any).subscribe((allowed: boolean) => {
      expect(allowed).toBeTrue();
      expect(routerSpy.navigate).not.toHaveBeenCalled();
      done();
    });
  });

  it('should redirect to /login and block if unauthenticated and refresh fails', (done) => {
    authServiceSpy.isAuthenticated.and.returnValue(false);
    authServiceSpy.refreshSession.and.returnValue(
      throwError(() => new Error('No refresh token'))
    );

    const result$ = TestBed.runInInjectionContext(() => authGuard({} as any, {} as any));
    (result$ as any).subscribe((allowed: boolean) => {
      expect(allowed).toBeFalse();
      expect(routerSpy.navigate).toHaveBeenCalledWith(['/login']);
      done();
    });
  });
});
