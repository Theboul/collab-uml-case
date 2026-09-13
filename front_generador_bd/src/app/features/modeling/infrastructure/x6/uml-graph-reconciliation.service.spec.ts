import { computeIdDiff } from './uml-graph-reconciliation.service';

describe('computeIdDiff', () => {
  it('detecta altas cuando un id existe solo en el modelo nuevo', () => {
    const diff = computeIdDiff(['a'], ['a', 'b']);
    expect(diff.toAdd).toEqual(['b']);
    expect(diff.toRemove).toEqual([]);
    expect(diff.toKeep).toEqual(['a']);
  });

  it('detecta bajas cuando un id existe solo en el grafo actual', () => {
    const diff = computeIdDiff(['a', 'b'], ['a']);
    expect(diff.toAdd).toEqual([]);
    expect(diff.toRemove).toEqual(['b']);
    expect(diff.toKeep).toEqual(['a']);
  });

  it('no marca nada para reconciliar cuando ambos conjuntos son iguales', () => {
    const diff = computeIdDiff(['a', 'b'], ['a', 'b']);
    expect(diff.toAdd).toEqual([]);
    expect(diff.toRemove).toEqual([]);
    expect(diff.toKeep).toEqual(['a', 'b']);
  });

  it('trata un id reemplazado (mismo elemento lógico, id distinto) como baja + alta independientes', () => {
    // Escenario del fallback esperado: si el id de un nodo/edge cambiara entre dos
    // snapshots consecutivos, no hay heurística de "parecido" — se remueve el viejo
    // id y se agrega el nuevo como si fueran entidades distintas.
    const diff = computeIdDiff(['old-id'], ['new-id']);
    expect(diff.toAdd).toEqual(['new-id']);
    expect(diff.toRemove).toEqual(['old-id']);
    expect(diff.toKeep).toEqual([]);
  });

  it('devuelve listas vacías cuando ambos conjuntos están vacíos', () => {
    const diff = computeIdDiff([], []);
    expect(diff.toAdd).toEqual([]);
    expect(diff.toRemove).toEqual([]);
    expect(diff.toKeep).toEqual([]);
  });
});
