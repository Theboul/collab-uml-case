/**
 * Medición y envoltura de texto para el nodo de clase UML. SVG no tiene layout de
 * texto propio (no hay `text-overflow` ni `word-wrap`), así que el ancho y el alto del
 * nodo se calculan midiendo con un `<canvas>` con la misma fuente que el shape usa.
 */

export type TextMeasure = (text: string, font: string) => number;

/** Fuentes del shape (deben coincidir con `uml-class-node.registration.ts` y `UmlAttributeRowsService`). */
export const UML_FONTS = {
  title: '700 13px Inter, system-ui, sans-serif',
  mono: '12px "JetBrains Mono", monospace',
} as const;

/** Margen de seguridad (px) al decidir si un texto entra: cubre el redondeo de subpíxeles entre canvas y SVG. */
export const FIT_MARGIN = 2;
const MAX_CACHE_ENTRIES = 5000;

let measureContext: CanvasRenderingContext2D | null | undefined;
const widthCache = new Map<string, number>();

function fallbackWidth(text: string, font: string): number {
  const size = Number(/(\d+(?:\.\d+)?)px/.exec(font)?.[1] ?? 12);
  return text.length * size * 0.6;
}

function getContext(): CanvasRenderingContext2D | null {
  if (measureContext !== undefined) return measureContext;
  try {
    measureContext =
      typeof document === 'undefined' ? null : document.createElement('canvas').getContext('2d');
  } catch {
    measureContext = null;
  }
  return measureContext;
}

/** Ancho en px de `text` con `font`, medido con canvas (con caché) o estimado si no hay canvas. */
export const measureTextWidth: TextMeasure = (text, font) => {
  if (text === '') return 0;
  const key = `${font}|${text}`;
  const cached = widthCache.get(key);
  if (cached !== undefined) return cached;

  const ctx = getContext();
  let width: number;
  if (ctx) {
    ctx.font = font;
    width = ctx.measureText(text).width;
  } else {
    width = fallbackWidth(text, font);
  }
  if (widthCache.size >= MAX_CACHE_ENTRIES) widthCache.clear();
  widthCache.set(key, width);
  return width;
};

/**
 * Parte `text` en tramos donde una línea puede cortarse: después de espacios y comas,
 * después de `_` y en cada salto minúscula→Mayúscula (`GestorDeFacturacion` →
 * `Gestor|De|Facturacion`). Sin esto un nombre CamelCase largo (sin espacios) solo
 * se podría cortar a mitad de palabra.
 */
function splitBreakable(text: string): string[] {
  return text.split(/(?<=[ ,_])|(?<=[a-z0-9])(?=[A-Z])/).filter((t) => t !== '');
}

/**
 * Envuelve `text` en líneas que entren en `firstWidth` (primera línea) y `restWidth`
 * (las demás, p. ej. con sangría). Corta en los puntos de `splitBreakable`; un tramo que
 * por sí solo no entra se corta por caracteres. Nunca devuelve una lista vacía.
 */
export function wrapText(
  text: string,
  firstWidth: number,
  restWidth: number,
  font: string,
  measure: TextMeasure = measureTextWidth,
): string[] {
  const fits = (candidate: string, lineIndex: number): boolean =>
    measure(candidate.trimEnd(), font) <= (lineIndex === 0 ? firstWidth : restWidth) - FIT_MARGIN;

  const lines: string[] = [];
  let current = '';

  for (const token of splitBreakable(text)) {
    if (fits(current + token, lines.length)) {
      current += token;
      continue;
    }
    if (current.trim() !== '') {
      lines.push(current.trimEnd());
      current = '';
    }
    let rest = token.trimStart();
    while (rest !== '' && !fits(rest, lines.length)) {
      let cut = 1;
      while (cut < rest.length && fits(rest.slice(0, cut + 1), lines.length)) cut++;
      lines.push(rest.slice(0, cut));
      rest = rest.slice(cut);
    }
    current = rest;
  }

  if (current.trim() !== '' || lines.length === 0) lines.push(current.trimEnd());
  return lines;
}
