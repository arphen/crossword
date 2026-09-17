import { defineConfig } from 'vitest/config';

export default defineConfig({
  esbuild: { jsx: 'automatic' },
  test: {
    include: ['apps/react/src/**/*.test.{js,jsx}', 'packages/*/src/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reportsDirectory: 'coverage/frontend',
      reporter: ['text', 'lcov', 'html', 'json-summary'],
      include: ['apps/react/src/**/*.{js,jsx}', 'packages/*/src/**/*.ts'],
      exclude: ['**/*.test.*', '**/index.ts', 'apps/react/src/main.jsx'],
      // Baselines include uncovered files, not just code imported by tests.
      thresholds: { lines: 50, statements: 50, functions: 45, branches: 40 },
    },
  },
});
