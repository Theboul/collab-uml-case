// @ts-check
const eslint = require('@eslint/js');
const tseslint = require('typescript-eslint');
const angular = require('angular-eslint');
const prettierConfig = require('eslint-config-prettier');

module.exports = tseslint.config(
  {
    ignores: ['dist/**', '.angular/**', 'coverage/**', 'node_modules/**'],
  },
  {
    files: ['**/*.ts'],
    extends: [
      eslint.configs.recommended,
      ...tseslint.configs.recommended,
      ...tseslint.configs.stylistic,
      ...angular.configs.tsRecommended,
      prettierConfig,
    ],
    processor: angular.processInlineTemplates,
    rules: {
      // Prefijo unico del design system SchemaCraft (ver .agents/rules/tooling_and_quality_gates.md).
      // 'app' se acepta temporalmente solo dentro de features/modeling (codigo legado JointJS en migracion a X6).
      '@angular-eslint/component-selector': [
        'error',
        { type: 'element', prefix: ['sc', 'app'], style: 'kebab-case' },
      ],
      '@angular-eslint/directive-selector': [
        'error',
        { type: 'attribute', prefix: ['sc', 'app'], style: 'camelCase' },
      ],
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/explicit-function-return-type': 'off',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      // Nadie inyecta HttpClient directo en un componente (regla dura de AGENTS.md #6/#4).
      'no-restricted-imports': [
        'error',
        {
          paths: [
            {
              name: '@angular/common/http',
              importNames: ['HttpClient'],
              message:
                'No inyectes HttpClient en componentes. Usa un Facade/Application Service que pase por un Gateway (ver AGENTS.md seccion "Frontend architecture").',
            },
          ],
        },
      ],
    },
  },
  {
    // El motor de canvas (AntV X6) solo puede vivir en su carpeta de infraestructura.
    files: ['**/*.ts'],
    ignores: ['**/features/modeling/infrastructure/x6/**', '**/features/modeling/infrastructure/jointjs/**'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          paths: [
            {
              name: '@antv/x6',
              message:
                'El motor de canvas X6 esta confinado a features/modeling/infrastructure/x6/ (ver AGENTS.md seccion "Frontend architecture" y .agents/rules/code_quality.md).',
            },
            {
              name: 'jointjs',
              message:
                'JointJS es legado y esta confinado a features/modeling/infrastructure/jointjs/ (en migracion a X6, ver CLAUDE.md).',
            },
          ],
          patterns: [
            {
              group: ['@antv/x6-plugin-*'],
              message: 'Los plugins de X6 solo se importan dentro de features/modeling/infrastructure/x6/.',
            },
          ],
        },
      ],
    },
  },
  {
    files: ['**/*.html'],
    extends: [...angular.configs.templateRecommended, ...angular.configs.templateAccessibility],
    rules: {},
  },
  {
    files: ['**/*.spec.ts'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
);
