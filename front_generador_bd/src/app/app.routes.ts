import { Routes } from '@angular/router';
import { Diagram } from './diagram/diagram';
import { LandinPage } from './landin-page/landin-page';
import { ScLoginComponent } from './features/auth/ui/login/login.component';

export const routes: Routes = [ 
  { path: 'login', component: ScLoginComponent },
  { path: '', component: ScLoginComponent },
  { path: 'legacy-landing', component: LandinPage },
  { 
    path: 'diagram/:roomId', 
    component: Diagram,
  },
  { path: '**', redirectTo: '' }
];
