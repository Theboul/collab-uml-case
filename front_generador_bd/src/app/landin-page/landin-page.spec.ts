import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { LandinPage } from './landin-page';

describe('LandinPage', () => {
  let component: LandinPage;
  let fixture: ComponentFixture<LandinPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LandinPage],
      providers: [
        provideZonelessChangeDetection(),
        provideRouter([]),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(LandinPage);
    component = fixture.componentInstance;
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
