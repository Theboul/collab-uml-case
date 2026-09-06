import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap, catchError, throwError, of, shareReplay } from 'rxjs';
import {
  AuthResponse,
  LoginRequest,
  RegisterRequest,
  GoogleAuthRequest,
  UserDto,
  UserProfileResponse,
  AuthConfigResponse,
} from './auth.models';

const TOKEN_KEY = 'sc_access_token';
const USER_KEY = 'sc_user_profile';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly baseUrl = '/api/v2/auth';

  readonly currentUser = signal<UserDto | null>(this.getInitialUser());
  readonly accessToken = signal<string | null>(this.getInitialToken());

  constructor(private http: HttpClient) {}

  private getInitialToken(): string | null {
    if (typeof window !== 'undefined' && window.localStorage) {
      return localStorage.getItem(TOKEN_KEY);
    }
    return null;
  }

  private getInitialUser(): UserDto | null {
    if (typeof window !== 'undefined' && window.localStorage) {
      const raw = localStorage.getItem(USER_KEY);
      if (raw) {
        try {
          return JSON.parse(raw) as UserDto;
        } catch {
          return null;
        }
      }
    }
    return null;
  }

  private setSession(auth: AuthResponse): void {
    this.accessToken.set(auth.accessToken);
    this.currentUser.set(auth.user);
    if (typeof window !== 'undefined' && window.localStorage) {
      localStorage.setItem(TOKEN_KEY, auth.accessToken);
      localStorage.setItem(USER_KEY, JSON.stringify(auth.user));
    }
  }

  private clearSession(): void {
    this.accessToken.set(null);
    this.currentUser.set(null);
    if (typeof window !== 'undefined' && window.localStorage) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    }
  }

  isAuthenticated(): boolean {
    return !!this.accessToken() && !!this.currentUser();
  }

  register(req: RegisterRequest): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${this.baseUrl}/register`, req, { withCredentials: true })
      .pipe(
        tap((res) => this.setSession(res))
      );
  }

  login(req: LoginRequest): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${this.baseUrl}/login`, req, { withCredentials: true })
      .pipe(
        tap((res) => this.setSession(res))
      );
  }

  loginWithGoogle(credential: string): Observable<AuthResponse> {
    const payload: GoogleAuthRequest = { credential };
    return this.http
      .post<AuthResponse>(`${this.baseUrl}/google`, payload, { withCredentials: true })
      .pipe(
        tap((res) => this.setSession(res))
      );
  }

  refreshSession(): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${this.baseUrl}/refresh`, {}, { withCredentials: true })
      .pipe(
        tap((res) => this.setSession(res)),
        catchError((err) => {
          this.clearSession();
          return throwError(() => err);
        })
      );
  }

  logout(): Observable<void> {
    return this.http
      .post<void>(`${this.baseUrl}/logout`, {}, { withCredentials: true })
      .pipe(
        tap(() => this.clearSession()),
        catchError(() => {
          this.clearSession();
          return of(undefined);
        })
      );
  }

  getProfile(): Observable<UserProfileResponse> {
    return this.http.get<UserProfileResponse>(`${this.baseUrl}/me`);
  }

  private configCache$: Observable<AuthConfigResponse> | null = null;

  getAuthConfig(): Observable<AuthConfigResponse> {
    if (!this.configCache$) {
      this.configCache$ = this.http
        .get<AuthConfigResponse>(`${this.baseUrl}/config`)
        .pipe(shareReplay(1));
    }
    return this.configCache$;
  }
}
