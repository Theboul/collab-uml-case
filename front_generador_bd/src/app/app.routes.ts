import { Routes } from '@angular/router';
import { Diagram } from './diagram/diagram';
import { LandinPage } from './landin-page/landin-page';
import { ScLoginComponent } from './features/auth/ui/login/login.component';
import { DashboardComponent } from './features/dashboard/dashboard.component';

export const routes: Routes = [ 
  { path: 'login', component: ScLoginComponent },
  { path: 'dashboard', component: DashboardComponent },
  { path: '', component: DashboardComponent },
  { path: 'legacy-landing', component: LandinPage },
  { 
    path: 'diagram/:roomId', 
    component: Diagram,
  },
  { path: '**', redirectTo: '' }
];
