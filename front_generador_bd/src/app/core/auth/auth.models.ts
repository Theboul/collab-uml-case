/**
 * Modelos y contratos de intercambio para el módulo de autenticación de SchemaCraft.
 * Basado en docs/architecture/authentication-specification.md y ADR-0005.
 */

export interface UserDto {
  id: string;
  email: string;
  fullName: string;
  avatarUrl?: string | null;
}

export interface RegisterRequest {
  email: string;
  password: string;
  fullName: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface GoogleAuthRequest {
  credential: string;
}

export interface AuthResponse {
  accessToken: string;
  tokenType: string;
  expiresIn: number;
  user: UserDto;
}

export interface UserProfileResponse {
  id: string;
  email: string;
  fullName: string;
  avatarUrl?: string | null;
  identities: string[];
  isVerified: boolean;
}

export interface ApiErrorResponse {
  code: string;
  message: string;
  details?: unknown[];
}

export interface AuthConfigResponse {
  googleClientId: string;
}
