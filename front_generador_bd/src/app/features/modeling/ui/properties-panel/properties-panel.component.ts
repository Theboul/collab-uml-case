import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { UmlEditorFacade } from '../../application/uml-editor.facade';
import { UmlAttribute, UmlOperation } from '../../domain/models/uml-editor.models';
import { ScButtonComponent } from '../../../../shared/ui/button/button.component';
import { ScIconComponent } from '../../../../shared/ui/icon/icon.component';

@Component({
  selector: 'app-properties-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, ScButtonComponent, ScIconComponent],
  templateUrl: './properties-panel.component.html',
  styleUrl: './properties-panel.component.css',
})
export class PropertiesPanelComponent {
  readonly facade = inject(UmlEditorFacade);

  closePanel(): void {
    this.facade.selectedNodes.set([]);
  }

  onNameChange(classId: string, newName: string): void {
    if (!newName.trim()) return;
    this.facade.updateClassDetails(classId, { name: newName });
  }

  onAbstractToggle(classId: string, event: Event): void {
    const cb = event.target as HTMLInputElement;
    this.facade.updateClassDetails(classId, { isAbstract: cb.checked });
  }

  addAttribute(cls: any): void {
    const newAttr: UmlAttribute = {
      id: crypto.randomUUID(),
      name: `attr${cls.attributes.length + 1}`,
      type: 'String',
      visibility: '-',
    };
    this.facade.updateClassDetails(cls.id, {
      attributes: [...cls.attributes, newAttr],
    });
  }

  updateAttr(cls: any, attrId: string, updates: Partial<UmlAttribute>): void {
    const updated = cls.attributes.map((a: UmlAttribute) =>
      a.id === attrId ? { ...a, ...updates } : a
    );
    this.facade.updateClassDetails(cls.id, { attributes: updated });
  }

  removeAttribute(cls: any, attrId: string): void {
    const updated = cls.attributes.filter((a: UmlAttribute) => a.id !== attrId);
    this.facade.updateClassDetails(cls.id, { attributes: updated });
  }

  addOperation(cls: any): void {
    const newOp: UmlOperation = {
      id: crypto.randomUUID(),
      name: `metodo${cls.operations.length + 1}`,
      returnType: 'void',
      visibility: '+',
    };
    this.facade.updateClassDetails(cls.id, {
      operations: [...cls.operations, newOp],
    });
  }

  updateOp(cls: any, opId: string, updates: Partial<UmlOperation>): void {
    const updated = cls.operations.map((o: UmlOperation) =>
      o.id === opId ? { ...o, ...updates } : o
    );
    this.facade.updateClassDetails(cls.id, { operations: updated });
  }

  removeOperation(cls: any, opId: string): void {
    const updated = cls.operations.filter((o: UmlOperation) => o.id !== opId);
    this.facade.updateClassDetails(cls.id, { operations: updated });
  }
}
