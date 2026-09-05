import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const fixturesDir = path.resolve(__dirname, '../fixtures/legacy');

/**
 * Replicación fiel de la lógica de parseo y serialización de `DiagramExportService`
 * de Angular (`front_generador_bd/src/services/exports/diagram-export.service.ts`).
 */
class LegacyDiagramExportService {
  parseAttributesFromText(text) {
    if (!text) return [];
    return text.split('\n').map(line => {
      const [name, type] = line.split(':').map(s => s.trim());
      return { name: name || '', type: type || '' };
    });
  }

  parseMethodsFromText(text) {
    if (!text) return [];
    return text.split('\n').map(line => {
      const parts = line.split('(');
      const name = parts[0]?.trim() || '';
      let parameters = '';
      let returnType = '';
      if (parts[1]) {
        const sub = parts[1].split(')');
        parameters = sub[0]?.trim() || '';
        if (sub[1]) {
          returnType = sub[1].replace(':', '').trim();
        }
      }
      return { name, parameters, returnType };
    });
  }

  exportFromCells(cells) {
    const classes = [];
    const relationships = [];

    cells.forEach(cell => {
      if (cell.isElement) {
        const rawAttrs = cell.attributes;
        const rawMeths = cell.methods;

        const attributes = Array.isArray(rawAttrs)
          ? rawAttrs
          : this.parseAttributesFromText(rawAttrs);

        const methods = Array.isArray(rawMeths)
          ? rawMeths
          : this.parseMethodsFromText(rawMeths);

        classes.push({
          id: cell.id,
          name: cell.name,
          attributes,
          methods,
          position: cell.position || { x: 0, y: 0 },
          size: cell.size || { width: 100, height: 100 }
        });
      } else if (cell.isLink) {
        relationships.push({
          id: cell.id,
          type: cell.relationType || 'association',
          sourceId: cell.source?.id,
          targetId: cell.target?.id,
          labels: (cell.labels || []).map(lbl => lbl.text || lbl),
          vertices: cell.vertices || []
        });
      }
    });

    return { classes, relationships };
  }
}

describe('Frontend Angular Legacy Serialization Tests (SPEC-04)', () => {
  const service = new LegacyDiagramExportService();

  test('T-FE-01: Serialización de clase UML', () => {
    const rawCells = [
      {
        id: 'cls-cliente-1',
        isElement: true,
        name: 'Cliente',
        attributes: [
          { name: 'id', type: 'Long' },
          { name: 'nombre', type: 'String' },
          { name: 'email', type: 'String' }
        ],
        methods: [],
        position: { x: 100, y: 120 },
        size: { width: 200, height: 140 }
      }
    ];

    const result = service.exportFromCells(rawCells);
    const expected = JSON.parse(fs.readFileSync(path.join(fixturesDir, 'F01-simple-class.json'), 'utf-8'));

    assert.equal(result.classes.length, 1);
    assert.equal(result.classes[0].name, 'Cliente');
    assert.equal(result.classes[0].id, 'cls-cliente-1');
    assert.deepEqual(result.classes[0].attributes, expected.classes[0].attributes);
  });

  test('T-FE-02: Serialización de atributos y parseo de texto multilínea', () => {
    const multilineText = 'id: Long\nnombre: String\nemail: String';
    const parsed = service.parseAttributesFromText(multilineText);

    assert.equal(parsed.length, 3);
    assert.deepEqual(parsed[0], { name: 'id', type: 'Long' });
    assert.deepEqual(parsed[1], { name: 'nombre', type: 'String' });
    assert.deepEqual(parsed[2], { name: 'email', type: 'String' });

    // Defecto legacy: línea sin dos puntos asigna tipo vacío
    const invalidLine = service.parseAttributesFromText('sinTipo');
    assert.deepEqual(invalidLine[0], { name: 'sinTipo', type: '' });
  });

  test('T-FE-03: Serialización de operaciones', () => {
    const rawCell = {
      id: 'cls-cliente-2',
      isElement: true,
      name: 'Cliente',
      attributes: 'id: Long',
      methods: 'calcularDescuento(porcentaje: Double): Double',
      position: { x: 100, y: 120 },
      size: { width: 260, height: 140 }
    };

    const result = service.exportFromCells([rawCell]);
    const expected = JSON.parse(fs.readFileSync(path.join(fixturesDir, 'F02-operation.json'), 'utf-8'));

    assert.equal(result.classes[0].methods.length, 1);
    assert.equal(result.classes[0].methods[0].name, 'calcularDescuento');
    assert.equal(result.classes[0].methods[0].parameters, 'porcentaje: Double');
    assert.equal(result.classes[0].methods[0].returnType, 'Double');
    assert.deepEqual(result.classes[0].methods, expected.classes[0].methods);
  });

  test('T-FE-04: Serialización de relaciones', () => {
    const linkCell = {
      id: 'rel-cliente-pedido-3',
      isLink: true,
      relationType: 'association',
      source: { id: 'cls-cliente-3' },
      target: { id: 'cls-pedido-3' },
      labels: [{ text: '1' }, { text: '0..*' }],
      vertices: []
    };

    const result = service.exportFromCells([linkCell]);
    const expected = JSON.parse(fs.readFileSync(path.join(fixturesDir, 'F03-one-to-many.json'), 'utf-8'));

    assert.equal(result.relationships.length, 1);
    assert.equal(result.relationships[0].sourceId, 'cls-cliente-3');
    assert.equal(result.relationships[0].targetId, 'cls-pedido-3');
    assert.equal(result.relationships[0].type, 'association');
    assert.deepEqual(result.relationships[0].labels, expected.relationships[0].labels);
  });

  test('T-FE-05: Multiplicidades legacy soportadas', () => {
    const supportedMultiplicities = ['1', '*', '0..1', '0..*', '1..*'];
    const links = supportedMultiplicities.map((mult, idx) => ({
      id: `rel-${idx}`,
      isLink: true,
      relationType: 'association',
      source: { id: 'c1' },
      target: { id: 'c2' },
      labels: [{ text: mult }, { text: '1' }]
    }));

    const result = service.exportFromCells(links);
    assert.equal(result.relationships.length, supportedMultiplicities.length);
    result.relationships.forEach((rel, idx) => {
      assert.equal(rel.labels[0], supportedMultiplicities[idx]);
    });
  });

  test('T-FE-06: Exportación del modelo combinado F08', () => {
    const f08Expected = JSON.parse(fs.readFileSync(path.join(fixturesDir, 'F08-combined-model.json'), 'utf-8'));
    
    // Construir celdas correspondientes a F08
    const mockCells = [
      ...f08Expected.classes.map(c => ({
        id: c.id,
        isElement: true,
        name: c.name,
        attributes: c.attributes,
        methods: c.methods,
        position: c.position,
        size: c.size
      })),
      ...f08Expected.relationships.map(r => ({
        id: r.id,
        isLink: true,
        relationType: r.type,
        source: { id: r.sourceId },
        target: { id: r.targetId },
        labels: r.labels.map(l => ({ text: l })),
        vertices: r.vertices
      }))
    ];

    const result = service.exportFromCells(mockCells);

    assert.equal(result.classes.length, f08Expected.classes.length);
    assert.equal(result.relationships.length, f08Expected.relationships.length);
    assert.deepEqual(result.classes.map(c => c.name), f08Expected.classes.map(c => c.name));
    assert.deepEqual(result.relationships.map(r => r.type), f08Expected.relationships.map(r => r.type));
  });
});
