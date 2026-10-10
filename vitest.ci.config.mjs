import { defineConfig } from 'vitest/config';

export default defineConfig({
  esbuild: { jsx: 'automatic' },
  test: {
    include: [
      'apps/react/src/**/*.test.{js,jsx,ts}',
      'packages/*/src/**/*.test.ts',
    ],
    setupFiles: ['apps/react/vitest.setup.js'],
    // Concise console output for agent runs; details stay in the HTML report.
    reporters: ['basic'],
    silent: true,
    coverage: {
      provider: 'v8',
      reportsDirectory: 'coverage/frontend',
      reporter: ['text-summary', 'lcov', 'html', 'json-summary'],
      include: ['apps/react/src/**/*.{js,jsx}', 'packages/*/src/**/*.ts'],
      exclude: ['**/*.test.*', '**/index.ts', 'apps/react/src/main.jsx'],
      // Baselines include uncovered files, not just code imported by tests.
      thresholds: { lines: 50, statements: 50, functions: 45, branches: 40 },
    },
  },
});
