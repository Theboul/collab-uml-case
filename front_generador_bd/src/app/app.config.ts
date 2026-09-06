import { ApplicationConfig, provideBrowserGlobalErrorListeners, provideZonelessChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';

import { routes } from './app.routes';
import { provideClientHydration, withEventReplay } from '@angular/platform-browser';
import { DiagramService } from '../services/diagram/diagram.service';
import { FallbackService } from '../services/diagram/fallback.service';
import { RelationshipService } from '../services/diagram/relationship.service';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { authInterceptor } from './core/auth';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZonelessChangeDetection(),
    provideRouter(routes),
    provideClientHydration(withEventReplay()),
    // Servicios para el diagrama
    DiagramService,
    FallbackService,
    RelationshipService,
    provideHttpClient(withFetch(), withInterceptors([authInterceptor]))
  ]
};
