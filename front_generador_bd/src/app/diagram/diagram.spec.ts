import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { provideRouter, ActivatedRoute } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { Diagram } from './diagram';
import { DiagramService } from '../../services/diagram/diagram.service';
import { FallbackService } from '../../services/diagram/fallback.service';
import { RelationshipService } from '../../services/diagram/relationship.service';
import { of } from 'rxjs';

describe('Diagram', () => {
  let component: Diagram;
  let fixture: ComponentFixture<Diagram>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Diagram],
      providers: [
        provideZonelessChangeDetection(),
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        DiagramService,
        FallbackService,
        RelationshipService,
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { paramMap: { get: () => 'test-room' } },
            params: of({ roomId: 'test-room' }),
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Diagram);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
