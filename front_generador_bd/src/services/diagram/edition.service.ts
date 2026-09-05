import { Injectable } from '@angular/core';
import { v4 as uuid } from 'uuid';
import { CollaborationService } from '../colaboration/collaboration.service';
import { DiagramExportService } from '../exports/diagram-export.service';
import { UmlValidationService } from '../colaboration/uml-validation.service';



@Injectable({ providedIn: 'root' })
export class EditionService {
  readonly MIN_W = 180;
  readonly NAME_H = 30;
  readonly MIN_ATTRS_H = 40;
  readonly MIN_METHS_H = 40;
  readonly PAD_V = 10;
  constructor(
    private exportService: DiagramExportService,
		private umlValidationService: UmlValidationService
  ){}
  // ========= Edición de campos =========
  startEditing(
    model: any,
    paper: any,
    field: 'name' | 'attributes' | 'methods',
    x: number,
    y: number,
    collab?: { broadcast: (msg: any) => void }
  ) {
    const MAP: Record<typeof field, string> = {
      name: '.uml-class-name-text',
      attributes: '.uml-class-attrs-text',
      methods: '.uml-class-methods-text'
    };
    const selector = MAP[field];
    const currentValue = model.attr(`${selector}/text`) || '';

    const paperRect = paper.el.getBoundingClientRect();
    const bbox = model.getBBox();
    const absX = paperRect.left + x;
    const absY = paperRect.top + y;

    const editor = field === 'name'
      ? document.createElement('input')
      : document.createElement('textarea');

    editor.value = currentValue;
    Object.assign(editor.style, {
      position: 'absolute',
      left: `${absX}px`,
      top: `${absY}px`,
      border: '1px solid #2196f3',
      padding: '2px',
      zIndex: '1000',
      fontSize: '14px',
      background: '#fff',
      minWidth: `${Math.max(120, bbox.width - 20)}px`,
      resize: field === 'name' ? 'none' : 'none'
    } as CSSStyleDeclaration);

    if (field !== 'name') (editor as HTMLTextAreaElement).rows = 4;

    document.body.appendChild(editor);
    editor.focus();

    let closed = false;
    const finish = (save: boolean) => {
      if (closed) return;
      closed = true;

      if (save) {
        const raw = (editor as HTMLInputElement | HTMLTextAreaElement).value;
        const newValue = field === 'name' ? raw.trim() : raw.replace(/\r?\n/g, '\n');
        model.attr(`${selector}/text`, newValue);
        model.set(field, newValue);
        collab?.broadcast({ t: 'edit_text', id: model.id, field, value: newValue });
        this.scheduleAutoResize(model, paper);
      }
      editor.parentNode && editor.parentNode.removeChild(editor);
    };

    editor.addEventListener('blur', () => finish(true));
      editor.addEventListener('keydown', (evt: Event) => {
        const e = evt as KeyboardEvent;
        if (field === 'name') {
          if (e.key === 'Enter') { e.preventDefault(); finish(true); }
          if (e.key === 'Escape') { e.preventDefault(); finish(false); }
        } else {
          if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); finish(true); }
          if (e.key === 'Escape') { e.preventDefault(); finish(false); }
        }
      });
  }
  
  // ========= Edición de etiquetas de enlaces =========
  startEditingLabel(
    model: any,
    paper: any,
    labelIndex: number,
    currentValue: string,
    x: number,
    y: number,
    collab?: { broadcast: (msg: any) => void },
    graph?: any
  ) {
    const paperRect = paper.el.getBoundingClientRect();
    const absX = paperRect.left + x;
    const absY = paperRect.top + y;

    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentValue;
    Object.assign(input.style, {
      position: 'absolute',
      left: `${absX}px`,
      top: `${absY}px`,
      border: '1px solid #2196f3',
      padding: '2px',
      zIndex: '1000',
      fontSize: '12px',
      background: '#fff',
      minWidth: '60px'
    } as CSSStyleDeclaration);

    document.body.appendChild(input);
    input.focus();

    const labelNode = (paper.findViewByModel(model) as any).findLabelNode(labelIndex) as SVGElement;
    if (labelNode) {
      labelNode.setAttribute('stroke', '#2196f3');
      labelNode.setAttribute('stroke-width', '1');
    }

    let closed = false;
    const cleanupHighlight = () => {
      if (labelNode) {
        labelNode.removeAttribute('stroke');
        labelNode.removeAttribute('stroke-width');
      }
    };
    const finish = (save: boolean) => {
      if (closed) return;
      closed = true;

      if (save) {
        const text = input.value.trim();
        model.label(labelIndex, { ...model.label(labelIndex), attrs: { text: { text } } });
        collab?.broadcast({ t: 'edit_label', linkId: model.id, index: labelIndex, text });
        model.set('label', text);
        const umlJson = this.exportService.export(graph);
        this.umlValidationService.validateModel(umlJson);
      }
      if (labelNode) { labelNode.removeAttribute('stroke'); labelNode.removeAttribute('stroke-width'); }
      input.parentNode && input.parentNode.removeChild(input);
      cleanupHighlight();
    };

    input.addEventListener('blur', () => finish(true));
    input.addEventListener('keydown', (e: KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === 'Escape' || e.key === ' ') {
        e.preventDefault();
        finish(e.key !== 'Escape'); // Enter/Espacio = guardar, Escape = cancelar
      }
    });
  }
  // ========= Actualiza la posición de los puertos o puntos de enlace =========
  updatePorts(model: any) {
    if (!model?.isElement?.()) return;
    const { width, height } = model.size();
    model.portProp('top',    'args', { x: width / 2, y: 0 });
    model.portProp('bottom', 'args', { x: width / 2, y: height });
    model.portProp('left',   'args', { x: 0,        y: height / 2 });
    model.portProp('right',  'args', { x: width,    y: height / 2 });
  }

  scheduleAutoResize(model: any, paper: any) {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => this.autoResizeUmlClass(model, paper));
    });
  }

  /**************************************************************************************************
  *                  FUNCIONES PRIVADAS
  ***************************************************************************************************/ 

  // ========= Auto-resize + puertos =========
  private getTextBBox(model: any, paper: any, selector: string): number {
    const view = paper.findViewByModel(model);
    const node = view?.findBySelector(selector)?.[0] as SVGGraphicsElement | undefined;
    try { return node ? node.getBBox().height : 0; } catch { return 0; }
  }

  // ========= Auto-ajusta el tamaño del diagrama UML de clase al contenido =========
  autoResizeUmlClass(model: any, paper: any) {
    if (!model?.isElement?.()) return;

    const width  = Math.max(this.MIN_W, (model.get('size')?.width) || this.MIN_W);
    const nameH  = this.NAME_H;

    const attrsHText = this.getTextBBox(model, paper, '.uml-class-attrs-text');
    const methsHText = this.getTextBBox(model, paper, '.uml-class-methods-text');

    const attrsH = Math.max(this.MIN_ATTRS_H, Math.round((attrsHText || 0) + this.PAD_V));
    const methsH = Math.max(this.MIN_METHS_H, Math.round((methsHText || 0) + this.PAD_V));
    const totalH = Math.round(nameH + attrsH + methsH);

    model.attr('.uml-class-name-rect/height', nameH);

    const x1 = 1, x2 = width - 1;
    const y1 = Math.round(nameH) + 0.5;
    const y2 = Math.round(nameH + attrsH) + 0.5;

    model.attr({
      '.sep-name':  { x1, y1, x2, y2: y1 },
      '.sep-attrs': { x1, y1: y2, x2, y2 }
    });

    model.attr('.uml-class-attrs-text/transform',  `translate(10, ${Math.round(nameH + 10)})`);
    model.attr('.uml-class-attrs-text/textWrap/width', width - 20);

    model.attr('.uml-class-methods-text/transform', `translate(10, ${Math.round(nameH + attrsH + 10)})`);
    model.attr('.uml-class-methods-text/textWrap/width', width - 20);

    model.resize(width, totalH);
    this.updatePorts(model);
  }
}
