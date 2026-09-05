import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class SqlExportService {

  private typeMap: Record<string, string> = {
    'UUID': 'UUID',
    'String': 'VARCHAR(255)',
    'Text': 'TEXT',
    'Integer': 'INT',
    'Int': 'INT',
    'int': 'INT',
    'Long': 'BIGINT',
    'Boolean': 'BOOLEAN',
    'Float': 'FLOAT',
    'Double': 'DOUBLE PRECISION',
    'Decimal': 'DECIMAL(15,2)',
    'Date': 'DATE',
    'DateTime': 'TIMESTAMP'
  };

  private invalidPkTypes = new Set(['TEXT', 'FLOAT', 'DOUBLE PRECISION', 'DECIMAL(15,2)', 'BOOLEAN']);

  exportToSql(umlJson: any, dbName: string = 'uml_database'): string {
    let sql = '';
    sql += `CREATE DATABASE ${dbName};\n`;
    sql += `USE ${dbName};\n\n`;

    // ====== TABLAS ======
    for (const cls of umlJson.classes) {
      // Verificar si la clase es hija en una relación de herencia
      const generalizationRel = umlJson.relationships.find((rel: any) => rel.type === 'generalization' && rel.sourceId === cls.id);
      sql += `CREATE TABLE ${cls.name} (\n`;
      const columns: string[] = [];
      if (generalizationRel) {
        // Es clase hija: la PK es la referencia al padre, con mismo nombre y tipo
        const parent = umlJson.classes.find((c: any) => c.id === generalizationRel.targetId);
        let parentPkName = 'id';
        let parentPkType = 'UUID';
        if (parent.attributes && parent.attributes.length > 0) {
          const firstAttr = parent.attributes[0];
          parentPkName = firstAttr.name;
          parentPkType = this.typeMap[firstAttr.type] || 'VARCHAR(255)';
        }
        columns.push(`  ${parentPkName} ${parentPkType} PRIMARY KEY`);
        if (cls.attributes && cls.attributes.length > 0) {
          cls.attributes.forEach((attr: any) => {
            if (attr.name !== parentPkName) {
              const sqlType = this.typeMap[attr.type] || 'VARCHAR(255)';
              columns.push(`  ${attr.name} ${sqlType}`);
            }
          });
        }
      } else if (!cls.attributes || cls.attributes.length === 0) {
        columns.push(`  id UUID PRIMARY KEY`);
      } else {
        cls.attributes.forEach((attr: any, index: number) => {
          const sqlType = this.typeMap[attr.type] || 'VARCHAR(255)';
          let colDef = `  ${attr.name} ${sqlType}`;
          if (index === 0) {
            if (this.invalidPkTypes.has(sqlType)) {
              columns.push(`  id UUID PRIMARY KEY`);
              columns.push(colDef);
            } else {
              colDef += ' PRIMARY KEY';
              columns.push(colDef);
            }
          } else {
            columns.push(colDef);
          }
        });
      }
      sql += columns.join(',\n') + `\n);\n\n`;
    }

    // ====== RELACIONES ======
    for (const rel of umlJson.relationships) {
      const source = umlJson.classes.find((c: any) => c.id === rel.sourceId);
      const target = umlJson.classes.find((c: any) => c.id === rel.targetId);
      if (!source || !target) continue;

      // Multiplicidad
      const multSource = rel.labels?.[0] || '1';
      const multTarget = rel.labels?.[1] || '1';

      // N:M → tabla intermedia
      if (multSource.includes('*') && multTarget.includes('*')) {
        const joinTable = `${source.name}_${target.name}`;
        sql += `CREATE TABLE ${joinTable} (\n`;
        sql += `  ${source.name.toLowerCase()}_id UUID NOT NULL,\n`;
        sql += `  ${target.name.toLowerCase()}_id UUID NOT NULL,\n`;
        sql += `  PRIMARY KEY (${source.name.toLowerCase()}_id, ${target.name.toLowerCase()}_id),\n`;
        sql += `  CONSTRAINT fk_${joinTable}_${source.name.toLowerCase()} FOREIGN KEY (${source.name.toLowerCase()}_id) REFERENCES ${source.name}(${this.getPrimaryKey(source)}) ON DELETE CASCADE ON UPDATE CASCADE,\n`;
        sql += `  CONSTRAINT fk_${joinTable}_${target.name.toLowerCase()} FOREIGN KEY (${target.name.toLowerCase()}_id) REFERENCES ${target.name}(${this.getPrimaryKey(target)}) ON DELETE CASCADE ON UPDATE CASCADE\n`;
        sql += `);\n\n`;
        continue;
      }

      // Determinar el lado de la FK según multiplicidad
      let fkTable = source;
      let refTable = target;
      let fkName = `fk_${source.name.toLowerCase()}_${target.name.toLowerCase()}`;
      let column = `${target.name.toLowerCase()}_id`;
      let onDelete = 'SET NULL';
      let notNull = '';

      // Si es 1:N, la FK va en el lado N, o si es dependencia, siempre FK en source
      if (['association', 'aggregation', 'composition', 'dependency'].includes(rel.type)) {
        if (rel.type === 'dependency') {
          // Siempre FK en el source hacia el target
          fkTable = source;
          refTable = target;
          fkName = `fk_${source.name.toLowerCase()}_${target.name.toLowerCase()}`;
          column = `${target.name.toLowerCase()}_id`;
          onDelete = 'NO ACTION';
          notNull = '';
        } else {
          if (multSource.includes('*') && !multTarget.includes('*')) {
            // source: muchos, target: uno → FK en source
            fkTable = source;
            refTable = target;
            fkName = `fk_${source.name.toLowerCase()}_${target.name.toLowerCase()}`;
            column = `${target.name.toLowerCase()}_id`;
          } else if (!multSource.includes('*') && multTarget.includes('*')) {
            // source: uno, target: muchos → FK en target
            fkTable = target;
            refTable = source;
            fkName = `fk_${target.name.toLowerCase()}_${source.name.toLowerCase()}`;
            column = `${source.name.toLowerCase()}_id`;
          } else {
            // 1:1 o caso ambiguo, por convención FK en source
            fkTable = source;
            refTable = target;
            fkName = `fk_${source.name.toLowerCase()}_${target.name.toLowerCase()}`;
            column = `${target.name.toLowerCase()}_id`;
          }
          // Composición: FK NOT NULL y ON DELETE CASCADE
          if (rel.type === 'composition') {
            notNull = ' NOT NULL';
            onDelete = 'CASCADE';
          } else if (rel.type === 'aggregation') {
            onDelete = 'SET NULL';
          } else if (rel.type === 'association') {
            onDelete = 'SET NULL';
          }
        }
        sql += `ALTER TABLE ${fkTable.name}\n`;
        sql += `  ADD COLUMN ${column} UUID${notNull},\n`;
        sql += `  ADD CONSTRAINT ${fkName} FOREIGN KEY (${column}) REFERENCES ${refTable.name}(${this.getPrimaryKey(refTable)}) ON DELETE ${onDelete} ON UPDATE CASCADE;\n\n`;
        continue;
      }
    }

    return sql.trim();
  }

  private getPrimaryKey(cls: any): string {
    if (!cls.attributes || cls.attributes.length === 0) return 'id';

    const firstAttr = cls.attributes[0];
    const sqlType = this.typeMap[firstAttr.type] || 'VARCHAR(255)';

    return this.invalidPkTypes.has(sqlType) ? 'id' : firstAttr.name;
  }

  downloadSql(umlJson: any, fileName: string = 'diagram.sql'): void {
    const sqlContent = this.exportToSql(umlJson);
    const blob = new Blob([sqlContent], { type: 'text/sql' });
    const url = window.URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    a.click();

    window.URL.revokeObjectURL(url);
  }
}
