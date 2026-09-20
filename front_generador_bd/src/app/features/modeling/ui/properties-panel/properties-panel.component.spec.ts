import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection, signal, WritableSignal } from '@angular/core';
import { PropertiesPanelComponent } from './properties-panel.component';
import { UmlEditorFacade } from '../../application/uml-editor.facade';
import { UmlClassDto } from '../../domain/models/uml-editor.models';

describe('PropertiesPanelComponent (Bloqueo remoto editable <-> solo lectura)', () => {
  let fixture: ComponentFixture<PropertiesPanelComponent>;
  let component: PropertiesPanelComponent;

  let selectedClassSignal: WritableSignal<UmlClassDto | null>;
  let remoteLocksSignal: WritableSignal<Record<string, { sessionId: string; userId: string; displayName: string }>>;

  let updateClassNameSpy: jasmine.Spy;
  let addAttributeSpy: jasmine.Spy;
  let recordActivitySpy: jasmine.Spy;

  const mockClass: UmlClassDto = {
    id: 'class-1',
    name: 'Pedido',
    isAbstract: false,
    attributes: [
      { id: 'attr-1', name: 'id', type: 'UUID', visibility: '+', isStatic: false },
    ],
    operations: [],
  };

  beforeEach(async () => {
    selectedClassSignal = signal<UmlClassDto | null>(mockClass);
    remoteLocksSignal = signal({});

    updateClassNameSpy = jasmine.createSpy('updateClassName');
    addAttributeSpy = jasmine.createSpy('addAttribute');
    recordActivitySpy = jasmine.createSpy('recordActivity');

    const fakeFacade = {
      selectedClass: selectedClassSignal,
      selectedNodes: signal<string[]>(['class-1']),
      isElementLockedByOther: (id: string) => Boolean(remoteLocksSignal()[id]),
      getLockHolderName: (id: string) => remoteLocksSignal()[id]?.displayName ?? null,
      recordActivity: recordActivitySpy,
      updateClassName: updateClassNameSpy,
      addAttribute: addAttributeSpy,
      updateClassAbstract: jasmine.createSpy('updateClassAbstract'),
      updateAttribute: jasmine.createSpy('updateAttribute'),
      deleteAttribute: jasmine.createSpy('deleteAttribute'),
      addOperation: jasmine.createSpy('addOperation'),
      updateOperation: jasmine.createSpy('updateOperation'),
      deleteOperation: jasmine.createSpy('deleteOperation'),
      addParameter: jasmine.createSpy('addParameter'),
      updateParameter: jasmine.createSpy('updateParameter'),
      deleteParameter: jasmine.createSpy('deleteParameter'),
    };

    await TestBed.configureTestingModule({
      imports: [PropertiesPanelComponent],
      providers: [
        provideZonelessChangeDetection(),
        { provide: UmlEditorFacade, useValue: fakeFacade },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(PropertiesPanelComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('cuando no está bloqueado por otro peer, los controles están habilitados y aplican cambios', () => {
    expect(component.isLockedByOther()).toBeFalse();
    expect(component.lockHolderName()).toBeNull();

    const banner = fixture.nativeElement.querySelector('.bg-amber-50');
    expect(banner).toBeNull();

    const nameInput = fixture.nativeElement.querySelector('input[type="text"]');
    expect(nameInput?.disabled).toBeFalse();

    component.commitClassName(mockClass, 'Factura');
    expect(updateClassNameSpy).toHaveBeenCalledWith('class-1', 'Factura');
    expect(recordActivitySpy).toHaveBeenCalled();
  });

  it('transición a solo lectura: al bloquearse muestra aviso "En edición por..." y bloquea inputs y mutaciones', () => {
    remoteLocksSignal.set({
      'class-1': { sessionId: 'peer-2', userId: 'u2', displayName: 'Carlos' },
    });

    fixture.detectChanges();

    expect(component.isLockedByOther()).toBeTrue();
    expect(component.lockHolderName()).toBe('Carlos');

    const banner = fixture.nativeElement.querySelector('.bg-amber-50');
    expect(banner).not.toBeNull();
    expect(banner?.textContent).toContain('En edición por Carlos');

    const inputs: HTMLInputElement[] = Array.from(fixture.nativeElement.querySelectorAll('input'));
    for (const input of inputs) {
      expect(input.disabled).toBeTrue();
    }

    updateClassNameSpy.calls.reset();
    addAttributeSpy.calls.reset();

    component.commitClassName(mockClass, 'NuevoNombre');
    expect(updateClassNameSpy).not.toHaveBeenCalled();

    component.addAttribute(mockClass);
    expect(addAttributeSpy).not.toHaveBeenCalled();
  });

  it('transición de vuelta a editable: al liberarse el lock vuelve a habilitar controles', () => {
    remoteLocksSignal.set({
      'class-1': { sessionId: 'peer-2', userId: 'u2', displayName: 'Carlos' },
    });
    fixture.detectChanges();
    expect(component.isLockedByOther()).toBeTrue();

    remoteLocksSignal.set({});
    fixture.detectChanges();

    expect(component.isLockedByOther()).toBeFalse();
    const banner = fixture.nativeElement.querySelector('.bg-amber-50');
    expect(banner).toBeNull();

    component.commitClassName(mockClass, 'Factura');
    expect(updateClassNameSpy).toHaveBeenCalledWith('class-1', 'Factura');
  });
});
