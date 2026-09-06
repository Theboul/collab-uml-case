import { inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = (_route, state) => {
  const platformId = inject(PLATFORM_ID);
  if (!isPlatformBrowser(platformId)) {
    return true;
  }

  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated()) {
    return true;
  }

  // Intentar recuperación mediante cookie de refresco antes de bloquear
  return authService.refreshSession().pipe(
    map(() => true),
    catchError(() => {
      router.navigate(['/login'], {
        queryParams: state.url && state.url !== '/' ? { returnUrl: state.url } : {},
      });
      return of(false);
    })
  );
};
