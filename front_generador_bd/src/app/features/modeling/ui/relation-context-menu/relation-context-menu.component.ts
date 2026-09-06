import { Component, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { UmlEditorFacade } from '../../application/uml-editor.facade';
import { UmlMultiplicity, UmlRelationType } from '../../domain/models/uml-editor.models';
import { ScIconComponent } from '../../../../shared/ui/icon/icon.component';
import { ScButtonComponent } from '../../../../shared/ui/button/button.component';

@Component({
  selector: 'app-relation-context-menu',
  standalone: true,
  imports: [CommonModule, ScIconComponent, ScButtonComponent],
  templateUrl: './relation-context-menu.component.html',
  styleUrl: './relation-context-menu.component.css',
})
export class RelationContextMenuComponent {
  readonly facade = inject(UmlEditorFacade);

  readonly relationTypes: Array<{ type: UmlRelationType; label: string; symbol: string }> = [
    { type: 'ASSOCIATION', label: 'Asociación', symbol: '1 — 1' },
    { type: 'AGGREGATION', label: 'Agregación', symbol: '◇' },
    { type: 'COMPOSITION', label: 'Composición', symbol: '◆' },
    { type: 'GENERALIZATION', label: 'Herencia', symbol: '△' },
    { type: 'DEPENDENCY', label: 'Dependencia', symbol: '- - ▷' },
  ];

  readonly multiplicities: UmlMultiplicity[] = ['1', '0..1', '*', '0..*', '1..*'];

  readonly currentRelation = computed(() => {
    const menu = this.facade.contextMenu();
    if (!menu) return null;
    return this.facade.model().relations.find((r) => r.id === menu.edgeId) ?? null;
  });

  changeType(edgeId: string, type: UmlRelationType): void {
    this.facade.updateRelation(edgeId, { type });
    this.facade.closeContextMenu();
  }

  changeSourceMultiplicity(edgeId: string, m: UmlMultiplicity): void {
    this.facade.updateMultiplicity(edgeId, m, undefined);
  }

  changeTargetMultiplicity(edgeId: string, m: UmlMultiplicity): void {
    this.facade.updateMultiplicity(edgeId, undefined, m);
  }

  deleteRelation(edgeId: string): void {
    this.facade.deleteRelation(edgeId);
    this.facade.closeContextMenu();
  }
}
