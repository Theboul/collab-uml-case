import { Routes } from '@angular/router';
import { Diagram } from './diagram/diagram';
import { LandinPage } from './landin-page/landin-page';
import { ScLoginComponent } from './features/auth/ui/login/login.component';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { authGuard } from './core/auth';

import { UmlEditorComponent } from './features/modeling/ui/uml-editor.component';

export const routes: Routes = [
  { path: 'login', component: ScLoginComponent },
  { path: 'dashboard', component: DashboardComponent, canActivate: [authGuard] },
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  { path: 'legacy-landing', component: LandinPage },
  {
    path: 'diagram/:roomId',
    component: UmlEditorComponent,
    canActivate: [authGuard],
  },
  {
    path: 'join/:accessCode',
    loadComponent: () =>
      import('./features/modeling/ui/join-workspace/join-workspace.component').then(
        (m) => m.JoinWorkspaceComponent
      ),
    canActivate: [authGuard],
  },
  {
    path: 'canvas/:roomId',
    redirectTo: 'diagram/:roomId',
    pathMatch: 'full',
  },

  {
    path: 'legacy-diagram/:roomId',
    component: Diagram,
    canActivate: [authGuard],
  },
  { path: '**', redirectTo: 'dashboard' },
];
