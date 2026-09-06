import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { AuthService } from './auth.service';
import { AuthResponse } from './auth.models';

describe('AuthService', () => {
  let service: AuthService;
  let httpMock: HttpTestingController;

  const mockAuthResponse: AuthResponse = {
    accessToken: 'test-jwt-access-token',
    tokenType: 'Bearer',
    expiresIn: 900,
    user: {
      id: 'usr-123',
      email: 'alex@schemacraft.dev',
      fullName: 'Alex Schema',
      avatarUrl: null,
    },
  };

  beforeEach(() => {
    localStorage.clear();

    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(),
        provideHttpClientTesting(),
        AuthService,
      ],
    });

    service = TestBed.inject(AuthService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    localStorage.clear();
  });

  it('should be created with empty session by default', () => {
    expect(service).toBeTruthy();
    expect(service.isAuthenticated()).toBeFalse();
    expect(service.currentUser()).toBeNull();
    expect(service.accessToken()).toBeNull();
  });

  it('should register and establish session', () => {
    service
      .register({
        email: 'alex@schemacraft.dev',
        password: 'Password123!',
        fullName: 'Alex Schema',
      })
      .subscribe((res) => {
        expect(res.accessToken).toBe('test-jwt-access-token');
        expect(service.currentUser()?.email).toBe('alex@schemacraft.dev');
        expect(service.isAuthenticated()).toBeTrue();
      });

    const req = httpMock.expectOne('/api/v2/auth/register');
    expect(req.request.method).toBe('POST');
    expect(req.request.withCredentials).toBeTrue();
    req.flush(mockAuthResponse);
  });

  it('should login and establish session', () => {
    service
      .login({
        email: 'alex@schemacraft.dev',
        password: 'Password123!',
      })
      .subscribe((res) => {
        expect(res.accessToken).toBe('test-jwt-access-token');
        expect(service.accessToken()).toBe('test-jwt-access-token');
        expect(service.isAuthenticated()).toBeTrue();
      });

    const req = httpMock.expectOne('/api/v2/auth/login');
    expect(req.request.method).toBe('POST');
    expect(req.request.withCredentials).toBeTrue();
    req.flush(mockAuthResponse);
  });

  it('should authenticate with google credential', () => {
    service.loginWithGoogle('mock-google-id-token').subscribe((res) => {
      expect(res.user.fullName).toBe('Alex Schema');
      expect(service.isAuthenticated()).toBeTrue();
    });

    const req = httpMock.expectOne('/api/v2/auth/google');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ credential: 'mock-google-id-token' });
    req.flush(mockAuthResponse);
  });

  it('should refresh session and update access token', () => {
    service.refreshSession().subscribe((res) => {
      expect(res.accessToken).toBe('test-jwt-access-token');
      expect(service.accessToken()).toBe('test-jwt-access-token');
    });

    const req = httpMock.expectOne('/api/v2/auth/refresh');
    expect(req.request.method).toBe('POST');
    expect(req.request.withCredentials).toBeTrue();
    req.flush(mockAuthResponse);
  });

  it('should logout and clear local session state', () => {
    // Manually prime session
    (service as any).setSession(mockAuthResponse);
    expect(service.isAuthenticated()).toBeTrue();

    service.logout().subscribe(() => {
      expect(service.isAuthenticated()).toBeFalse();
      expect(service.currentUser()).toBeNull();
      expect(service.accessToken()).toBeNull();
    });

    const req = httpMock.expectOne('/api/v2/auth/logout');
    expect(req.request.method).toBe('POST');
    req.flush(null, { status: 204, statusText: 'No Content' });
  });

  it('should fetch and cache public auth config', () => {
    service.getAuthConfig().subscribe((config) => {
      expect(config.googleClientId).toBe('client-id-123.apps.googleusercontent.com');
    });

    const req = httpMock.expectOne('/api/v2/auth/config');
    expect(req.request.method).toBe('GET');
    req.flush({ googleClientId: 'client-id-123.apps.googleusercontent.com' });

    // Second call should return cached observable without repeating HTTP request
    service.getAuthConfig().subscribe((config) => {
      expect(config.googleClientId).toBe('client-id-123.apps.googleusercontent.com');
    });
    httpMock.expectNone('/api/v2/auth/config');
  });
});
