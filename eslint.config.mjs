import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import globals from 'globals';
import react from 'eslint-plugin-react';

export default tseslint.config(
  {
    ignores: [
      '**/node_modules/**',
      '.venv/**',
      'vendor/**',
      'reports/**',
      'coverage/**',
      'playwright-report/**',
      'test-results/**',
      '.stryker-tmp/**',
      'src/crossword/static/lib/**',
      'src/crossword/static/react/**',
    ],
  },
  js.configs.recommended,
  {
    files: ['**/*.{js,mjs,cjs,jsx,ts,tsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      globals: { ...globals.browser, ...globals.node },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: {
      'no-unused-vars': ['error', { ignoreRestSiblings: true }],
    },
  },
  {
    files: [
      'src/crossword/static/{main,mobile}.js',
      'apps/react/src/behavior/{desktop,mobile}.js',
    ],
    // Preserve the mirrored legacy sources. These are the only inherited
    // exceptions: direct hasOwnProperty and unused injected/callback arguments.
    // Undefined variables and the other recommended correctness checks remain on.
    rules: {
      'no-prototype-builtins': 'off',
      'no-unused-vars': ['error', { args: 'none', caughtErrors: 'none' }],
    },
  },
  {
    files: ['**/*.{jsx,tsx}'],
    ...react.configs.flat.recommended,
    settings: { react: { version: 'detect' } },
    rules: {
      ...react.configs.flat.recommended.rules,
      // Props currently come from the dynamic legacy controller; checkJs checks
      // JSX/DOM contracts. Runtime PropTypes are not used by this React 19 app.
      'react/prop-types': 'off',
      // Apostrophes in ordinary JSX prose are valid; still flag delimiters that
      // commonly indicate accidentally terminated markup or attributes.
      'react/no-unescaped-entities': ['error', { forbid: ['>', '}', '"'] }],
    },
  },
  ...tseslint.configs.recommended.map((config) => ({
    ...config,
    files: ['**/*.{ts,tsx}'],
  })),
  {
    files: ['**/*.{ts,tsx}'],
    rules: {
      '@typescript-eslint/no-unused-vars': [
        'error',
        { ignoreRestSiblings: true },
      ],
    },
  },
  {
    files: ['**/*.test.{js,jsx}', 'tests/**/*.js'],
    languageOptions: { globals: globals.jest },
  },
  {
    files: ['src/crossword/static/{main,mobile}.js'],
    languageOptions: {
      sourceType: 'script',
      globals: {
        Vue: 'readonly',
        axios: 'readonly',
        io: 'readonly',
        ROOM_ID: 'readonly',
        INITIAL_ROLE: 'readonly',
      },
    },
  },
);
