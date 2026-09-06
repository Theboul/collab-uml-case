import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ScTableCardComponent } from './table-card.component';

describe('ScTableCardComponent', () => {
  let component: ScTableCardComponent;
  let fixture: ComponentFixture<ScTableCardComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ScTableCardComponent],
      providers: [provideZonelessChangeDetection()],
    }).compileComponents();

    fixture = TestBed.createComponent(ScTableCardComponent);
    component = fixture.componentInstance;
    component.tableName = 'users';
  });

  it('should create the table-card component', () => {
    expect(component).toBeTruthy();
  });

  it('should render tableName and columns', async () => {
    fixture.componentRef.setInput('tableName', 'orders');
    fixture.componentRef.setInput('columns', [
      { name: 'id', type: 'UUID', isPk: true },
      { name: 'user_id', type: 'UUID', isFk: true },
    ]);
    await fixture.whenStable();

    const titleEl: HTMLElement = fixture.nativeElement.querySelector('.font-code');
    expect(titleEl.textContent?.trim()).toBe('orders');
    expect(component.visibleColumns.length).toBe(2);
  });

  it('should limit columns in isCompact mode', async () => {
    fixture.componentRef.setInput('isCompact', true);
    fixture.componentRef.setInput('maxCompactColumns', 1);
    fixture.componentRef.setInput('columns', [
      { name: 'id', type: 'UUID', isPk: true },
      { name: 'total', type: 'NUMERIC' },
      { name: 'status', type: 'VARCHAR' },
    ]);
    await fixture.whenStable();

    expect(component.visibleColumns.length).toBe(1);
    expect(component.remainingColumnsCount).toBe(2);
  });
});
