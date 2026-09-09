import { Injectable, inject } from '@angular/core';
import {
  UmlAttribute,
  UmlClassDto,
  UmlOperation,
  UmlParameter,
} from '../domain/models/uml-editor.models';
import { EditorStateService } from './editor-state.service';
import { EditorSelectionService } from './editor-selection.service';
import { UmlGraphService } from '../infrastructure/x6/uml-graph.service';
import { EditorCommandService } from './editor-command.service';

@Injectable({
  providedIn: 'root',
})
export class EditorMemberCommandService {
  private readonly state = inject(EditorStateService);
  private readonly selection = inject(EditorSelectionService);
  private readonly graphService = inject(UmlGraphService);
  private readonly commandService = inject(EditorCommandService);

  addAttribute(classId: string, attr?: Partial<UmlAttribute>): void {
    const currentModel = this.state.model();
    const cls = currentModel.classes.find((c) => c.id === classId);
    if (!cls) return;

    const attributeId = crypto.randomUUID();
    const newAttr: UmlAttribute = {
      id: attributeId,
      name: attr?.name ?? `campo${cls.attributes.length + 1}`,
      type: attr?.type ?? 'String',
      visibility: attr?.visibility ?? '-',
      isStatic: attr?.isStatic ?? false,
    };

    this.commandService.executeCommandWithHistory(
      {
        type: 'ADD_ATTRIBUTE',
        payload: {
          classId,
          attributeId,
          name: newAttr.name,
          type: newAttr.type,
          visibility: newAttr.visibility,
          isStatic: newAttr.isStatic,
        },
      },
      { type: 'DELETE_ATTRIBUTE', payload: { classId, attributeId } },
      `Agregar atributo ${newAttr.name} a ${cls.name}`,
      () => this.mutateClass(classId, (c) => ({ ...c, attributes: [...c.attributes, newAttr] }), true)
    );
  }

  updateAttribute(classId: string, attributeId: string, updates: Partial<UmlAttribute>): void {
    const currentModel = this.state.model();
    const cls = currentModel.classes.find((c) => c.id === classId);
    if (!cls) return;
    const oldAttr = cls.attributes.find((a) => a.id === attributeId);
    if (!oldAttr) return;

    this.commandService.executeCommandWithHistory(
      { type: 'UPDATE_ATTRIBUTE', payload: { classId, attributeId, ...updates } },
      {
        type: 'UPDATE_ATTRIBUTE',
        payload: {
          classId,
          attributeId,
          name: oldAttr.name,
          type: oldAttr.type,
          visibility: oldAttr.visibility,
          isStatic: oldAttr.isStatic,
        },
      },
      `Actualizar atributo ${oldAttr.name}`,
      () =>
        this.mutateClass(
          classId,
          (c) => ({
            ...c,
            attributes: c.attributes.map((a) => (a.id === attributeId ? { ...a, ...updates } : a)),
          }),
          true
        )
    );
  }

  deleteAttribute(classId: string, attributeId: string): void {
    const currentModel = this.state.model();
    const cls = currentModel.classes.find((c) => c.id === classId);
    if (!cls) return;
    const oldAttr = cls.attributes.find((a) => a.id === attributeId);
    if (!oldAttr) return;

    this.commandService.executeCommandWithHistory(
      { type: 'DELETE_ATTRIBUTE', payload: { classId, attributeId } },
      {
        type: 'ADD_ATTRIBUTE',
        payload: {
          classId,
          attributeId,
          name: oldAttr.name,
          type: oldAttr.type,
          visibility: oldAttr.visibility,
          isStatic: oldAttr.isStatic,
        },
      },
      `Eliminar atributo ${oldAttr.name}`,
      () => {
        this.mutateClass(classId, (c) => ({
          ...c,
          attributes: c.attributes.filter((a) => a.id !== attributeId),
        }));
        const currentSub = this.selection.selectedSubElement();
        if (currentSub && currentSub.elementId === attributeId) {
          this.selection.clearSubElement();
        } else if (currentSub && currentSub.classId === classId) {
          this.selection.selectSubElement(currentSub);
        }
      }
    );
  }

