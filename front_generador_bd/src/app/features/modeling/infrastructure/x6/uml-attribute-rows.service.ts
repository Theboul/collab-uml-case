import { Injectable, NgZone, inject } from '@angular/core';
import { Subject } from 'rxjs';
import { CellView, Graph, Node } from '@antv/x6';
import { UML_NODE_DIMENSIONS, UmlNodeSubElementEvent } from '../../domain/models/uml-editor.models';
import type { NodeDblClickEvent } from './uml-graph.service';

export interface UmlAttributeRowInput {
  id?: string;
  name: string;
  type: string;
  visibility: string;
}

const SVG_NS = 'http://www.w3.org/2000/svg';
const ROW_PADDING_X = 8;
const ICON_SIZE = 13;
const ICON_GAP = 4;
const NAME_TYPE_GAP = 8;
const ROWS_SELECTOR_NAME = 'attributeRows';

/**
 * Dueño de las filas reales del compartimento de atributos (Fase 2): construye y
 * muta a mano el subárbol DOM del selector `attributeRows` del shape registrado en
 * `uml-class-node.registration.ts` — a propósito por fuera del sistema declarativo
 * de `attrs` de X6, porque necesita clip + scroll + listeners por fila, cosas que
 * ese sistema no cubre. Decisión de usar SVG puro (no `foreignObject`) documentada
 * en `docs/analysis/decision-render-atributos-svg-vs-foreignobject.md`.
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

  /** Contenedores con el listener de rueda/mousedown ya wireado (una sola vez por nodo). */
  private readonly wiredContainers = new WeakSet<Element>();
  /** Última lista de atributos pintada por nodo, para poder repintar en el wheel sin pedirla de vuelta. */
  private readonly latestAttributes = new WeakMap<Node, UmlAttributeRowInput[]>();

  /**
   * Reconstruye las filas visibles del compartimento de atributos de `node` según
   * el scroll actual (clampeado a lo que sigue siendo válido si la lista encogió).
   */
  render(
    graph: Graph,
    node: Node,
    attributes: UmlAttributeRowInput[],
    attrBlockHeight: number,
  ): void {
    const view = graph.findViewByCell(node);
    if (!view || !graph.renderer.isViewMounted(view)) {
      this.renderOnceMounted(graph, node, attributes, attrBlockHeight);
      return;
    }

    const container = this.findRowsContainer(graph, node);
    if (!container) return;

    this.latestAttributes.set(node, attributes);

    const visibleRows = Math.max(
      1,
      Math.round(attrBlockHeight / UML_NODE_DIMENSIONS.ATTR_ROW_HEIGHT),
    );
    const maxStartRow = Math.max(0, attributes.length - visibleRows);
    const requestedScroll = (node.prop('attrScrollRow') as number | undefined) ?? 0;
    const scrollRow = Math.min(maxStartRow, Math.max(0, requestedScroll));
    if (scrollRow !== requestedScroll) {
      node.prop('attrScrollRow', scrollRow, { silent: true });
    }

    container.setAttribute('data-total-rows', String(attributes.length));
    container.setAttribute('data-visible-rows', String(visibleRows));

    this.paintRows(node, container, attributes, scrollRow, visibleRows);
    this.wireContainer(node, container);
  }

  /** Fila actualmente en el tope del scroll de un nodo (0 si no hay scroll aplicado). */
  getScrollRow(graph: Graph | null, nodeId: string): number {
    const node = graph?.getCellById(nodeId);
    if (!node || !node.isNode()) return 0;
    return (node.prop('attrScrollRow') as number | undefined) ?? 0;
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
    attrBlockHeight: number,
  ): void {
    const onMounted = ({ view }: { view: CellView }): void => {
      if (view.cell.id !== node.id) return;
      graph.off('view:mounted', onMounted);
      queueMicrotask(() => this.render(graph, node, attributes, attrBlockHeight));
    };
    graph.on('view:mounted', onMounted);
  }

  /**
   * `graph.findViewByCell(node)` expone `selectors` (protected en el tipo, real en
   * runtime) — el mapa selector→Elemento que arma X6 en `parseJSONMarkup` al crear
   * la vista. Confirmado leyendo `@antv/x6/lib/view/markup.js`: ese mapa vive solo
   * en memoria, X6 NUNCA estampa un atributo `data-selector` en el DOM para markup
   * genérico (eso es específico de puertos/magnets, ver `cell.js`). Usar
   * `container.querySelector('[data-selector="..."]')` (como hacía esta función
   * antes) no matchea nunca — `render()` cortaba en el guard de `!container` y las
   * filas jamás se pintaban. Bug real de Fase 2, confirmado por lectura de fuente.
   */
  private findRowsContainer(graph: Graph, node: Node): SVGGElement | null {
    const view = graph.findViewByCell(node) as unknown as {
      selectors?: Record<string, Element | Element[]>;
    } | null;
    const el = view?.selectors?.[ROWS_SELECTOR_NAME];
    if (!el || Array.isArray(el)) return null;
    return el as SVGGElement;
  }

  private paintRows(
    node: Node,
    container: SVGGElement,
    attributes: UmlAttributeRowInput[],
    scrollRow: number,
    visibleRows: number,
  ): void {
    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }
    const nodeWidth = node.getSize().width;
    const slice = attributes.slice(scrollRow, scrollRow + visibleRows);
    slice.forEach((attr, i) => {
      container.appendChild(this.buildRow(node, attr, i, nodeWidth));
    });
  }

  private buildRow(
    node: Node,
    attr: UmlAttributeRowInput,
    rowIndex: number,
    nodeWidth: number,
  ): SVGGElement {
    const rowY = rowIndex * UML_NODE_DIMENSIONS.ATTR_ROW_HEIGHT;
    const centerY = rowY + UML_NODE_DIMENSIONS.ATTR_ROW_HEIGHT / 2;

    const row = document.createElementNS(SVG_NS, 'g');
    row.setAttribute('class', 'uml-attr-row');
    if (attr.id) row.setAttribute('data-attr-id', attr.id);

    const bg = document.createElementNS(SVG_NS, 'rect');
    bg.setAttribute('class', 'uml-attr-row-bg');
    bg.setAttribute('x', '0');
    bg.setAttribute('y', String(rowY));
    bg.setAttribute('width', String(nodeWidth));
    bg.setAttribute('height', String(UML_NODE_DIMENSIONS.ATTR_ROW_HEIGHT));
    bg.setAttribute('fill', 'transparent');
    row.appendChild(bg);

    // fill/font se fijan acá como atributos SVG explícitos, no solo por CSS
    // (::ng-deep en uml-canvas.component.css) — para que el texto sea visible
    // independientemente de cualquier timing/cascada de estilos. La CSS sigue
    // siendo la dueña de los estados dinámicos (hover, opacity del ícono).
    const icon = document.createElementNS(SVG_NS, 'text');
    icon.setAttribute('class', 'uml-attr-delete');
    icon.setAttribute('x', String(nodeWidth - ROW_PADDING_X));
    icon.setAttribute('y', String(centerY));
    icon.setAttribute('text-anchor', 'end');
    icon.setAttribute('dominant-baseline', 'central');
    icon.setAttribute('font-family', 'Material Symbols Outlined');
    icon.setAttribute('font-size', String(ICON_SIZE));
    icon.setAttribute('fill', '#f43f5e');
    icon.textContent = 'delete';
    row.appendChild(icon);

    const typeRightX = nodeWidth - ROW_PADDING_X - ICON_SIZE - ICON_GAP;
    const typeText = document.createElementNS(SVG_NS, 'text');
    typeText.setAttribute('class', 'uml-attr-type');
    typeText.setAttribute('x', String(typeRightX));
    typeText.setAttribute('y', String(centerY));
    typeText.setAttribute('text-anchor', 'end');
    typeText.setAttribute('dominant-baseline', 'central');
    typeText.setAttribute('font-family', 'JetBrains Mono, monospace');
    typeText.setAttribute('font-size', String(UML_NODE_DIMENSIONS.ATTR_FONT_SIZE));
    typeText.setAttribute('fill', '#334155');
    typeText.textContent = `: ${attr.type}`;
    row.appendChild(typeText);

    const fullLabel = `${attr.visibility} ${attr.name}`;
    const nameText = document.createElementNS(SVG_NS, 'text');
    nameText.setAttribute('class', 'uml-attr-name');
    nameText.setAttribute('x', String(ROW_PADDING_X));
    nameText.setAttribute('y', String(centerY));
    nameText.setAttribute('text-anchor', 'start');
    nameText.setAttribute('dominant-baseline', 'central');
    nameText.setAttribute('font-family', 'JetBrains Mono, monospace');
    nameText.setAttribute('font-size', String(UML_NODE_DIMENSIONS.ATTR_FONT_SIZE));
    nameText.setAttribute('fill', '#334155');
    nameText.textContent = fullLabel;
    const title = document.createElementNS(SVG_NS, 'title');
    title.textContent = `${fullLabel} : ${attr.type}`;
    nameText.appendChild(title);
    row.appendChild(nameText);

    // getComputedTextLength() exige que el elemento esté anclado a un <svg> con
    // layout — recién es seguro medir/truncar después de este appendChild, por
    // eso el `row` ya se devuelve completo y el caller lo agrega al contenedor
    // real antes de que se dispare cualquier medición (ver render()/paintRows()).
    queueMicrotask(() => this.truncateNameIfNeeded(nameText, fullLabel, typeText, typeRightX));

    this.wireRowEvents(row, icon, node, attr, rowY);
    return row;
  }

  /**
   * Trunca el nombre con elipsis para que no invada la columna de tipo — no hay
   * `text-overflow` nativo en SVG. Recalcula solo cuando cambian los datos del
   * atributo (ver el `render()` que dispara `buildRow`), no en cada frame de un
   * resize manual en vivo del nodo: limitación aceptada y documentada en
   * docs/analysis/decision-render-atributos-svg-vs-foreignobject.md.
   */
  private truncateNameIfNeeded(
    nameEl: SVGTextElement,
    fullLabel: string,
    typeEl: SVGTextElement,
    typeRightX: number,
  ): void {
    if (!nameEl.isConnected) return;
    const typeWidth = typeEl.getComputedTextLength();
    const maxWidth = Math.max(20, typeRightX - typeWidth - NAME_TYPE_GAP - ROW_PADDING_X);
    if (nameEl.getComputedTextLength() <= maxWidth) return;

    let lo = 0;
    let hi = fullLabel.length;
    while (lo < hi) {
      const mid = Math.ceil((lo + hi) / 2);
      nameEl.textContent = fullLabel.slice(0, mid) + '…';
      if (nameEl.getComputedTextLength() <= maxWidth) {
        lo = mid;
      } else {
        hi = mid - 1;
      }
    }
    nameEl.textContent = lo > 0 ? fullLabel.slice(0, lo) + '…' : '…';
  }

  private wireRowEvents(
    row: SVGGElement,
    icon: SVGTextElement,
    node: Node,
    attr: UmlAttributeRowInput,
    rowRelY: number,
  ): void {
    row.addEventListener('click', (e: MouseEvent) => {
      e.stopPropagation();
      if (!attr.id) return;
      if (e.target === icon) {
        this.ngZone.run(() =>
          this.deleteRequested$.next({ classId: node.id, attributeId: attr.id! }),
        );
        return;
      }
      this.ngZone.run(() => this.rowClick$.next(this.toSubElementEvent(node, attr, rowRelY, e)));
    });

    row.addEventListener('dblclick', (e: MouseEvent) => {
      e.stopPropagation();
      if (e.target === icon || !attr.id) return;
      this.ngZone.run(() => this.rowDblClick$.next(this.toDblClickEvent(node, attr, rowRelY)));
    });
  }

  /** Wireado una sola vez por nodo: bloquea el drag del nodo desde el compartimento y maneja el scroll. */
  private wireContainer(node: Node, container: SVGGElement): void {
    if (this.wiredContainers.has(container)) return;
    this.wiredContainers.add(container);

    container.addEventListener('mousedown', (e: MouseEvent) => e.stopPropagation());

    container.addEventListener('wheel', (e: WheelEvent) => {
      const totalRows = Number(container.getAttribute('data-total-rows') ?? '0');
      const visibleRows = Number(container.getAttribute('data-visible-rows') ?? '1');
      const maxStartRow = Math.max(0, totalRows - visibleRows);
      if (maxStartRow <= 0) return;

      e.preventDefault();
      e.stopPropagation();

      const current = (node.prop('attrScrollRow') as number | undefined) ?? 0;
      const direction = e.deltaY > 0 ? 1 : e.deltaY < 0 ? -1 : 0;
      const next = Math.min(maxStartRow, Math.max(0, current + direction));
      if (next === current) return;

      node.prop('attrScrollRow', next, { silent: true });
      const attributes = this.latestAttributes.get(node) ?? [];
      this.paintRows(node, container, attributes, next, visibleRows);
    });
  }

  private toSubElementEvent(
    node: Node,
    attr: UmlAttributeRowInput,
    rowRelY: number,
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
      itemRelY: UML_NODE_DIMENSIONS.HEADER_HEIGHT + UML_NODE_DIMENSIONS.SEP_PADDING + rowRelY,
      nodeBBox: { x: pos.x, y: pos.y, width: size.width, height: size.height },
      clientX: e.clientX,
      clientY: e.clientY,
    };
  }

  private toDblClickEvent(
    node: Node,
    attr: UmlAttributeRowInput,
    rowRelY: number,
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
      itemRelY: UML_NODE_DIMENSIONS.HEADER_HEIGHT + UML_NODE_DIMENSIONS.SEP_PADDING + rowRelY,
      nodeBBox: { x: pos.x, y: pos.y, width: size.width, height: size.height },
    };
  }
}
