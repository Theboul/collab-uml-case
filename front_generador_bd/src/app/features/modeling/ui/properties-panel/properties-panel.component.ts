import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { UmlEditorFacade } from '../../application/uml-editor.facade';
import { UmlAttribute, UmlClassDto, UmlOperation, UmlParameter } from '../../domain/models/uml-editor.models';
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

  commitClassName(cls: UmlClassDto, value: string): void {
    const trimmed = value.trim();
    if (!trimmed || trimmed === cls.name) return;
    this.facade.updateClassName(cls.id, trimmed);
  }

  commitClassAbstract(cls: UmlClassDto, checked: boolean): void {
    if (checked === cls.isAbstract) return;
    this.facade.updateClassAbstract(cls.id, checked);
  }

  addAttribute(cls: UmlClassDto): void {
    this.facade.addAttribute(cls.id);
  }

  commitAttrName(cls: UmlClassDto, attr: UmlAttribute, value: string): void {
    const trimmed = value.trim();
    if (!trimmed || trimmed === attr.name) return;
    this.facade.updateAttribute(cls.id, attr.id, { name: trimmed });
  }

  commitAttrType(cls: UmlClassDto, attr: UmlAttribute, value: string): void {
    const trimmed = value.trim();
    if (!trimmed || trimmed === attr.type) return;
    this.facade.updateAttribute(cls.id, attr.id, { type: trimmed });
  }

  commitAttrVisibility(cls: UmlClassDto, attr: UmlAttribute, value: string): void {
    if (!value || value === attr.visibility) return;
    this.facade.updateAttribute(cls.id, attr.id, { visibility: value as UmlAttribute['visibility'] });
  }

  removeAttribute(cls: UmlClassDto, attrId: string): void {
    this.facade.deleteAttribute(cls.id, attrId);
  }

  addOperation(cls: UmlClassDto): void {
    this.facade.addOperation(cls.id);
  }

  commitOpName(cls: UmlClassDto, op: UmlOperation, value: string): void {
    const trimmed = value.trim();
    if (!trimmed || trimmed === op.name) return;
    this.facade.updateOperation(cls.id, op.id, { name: trimmed });
  }

  commitOpReturnType(cls: UmlClassDto, op: UmlOperation, value: string): void {
    const trimmed = value.trim();
    if (!trimmed || trimmed === op.returnType) return;
    this.facade.updateOperation(cls.id, op.id, { returnType: trimmed });
  }

  commitOpVisibility(cls: UmlClassDto, op: UmlOperation, value: string): void {
    if (!value || value === op.visibility) return;
    this.facade.updateOperation(cls.id, op.id, { visibility: value as UmlOperation['visibility'] });
  }

  removeOperation(cls: UmlClassDto, opId: string): void {
    this.facade.deleteOperation(cls.id, opId);
  }

  addParameter(cls: UmlClassDto, op: UmlOperation): void {
    this.facade.addParameter(cls.id, op.id);
  }

  commitParamName(cls: UmlClassDto, op: UmlOperation, param: UmlParameter, value: string): void {
    const trimmed = value.trim();
    if (!trimmed || trimmed === param.name) return;
    this.facade.updateParameter(cls.id, op.id, param.id, { name: trimmed });
  }

  commitParamType(cls: UmlClassDto, op: UmlOperation, param: UmlParameter, value: string): void {
    const trimmed = value.trim();
    if (!trimmed || trimmed === param.type) return;
    this.facade.updateParameter(cls.id, op.id, param.id, { type: trimmed });
  }

  removeParameter(cls: UmlClassDto, op: UmlOperation, paramId: string): void {
    this.facade.deleteParameter(cls.id, op.id, paramId);
  }

  asArray(params: UmlParameter[] | string | undefined): UmlParameter[] {
    return Array.isArray(params) ? params : [];
  }
}