  addOperation(classId: string, op?: Partial<UmlOperation>): void {
    const currentModel = this.state.model();
    const cls = currentModel.classes.find((c) => c.id === classId);
    if (!cls) return;

    const operationId = crypto.randomUUID();
    const newOp: UmlOperation = {
      id: operationId,
      name: op?.name ?? `metodo${cls.operations.length + 1}`,
      returnType: op?.returnType ?? 'void',
      visibility: op?.visibility ?? '+',
      parameters: [],
      isStatic: op?.isStatic ?? false,
      isAbstract: op?.isAbstract ?? false,
    };

    this.commandService.executeCommandWithHistory(
      {
        type: 'ADD_OPERATION',
        payload: {
          classId,
          operationId,
          name: newOp.name,
          returnType: newOp.returnType,
          visibility: newOp.visibility,
          isStatic: newOp.isStatic,
          isAbstract: newOp.isAbstract,
        },
      },
      { type: 'DELETE_OPERATION', payload: { classId, operationId } },
      `Agregar operación ${newOp.name} a ${cls.name}`,
      () => this.mutateClass(classId, (c) => ({ ...c, operations: [...c.operations, newOp] }), true)
    );
  }

  updateOperation(classId: string, operationId: string, updates: Partial<UmlOperation>): void {
    const currentModel = this.state.model();
    const cls = currentModel.classes.find((c) => c.id === classId);
    if (!cls) return;
    const oldOp = cls.operations.find((o) => o.id === operationId);
    if (!oldOp) return;

    this.commandService.executeCommandWithHistory(
      { type: 'UPDATE_OPERATION', payload: { classId, operationId, ...updates } },
      {
        type: 'UPDATE_OPERATION',
        payload: {
          classId,
          operationId,
          name: oldOp.name,
          returnType: oldOp.returnType,
          visibility: oldOp.visibility,
          isStatic: oldOp.isStatic,
          isAbstract: oldOp.isAbstract,
        },
      },
      `Actualizar operación ${oldOp.name}`,
      () =>
        this.mutateClass(
          classId,
          (c) => ({
            ...c,
            operations: c.operations.map((o) => (o.id === operationId ? { ...o, ...updates } : o)),
          }),
          true
        )
    );
  }

  deleteOperation(classId: string, operationId: string): void {
    const currentModel = this.state.model();
    const cls = currentModel.classes.find((c) => c.id === classId);
    if (!cls) return;
    const oldOp = cls.operations.find((o) => o.id === operationId);
    if (!oldOp) return;

    this.commandService.executeCommandWithHistory(
      { type: 'DELETE_OPERATION', payload: { classId, operationId } },
      {
        type: 'ADD_OPERATION',
        payload: {
          classId,
          operationId,
          name: oldOp.name,
          returnType: oldOp.returnType,
          visibility: oldOp.visibility,
          isStatic: oldOp.isStatic,
          isAbstract: oldOp.isAbstract,
        },
      },
      `Eliminar operación ${oldOp.name}`,
      () => {
        this.mutateClass(classId, (c) => ({
          ...c,
          operations: c.operations.filter((o) => o.id !== operationId),
        }));
        const currentSub = this.selection.selectedSubElement();
        if (currentSub && currentSub.elementId === operationId) {
          this.selection.clearSubElement();
        } else if (currentSub && currentSub.classId === classId) {
          this.selection.selectSubElement(currentSub);
        }
      }
    );
  }

