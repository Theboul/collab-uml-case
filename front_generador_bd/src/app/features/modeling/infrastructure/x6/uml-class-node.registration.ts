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
      // Sin `inherit: 'rect'`: ese shape trae defaults para los selectores CSS `rect` y
      // `text` (fuente 14 Arial, text-anchor middle, borde #333…) que X6 re-aplica a
      // TODOS los <rect>/<text> de la vista en cada actualización — incluidas las filas
      // de atributos y operaciones que pinta UmlAttributeRowsService a mano — y las
      // desarmaban (p. ej. al resaltar una fila).
      width: 190,
      height: 130,
      markup: [
        { tagName: 'rect', selector: 'body' },
        { tagName: 'rect', selector: 'header' },
        // Aplana las esquinas inferiores (redondeadas) del encabezado, que ahora tiene color propio.
        { tagName: 'rect', selector: 'headerCap' },
        { tagName: 'rect', selector: 'rowHighlight' },
        { tagName: 'text', selector: 'title' },
        // Separadores como rect de ancho relativo: un <line> no puede expresar
        // `x2 = 100%` (refX2 es alias de refX y solo traslada el elemento).
        { tagName: 'rect', selector: 'separator1' },
        // Filas reales de atributo y de operación: grupos vacíos poblados/mutados
        // directamente en el DOM por UmlAttributeRowsService, fuera del sistema
        // declarativo de attrs de X6 (necesitan filas de alto variable por envoltura
        // de texto y listeners por fila).
        { tagName: 'g', selector: 'attributeRows' },
        { tagName: 'rect', selector: 'separator2' },
        { tagName: 'g', selector: 'operationRows' },
        // Contorno encima de todo: el encabezado con fondo propio y el hover de fila
        // taparían la mitad interior de un trazo dibujado en `body`.
        { tagName: 'rect', selector: 'frame' },
      ],
      attrs: {
        body: {
          refWidth: '100%',
          refHeight: '100%',
          fill: '#ffffff',
          stroke: 'none',
          rx: 4,
          ry: 4,
        },
        header: {
          refWidth: '100%',
          height: 32,
          fill: '#e0e7ff',
          stroke: 'none',
          rx: 4,
          ry: 4,
        },
        headerCap: {
          refWidth: '100%',
          height: 4,
          y: 28,
          fill: '#e0e7ff',
          stroke: 'none',
        },
        frame: {
          refWidth: '100%',
          refHeight: '100%',
          fill: 'none',
          stroke: '#1e293b',
          strokeWidth: 1.5,
          rx: 4,
          ry: 4,
          pointerEvents: 'none',
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
          lineHeight: 18,
          fill: '#0f172a',
        },
        separator1: {
          refWidth: '100%',
          height: 1.5,
          y: 31.25,
          fill: '#1e293b',
          stroke: 'none',
        },
        attributeRows: {
          refX: 0,
          refY: 42,
        },
        separator2: {
          refWidth: '100%',
          height: 1.5,
          y: 81.25,
          fill: '#cbd5e1',
          stroke: 'none',
        },
        operationRows: {
          refX: 0,
          refY: 92,
        },
      },
    });
    registered = true;
  } catch {
    registered = true;
  }
}
