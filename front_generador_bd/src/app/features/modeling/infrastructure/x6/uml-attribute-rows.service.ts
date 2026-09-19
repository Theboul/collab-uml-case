import { Injectable, NgZone, inject } from '@angular/core';
import { Subject } from 'rxjs';
import { CellView, Graph, Node } from '@antv/x6';
import {
  UML_NODE_DIMENSIONS as D,
  UmlNodeSubElementEvent,
} from '../../domain/models/uml-editor.models';
import { UmlAttributeRowLayout, UmlClassLayout, UmlRowLayout } from './uml-class-node-layout';
import type { NodeDblClickEvent } from './uml-graph.service';

export interface UmlAttributeRowInput {
  id?: string;
  name: string;
  type: string;
  visibility: string;
}

const SVG_NS = 'http://www.w3.org/2000/svg';
const ICON_SIZE = 13;
const ATTRIBUTE_ROWS_SELECTOR = 'attributeRows';
const OPERATION_ROWS_SELECTOR = 'operationRows';
const MONO_FONT = 'JetBrains Mono, monospace';
const TEXT_FILL = '#334155';

/**
 * Dueño de las filas reales de los compartimentos de atributos y de operaciones:
 * construye y muta a mano el subárbol DOM de los selectores `attributeRows` y
 * `operationRows` del shape registrado en `uml-class-node.registration.ts` — a
 * propósito por fuera del sistema declarativo de `attrs` de X6, porque las filas
 * tienen alto variable (los textos largos se envuelven en varias líneas) y los
 * atributos necesitan listeners por fila. La posición, el alto y las líneas de cada
 * fila vienen ya calculados de `UmlClassLayout`; este servicio solo las dibuja.
 * Decisión de usar SVG puro (no `foreignObject`) documentada en
 * `docs/analysis/decision-render-atributos-svg-vs-foreignobject.md`.
 *
 * No hay scroll interno ni recorte: el nodo crece hasta mostrar todas las filas.
 *
 * No inyecta `UmlGraphService` (que sí inyecta este servicio para llamar a
 * `render()`) para no crear una dependencia circular — expone sus propios Subjects
 * y quien los consuma (`UmlEditorFacade`, `UmlCanvasComponent`) se conecta
 * directamente a ellos.
 */
@Injectable({
  providedIn: 'root',
})
export class UmlAttributeRowsService {
  private readonly ngZone = inject(NgZone);

  /** Mismo evento que `UmlGraphService.nodeSubElementClick$` para type:'attribute' — el consumidor los mergea. */
  readonly rowClick$ = new Subject<UmlNodeSubElementEvent>();
  /** Mismo evento que `UmlGraphService.nodeDblClick$` para targetType:'attribute'. */
  readonly rowDblClick$ = new Subject<NodeDblClickEvent>();
  readonly deleteRequested$ = new Subject<{ classId: string; attributeId: string }>();

  /** Contenedores con el listener de mousedown ya wireado (una sola vez por nodo). */
  private readonly wiredContainers = new WeakSet<Element>();

  /** Reconstruye las filas de atributos y de operaciones de `node` según `layout`. */
  render(
    graph: Graph,
    node: Node,
    attributes: UmlAttributeRowInput[],
    layout: UmlClassLayout,
  ): void {
    const view = graph.findViewByCell(node);
    if (!view || !graph.renderer.isViewMounted(view)) {
      this.renderOnceMounted(graph, node, attributes, layout);
      return;
    }

    const attrContainer = this.findRowsContainer(graph, node, ATTRIBUTE_ROWS_SELECTOR);
    const opContainer = this.findRowsContainer(graph, node, OPERATION_ROWS_SELECTOR);
    if (!attrContainer || !opContainer) return;

    this.paintAttributeRows(node, attrContainer, attributes, layout);
    this.paintOperationRows(opContainer, layout);
    this.wireContainer(attrContainer);
  }