  addParameter(classId: string, operationId: string, param?: Partial<UmlParameter>): void {
    const currentModel = this.state.model();
    const cls = currentModel.classes.find((c) => c.id === classId);
    if (!cls) return;
    const op = cls.operations.find((o) => o.id === operationId);
    if (!op) return;

    const parameterId = crypto.randomUUID();
    const currentParams = Array.isArray(op.parameters) ? op.parameters : [];
    const newParam: UmlParameter = {
      id: parameterId,
      name: param?.name ?? `p${currentParams.length + 1}`,
      type: param?.type ?? 'String',
      direction: param?.direction ?? 'in',
    };

    this.commandService.executeCommandWithHistory(
      {
        type: 'ADD_PARAMETER',
        payload: {
          classId,
          operationId,
          parameterId,
          name: newParam.name,
          type: newParam.type,
          direction: newParam.direction,
        },
      },
      { type: 'DELETE_PARAMETER', payload: { classId, operationId, parameterId } },
      `Agregar parámetro ${newParam.name}`,
      () =>
        this.mutateClass(classId, (c) => ({
          ...c,
          operations: c.operations.map((o) =>
            o.id === operationId ? { ...o, parameters: [...currentParams, newParam] } : o
          ),
        }))
    );
  }

  updateParameter(
    classId: string,
    operationId: string,
    parameterId: string,
    updates: Partial<UmlParameter>
  ): void {
    const currentModel = this.state.model();
    const cls = currentModel.classes.find((c) => c.id === classId);
    if (!cls) return;
    const op = cls.operations.find((o) => o.id === operationId);
    if (!op || !Array.isArray(op.parameters)) return;
    const oldParam = op.parameters.find((p) => p.id === parameterId);
    if (!oldParam) return;

    this.commandService.executeCommandWithHistory(
      { type: 'UPDATE_PARAMETER', payload: { classId, operationId, parameterId, ...updates } },
      {
        type: 'UPDATE_PARAMETER',
        payload: {
          classId,
          operationId,
          parameterId,
          name: oldParam.name,
          type: oldParam.type,
          direction: oldParam.direction,
        },
      },
      `Actualizar parámetro ${oldParam.name}`,
      () =>
        this.mutateClass(classId, (c) => ({
          ...c,
          operations: c.operations.map((o) =>
            o.id === operationId && Array.isArray(o.parameters)
              ? {
                  ...o,
                  parameters: o.parameters.map((p) =>
                    p.id === parameterId ? { ...p, ...updates } : p
                  ),
                }
              : o
          ),
        }))
    );
  }

  deleteParameter(classId: string, operationId: string, parameterId: string): void {
    const currentModel = this.state.model();
    const cls = currentModel.classes.find((c) => c.id === classId);
    if (!cls) return;
    const op = cls.operations.find((o) => o.id === operationId);
    if (!op || !Array.isArray(op.parameters)) return;
    const oldParam = op.parameters.find((p) => p.id === parameterId);
    if (!oldParam) return;

    this.commandService.executeCommandWithHistory(
      { type: 'DELETE_PARAMETER', payload: { classId, operationId, parameterId } },
      {
        type: 'ADD_PARAMETER',
        payload: {
          classId,
          operationId,
          parameterId,
          name: oldParam.name,
          type: oldParam.type,
          direction: oldParam.direction,
        },
      },
      `Eliminar parámetro ${oldParam.name}`,
      () =>
        this.mutateClass(classId, (c) => ({
          ...c,
          operations: c.operations.map((o) =>
            o.id === operationId && Array.isArray(o.parameters)
              ? { ...o, parameters: o.parameters.filter((p) => p.id !== parameterId) }
              : o
          ),
        }))
    );
  }

  private mutateClass(
    classId: string,
    mutator: (cls: UmlClassDto) => UmlClassDto,
    preserveSubSelection = false
  ): void {
    this.state.updateClasses((classes) =>
      classes.map((c) => (c.id === classId ? mutator(c) : c))
    );
    const updated = this.state.model().classes.find((c) => c.id === classId);
    if (updated) {
      this.graphService.updateNodeData(classId, updated);
      if (preserveSubSelection) {
        const currentSub = this.selection.selectedSubElement();
        if (currentSub && currentSub.classId === classId) {
          this.selection.selectSubElement(currentSub);
        }
      }
    }
  }
}
