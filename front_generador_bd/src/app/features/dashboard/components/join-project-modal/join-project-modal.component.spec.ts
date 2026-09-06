import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ScJoinProjectModalComponent } from './join-project-modal.component';

describe('ScJoinProjectModalComponent', () => {
  let component: ScJoinProjectModalComponent;
  let fixture: ComponentFixture<ScJoinProjectModalComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ScJoinProjectModalComponent],
      providers: [provideZonelessChangeDetection()],
    }).compileComponents();

    fixture = TestBed.createComponent(ScJoinProjectModalComponent);
    component = fixture.componentInstance;
  });

  it('should create the join project modal', () => {
    expect(component).toBeTruthy();
  });

  it('should validate empty room code on submit', () => {
    component.roomCode = '   ';
    component.submit();

    expect(component.errorMessage).toBe('Por favor ingresa un código de sala válido.');
  });

  it('should emit onJoin with trimmed roomCode when valid', () => {
    spyOn(component.onJoin, 'emit');
    component.roomCode = '  ecommerce-multivendor-8f3k  ';
    component.submit();

    expect(component.errorMessage).toBeNull();
    expect(component.onJoin.emit).toHaveBeenCalledWith('ecommerce-multivendor-8f3k');
  });

  it('should reset fields and emit onClose on close()', () => {
    spyOn(component.onClose, 'emit');
    component.roomCode = 'something';
    component.errorMessage = 'error';

    component.close();
    expect(component.roomCode).toBe('');
    expect(component.errorMessage).toBeNull();
    expect(component.onClose.emit).toHaveBeenCalled();
  });
});