  /**
   * X6 crea la `CellView` de un nodo de forma síncrona (`Scheduler.renderViews()`,
   * llamado por el listener de `cell:added`), pero el montaje real — el `render()`
   * de `NodeView` que arma `view.selectors` vía `renderMarkup()` — se ejecuta desde
   * un job de cola que `Graph.options.async` (default `true`, sin pisar acá) vacía
   * con `requestIdleCallback`/`setTimeout` (`renderer/queueJob.js`), nunca en el
   * mismo tick que `graph.addNode()`. Si este método corría antes de ese montaje,
   * `findRowsContainer` no encontraba nada, `render()` cortaba en el guard de
   * `!container` sin reintento, y las filas quedaban vacías para siempre — bug real
   * confirmado leyendo `scheduler.js`/`node.js` de @antv/x6 (ninguna vía análoga
   * afecta a `setNodePositionSilent`: el propio scheduler de X6 ya prioriza y
   * reordena esos jobs, así que esa operación no necesita este mismo guard).
   * `graph.renderer.isViewMounted(view)` (API real, `renderer.d.ts`) detecta la
   * ventana; si la vista no está montada, esperamos el evento real del scheduler
   * `'view:mounted'` (`scheduler.d.ts` — no existe `'node:mounted'`).
   *
   * `'view:mounted'` se dispara dentro de `Scheduler.insertView()`, que corre
   * ANTES de `view.confirmUpdate()` en el mismo `updateView()` síncrono — o sea,
   * marca que el contenedor ya se insertó en el DOM, no que `renderMarkup()` ya
   * armó `selectors` (eso pasa unas líneas después, todavía sin retornar de
   * `updateView()`). Confirmado empíricamente: reintentar `render()` en el propio
   * handler del evento seguía encontrando `containerFound=false`. Por eso el
   * reintento se difiere a un microtask (`queueMicrotask`): un microtask nunca
   * corre hasta que el stack síncrono actual se vacía por completo, así que para
   * cuando se ejecuta, `updateView()` (y su `confirmUpdate()`/`render()`) ya
   * terminaron sí o sí.
   */
  private renderOnceMounted(
    graph: Graph,
    node: Node,
    attributes: UmlAttributeRowInput[],
    layout: UmlClassLayout,
  ): void {
    const onMounted = ({ view }: { view: CellView }): void => {
      if (view.cell.id !== node.id) return;
      graph.off('view:mounted', onMounted);
      queueMicrotask(() => this.render(graph, node, attributes, layout));
    };
    graph.on('view:mounted', onMounted);
  }

  /**
   * `graph.findViewByCell(node)` expone `selectors` (protected en el tipo, real en
   * runtime) — el mapa selector→Elemento que arma X6 en `parseJSONMarkup` al crear
   * la vista. Confirmado leyendo `@antv/x6/lib/view/markup.js`: ese mapa vive solo
   * en memoria, X6 NUNCA estampa un atributo `data-selector` en el DOM para markup
   * genérico (eso es específico de puertos/magnets, ver `cell.js`). Usar
   * `container.querySelector('[data-selector="..."]')` no matchea nunca.
   */
  private findRowsContainer(graph: Graph, node: Node, selector: string): SVGGElement | null {
    const view = graph.findViewByCell(node) as unknown as {
      selectors?: Record<string, Element | Element[]>;
    } | null;
    const el = view?.selectors?.[selector];
    if (!el || Array.isArray(el)) return null;
    return el as SVGGElement;
  }

