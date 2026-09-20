import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection, signal } from '@angular/core';
import { provideRouter, Router } from '@angular/router';
import { of } from 'rxjs';
import { ProjectShellComponent } from './project-shell.component';
import { AuthService, UserDto } from '../../core/auth';
import { PresencePeer } from '../../features/modeling/domain/models/collaboration.models';

describe('ProjectShellComponent (Chips de presencia en encabezado)', () => {
  let fixture: ComponentFixture<ProjectShellComponent>;
  let router: Router;
  let authServiceSpy: jasmine.SpyObj<AuthService>;

  beforeEach(async () => {
    authServiceSpy = jasmine.createSpyObj('AuthService', ['logout'], {
      currentUser: signal<UserDto | null>({
        id: 'usr-1',
        email: 'alex.rivera@ejemplo.com',
        fullName: 'Alex Rivera',
      }),
    });
    authServiceSpy.logout.and.returnValue(of(undefined));

    await TestBed.configureTestingModule({
      imports: [ProjectShellComponent],
      providers: [
        provideZonelessChangeDetection(),
        provideRouter([]),
        { provide: AuthService, useValue: authServiceSpy },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ProjectShellComponent);
    router = TestBed.inject(Router);
    spyOn(router, 'navigate');
    fixture.detectChanges();
  });

  it('no muestra chips de presencia cuando la lista de peers está vacía', () => {
    fixture.componentRef.setInput('peers', []);
    fixture.detectChanges();

    const presenceContainer = fixture.nativeElement.querySelector(
      '[aria-label="Colaboradores en la sala"]',
    );
    expect(presenceContainer).toBeNull();
  });

  it('renderiza chips con color y nombre de los colaboradores remotos junto al avatar', () => {
    const peers: PresencePeer[] = [
      { sessionId: 's-1', userId: 'u1', displayName: 'Carlos', color: '#ef4444' },
      { sessionId: 's-2', userId: null, displayName: null, color: '#3b82f6' },
    ];
    fixture.componentRef.setInput('peers', peers);
    fixture.detectChanges();

    const presenceContainer = fixture.nativeElement.querySelector(
      '[aria-label="Colaboradores en la sala"]',
    );
    expect(presenceContainer).not.toBeNull();

    const chips = presenceContainer.querySelectorAll('[data-testid="peer-chip"]');
    expect(chips.length).toBe(2);

    // Primer chip: Carlos con color #ef4444
    expect(chips[0].textContent).toContain('Carlos');
    const dot1 = chips[0].querySelector('span');
    expect(dot1?.style.backgroundColor).toBe('rgb(239, 68, 68)');

    // Segundo chip: fallback Colaborador con color #3b82f6
    expect(chips[1].textContent).toContain('Colaborador');
    const dot2 = chips[1].querySelector('span');
    expect(dot2?.style.backgroundColor).toBe('rgb(59, 130, 246)');
  });

  it('si hay más de 3 colaboradores, muestra 3 chips y una insignia +N con el conteo de desborde', () => {
    const peers: PresencePeer[] = [
      { sessionId: 's-1', userId: 'u1', displayName: 'Peer 1', color: '#ef4444' },
      { sessionId: 's-2', userId: 'u2', displayName: 'Peer 2', color: '#f97316' },
      { sessionId: 's-3', userId: 'u3', displayName: 'Peer 3', color: '#eab308' },
      { sessionId: 's-4', userId: 'u4', displayName: 'Peer 4', color: '#22c55e' },
      { sessionId: 's-5', userId: 'u5', displayName: 'Peer 5', color: '#06b6d4' },
    ];
    fixture.componentRef.setInput('peers', peers);
    fixture.detectChanges();

    const presenceContainer = fixture.nativeElement.querySelector(
      '[aria-label="Colaboradores en la sala"]',
    );
    const chips = presenceContainer.querySelectorAll('[data-testid="peer-chip"]');
    expect(chips.length).toBe(3);

    const overflowBadge = presenceContainer.querySelector('[data-testid="overflow-badge"]');
    expect(overflowBadge).not.toBeNull();
    expect(overflowBadge?.textContent?.trim()).toBe('+2');
  });
});
