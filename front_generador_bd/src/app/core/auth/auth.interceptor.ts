import { inject } from '@angular/core';
import {
  HttpErrorResponse,
  HttpEvent,
  HttpHandlerFn,
  HttpInterceptorFn,
  HttpRequest,
} from '@angular/common/http';
import { Observable, catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';

export const authInterceptor: HttpInterceptorFn = (
  req: HttpRequest<unknown>,
  next: HttpHandlerFn
): Observable<HttpEvent<unknown>> => {
  const authService = inject(AuthService);
  const token = authService.accessToken();

  let modifiedReq = req;

  // Si la petición es hacia nuestra API
  if (req.url.startsWith('/api/')) {
    const isAuthEndpoint =
      req.url.includes('/api/v2/auth/login') ||
      req.url.includes('/api/v2/auth/register') ||
      req.url.includes('/api/v2/auth/refresh');

    const headersConfig: Record<string, string> = {};

    if (token && !isAuthEndpoint) {
      headersConfig['Authorization'] = `Bearer ${token}`;
    }

    modifiedReq = req.clone({
      setHeaders: headersConfig,
      withCredentials: true,
    });
  }

  return next(modifiedReq).pipe(
    catchError((error: unknown) => {
      if (
        error instanceof HttpErrorResponse &&
        error.status === 401 &&
        !req.url.includes('/api/v2/auth/')
      ) {
        // Intentar refresco silencioso del Access Token con la cookie HttpOnly
        return authService.refreshSession().pipe(
          switchMap((authRes) => {
            const retryReq = req.clone({
              setHeaders: {
                Authorization: `Bearer ${authRes.accessToken}`,
              },
              withCredentials: true,
            });
            return next(retryReq);
          }),
          catchError((refreshErr) => throwError(() => refreshErr))
        );
      }
      return throwError(() => error);
    })
  );
};