  private paintAttributeRows(
    node: Node,
    container: SVGGElement,
    attributes: UmlAttributeRowInput[],
    layout: UmlClassLayout,
  ): void {
    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }
    layout.attrRows.forEach((row, i) => {
      const attr = attributes[i];
      if (attr) container.appendChild(this.buildAttributeRow(node, attr, row, layout));
    });
  }

  private paintOperationRows(container: SVGGElement, layout: UmlClassLayout): void {
    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }
    for (const row of layout.opRows) {
      container.appendChild(this.buildOperationRow(row));
    }
  }

  /** Un `<text>` con un `<tspan>` por línea; cada línea con su `y` absoluto (centro vertical) dentro de la fila. */
  private appendLines(
    text: SVGTextElement,
    row: UmlRowLayout,
    startX: number,
    textAnchor: 'start' | 'end' = 'start',
  ): void {
    row.lines.forEach((line, i) => {
      const tspan = document.createElementNS(SVG_NS, 'tspan');
      tspan.setAttribute(
        'x',
        String(startX + (textAnchor === 'start' && i > 0 ? D.WRAP_INDENT : 0)),
      );
      tspan.setAttribute(
        'y',
        String(row.y + D.ROW_V_PADDING / 2 + i * D.WRAP_LINE_HEIGHT + D.WRAP_LINE_HEIGHT / 2),
      );
      tspan.textContent = line;
      text.appendChild(tspan);
    });
  }

  private buildOperationRow(row: UmlRowLayout): SVGTextElement {
    const text = document.createElementNS(SVG_NS, 'text');
    text.setAttribute('class', 'uml-operations-text');
    text.setAttribute('text-anchor', 'start');
    text.setAttribute('dominant-baseline', 'central');
    text.setAttribute('font-family', MONO_FONT);
    text.setAttribute('font-size', String(D.OP_FONT_SIZE));
    text.setAttribute('fill', TEXT_FILL);
    this.appendLines(text, row, D.OP_PADDING_X);
    return text;
  }

  private buildAttributeRow(
    node: Node,
    attr: UmlAttributeRowInput,
    layout: UmlAttributeRowLayout,
    classLayout: UmlClassLayout,
  ): SVGGElement {
    const nodeWidth = classLayout.width;
    const rowY = layout.y;
    const firstLineCenterY = rowY + D.ROW_V_PADDING / 2 + D.WRAP_LINE_HEIGHT / 2;
    const iconCenterY = rowY + layout.height / 2;

    const row = document.createElementNS(SVG_NS, 'g');
    row.setAttribute('class', 'uml-attr-row');
    if (attr.id) row.setAttribute('data-attr-id', attr.id);

    const bg = document.createElementNS(SVG_NS, 'rect');
    bg.setAttribute('class', 'uml-attr-row-bg');
    bg.setAttribute('x', '0');
    bg.setAttribute('y', String(rowY));
    bg.setAttribute('width', String(nodeWidth));
    bg.setAttribute('height', String(layout.height));
    bg.setAttribute('fill', 'transparent');
    row.appendChild(bg);

    // fill/font se fijan acá como atributos SVG explícitos, no solo por CSS
    // (::ng-deep en uml-canvas.component.css) — para que el texto sea visible
    // independientemente de cualquier timing/cascada de estilos. La CSS sigue
    // siendo la dueña de los estados dinámicos (hover, opacity del ícono).
    const icon = document.createElementNS(SVG_NS, 'text');
    icon.setAttribute('class', 'uml-attr-delete');
    icon.setAttribute('x', String(nodeWidth - D.ATTR_PADDING_X));
    icon.setAttribute('y', String(iconCenterY));
    icon.setAttribute('text-anchor', 'end');
    icon.setAttribute('dominant-baseline', 'central');
    icon.setAttribute('font-family', 'Material Symbols Outlined');
    icon.setAttribute('font-size', String(ICON_SIZE));
    icon.setAttribute('fill', '#f43f5e');
    icon.textContent = 'delete';
    row.appendChild(icon);

    const nameText = document.createElementNS(SVG_NS, 'text');
    nameText.setAttribute('class', 'uml-attr-name');
    nameText.setAttribute('text-anchor', 'start');
    nameText.setAttribute('dominant-baseline', 'central');
    nameText.setAttribute('font-family', MONO_FONT);
    nameText.setAttribute('font-size', String(D.ATTR_FONT_SIZE));
    nameText.setAttribute('fill', TEXT_FILL);

    if (layout.twoColumns) {
      // Una sola línea: nombre a la izquierda, tipo alineado a la derecha (antes del ícono).
      nameText.setAttribute('x', String(D.ATTR_PADDING_X));
      nameText.setAttribute('y', String(firstLineCenterY));
      nameText.textContent = layout.name;

      const typeText = document.createElementNS(SVG_NS, 'text');
      typeText.setAttribute('class', 'uml-attr-type');
      typeText.setAttribute('x', String(nodeWidth - D.ATTR_ICON_RESERVE));
      typeText.setAttribute('y', String(firstLineCenterY));
      typeText.setAttribute('text-anchor', 'end');
      typeText.setAttribute('dominant-baseline', 'central');
      typeText.setAttribute('font-family', MONO_FONT);
      typeText.setAttribute('font-size', String(D.ATTR_FONT_SIZE));
      typeText.setAttribute('fill', TEXT_FILL);
      typeText.textContent = layout.type;
      row.appendChild(typeText);
    } else {
      // No entra en una línea: texto único envuelto en varias líneas.
      this.appendLines(nameText, layout, D.ATTR_PADDING_X);
    }
    row.appendChild(nameText);

    this.wireRowEvents(row, icon, node, attr, classLayout, rowY);
    return row;
  }

  private wireRowEvents(
    row: SVGGElement,
    icon: SVGTextElement,
    node: Node,
    attr: UmlAttributeRowInput,
    classLayout: UmlClassLayout,
    rowRelY: number,
  ): void {
    const itemRelY = classLayout.headerHeight + D.SEP_PADDING + rowRelY;

    row.addEventListener('click', (e: MouseEvent) => {
      e.stopPropagation();
      if (!attr.id) return;
      if (e.target === icon) {
        this.ngZone.run(() =>
          this.deleteRequested$.next({ classId: node.id, attributeId: attr.id! }),
        );
        return;
      }
      this.ngZone.run(() => this.rowClick$.next(this.toSubElementEvent(node, attr, itemRelY, e)));
    });

    row.addEventListener('dblclick', (e: MouseEvent) => {
      e.stopPropagation();
      if (e.target === icon || !attr.id) return;
      this.ngZone.run(() => this.rowDblClick$.next(this.toDblClickEvent(node, attr, itemRelY)));
    });
  }

  /** Wireado una sola vez por nodo: bloquea el drag del nodo desde el compartimento de atributos. */
  private wireContainer(container: SVGGElement): void {
    if (this.wiredContainers.has(container)) return;
    this.wiredContainers.add(container);
    container.addEventListener('mousedown', (e: MouseEvent) => e.stopPropagation());
  }

  private toSubElementEvent(
    node: Node,
    attr: UmlAttributeRowInput,
    itemRelY: number,
    e: MouseEvent,
  ): UmlNodeSubElementEvent {
    const pos = node.getPosition();
    const size = node.getSize();
    return {
      classId: node.id,
      type: 'attribute',
      elementId: attr.id,
      name: attr.name,
      typeOrReturn: attr.type,
      visibility: attr.visibility,
      itemRelY,
      nodeBBox: { x: pos.x, y: pos.y, width: size.width, height: size.height },
      clientX: e.clientX,
      clientY: e.clientY,
    };
  }

  private toDblClickEvent(
    node: Node,
    attr: UmlAttributeRowInput,
    itemRelY: number,
  ): NodeDblClickEvent {
    const pos = node.getPosition();
    const size = node.getSize();
    return {
      nodeId: node.id,
      targetType: 'attribute',
      targetId: attr.id,
      name: attr.name,
      type: attr.type,
      visibility: attr.visibility,
      itemRelY,
      nodeBBox: { x: pos.x, y: pos.y, width: size.width, height: size.height },
    };
  }
}
