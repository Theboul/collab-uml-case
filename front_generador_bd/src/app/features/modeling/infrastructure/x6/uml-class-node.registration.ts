import { Graph } from '@antv/x6';

let registered = false;

/**
 * Registra el nodo visual canónico ClaseUML con estructura compartimental
 * (Nombre, Atributos y Operaciones) con SVG responsive y estilizado.
 * Idempotente: sólo lo hace efectivo una vez por sesión del bundle (X6
 * registra shapes en un registro global, no por instancia de Graph).
 */
export function registerUmlClassNode(): void {
  if (registered) return;
  try {
    Graph.registerNode('uml-class-node', {
      inherit: 'rect',
      width: 190,
      height: 130,
      markup: [
        { tagName: 'rect', selector: 'body' },
        { tagName: 'rect', selector: 'header' },
        { tagName: 'rect', selector: 'rowHighlight' },
        { tagName: 'text', selector: 'title' },
        { tagName: 'line', selector: 'separator1' },
        { tagName: 'text', selector: 'attributes', className: 'uml-attributes-text' },
        { tagName: 'line', selector: 'separator2' },
        { tagName: 'text', selector: 'operations', className: 'uml-operations-text' },
      ],
      attrs: {
        body: {
          refWidth: '100%',
          refHeight: '100%',
          fill: '#ffffff',
          stroke: '#1e293b',
          strokeWidth: 1.5,
          rx: 4,
          ry: 4,
        },
        header: {
          refWidth: '100%',
          height: 32,
          fill: '#f8fafc',
          stroke: 'none',
          rx: 4,
          ry: 4,
        },
        rowHighlight: {
          display: 'none',
          fill: '#6366f1',
          fillOpacity: 0.12,
          stroke: '#818cf8',
          strokeWidth: 1,
          rx: 2,
          ry: 2,
          pointerEvents: 'none',
        },
        title: {
          refX: '50%',
          refY: 16,
          textAnchor: 'middle',
          textVerticalAnchor: 'middle',
          fontFamily: 'Inter, system-ui, sans-serif',
          fontSize: 13,
          fontWeight: 700,
          fill: '#0f172a',
        },
        separator1: {
          stroke: '#1e293b',
          strokeWidth: 1.5,
          x1: 0,
          refX2: '100%',
          y1: 32,
          y2: 32,
        },
        attributes: {
          refX: 10,
          refY: 42,
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 11,
          fill: '#334155',
          textAnchor: 'start',
          textVerticalAnchor: 'top',
        },
        separator2: {
          stroke: '#cbd5e1',
          strokeWidth: 1,
          x1: 0,
          refX2: '100%',
          y1: 82,
          y2: 82,
        },
        operations: {
          refX: 10,
          refY: 92,
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 11,
          fill: '#334155',
          textAnchor: 'start',
          textVerticalAnchor: 'top',
        },
      },
    });
    registered = true;
  } catch {
    registered = true;
  }
}
