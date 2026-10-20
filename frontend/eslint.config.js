// @ts-check
import eslint from '@eslint/js';
import tseslint from 'typescript-eslint';
import angular from 'angular-eslint';

export default tseslint.config(
  {
    files: ['**/*.ts'],
    extends: [
      eslint.configs.recommended,
      ...tseslint.configs.recommendedTypeChecked,
      ...angular.configs.tsRecommended,
    ],
    languageOptions: {
      parserOptions: {
        projectService: true,
      },
    },
    processor: angular.processInlineTemplates,
    rules: {
      '@angular-eslint/directive-selector': [
        'error',
        { type: 'attribute', prefix: 'app', style: 'camelCase' },
      ],
      '@angular-eslint/component-selector': [
        'error',
        { type: 'element', prefix: 'app', style: 'kebab-case' },
      ],

      // Rule 7: three files, always. These two make it an error rather than a
      // review comment.
      '@angular-eslint/prefer-standalone': 'error',
      '@angular-eslint/use-component-view-encapsulation': 'off',

      // Rule 5: nothing unused.
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],

      // Rule 10: no setTimeout. The hook blocks it too; this catches it in the
      // editor rather than after the write.
      'no-restricted-globals': [
        'error',
        { name: 'setTimeout', message: 'Rule 10: model the timing in state.' },
        { name: 'setInterval', message: 'Rule 10: model the timing in state.' },
        { name: 'confirm', message: 'Rule 9: ask with MatDialog.' },
        { name: 'alert', message: 'Rule 9: report with MatSnackBar, or a role="alert" message in the page.' },
        { name: 'prompt', message: 'Rule 9: collect with a mat-form-field, in the page or in a MatDialog.' },
      ],

      // Rule 30: no `any`.
      '@typescript-eslint/no-explicit-any': 'error',

      // Rule 8: signals, not subjects, for view state.
      'no-restricted-imports': [
        'error',
        {
          paths: [
            {
              name: 'rxjs',
              importNames: ['BehaviorSubject'],
              message: 'Rule 8: view state is a signal.',
            },
          ],
        },
      ],
    },
  },
  {
    files: ['**/*.ts'],
    ignores: ['**/*.types.ts', '**/*.d.ts'],
    rules: {
      // Rule 30: interfaces and type aliases live in a sibling `*.types.ts`.
      'no-restricted-syntax': [
        'error',
        {
          selector: 'TSInterfaceDeclaration, TSTypeAliasDeclaration',
          message: 'Rule 30: declare it in a sibling *.types.ts and import it with `import type`.',
        },
      ],
    },
  },
  {
    // The journeys: the same type rule as above, which this block would otherwise replace,
    // and no waiting for time.
    files: ['e2e/**/*.ts'],
    ignores: ['**/*.types.ts'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: 'TSInterfaceDeclaration, TSTypeAliasDeclaration',
          message: 'Rule 30: declare it in a sibling *.types.ts and import it with `import type`.',
        },
        {
          selector: "CallExpression[callee.property.name='waitForTimeout']",
          message: 'Wait for what the page shows, with expect or expect.poll, never for a time.',
        },
      ],
    },
  },
  {
    files: ['**/*.html'],
    extends: [...angular.configs.templateRecommended, ...angular.configs.templateAccessibility],
    rules: {},
  },
);
