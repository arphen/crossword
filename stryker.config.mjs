export default {
  $schema: './node_modules/@stryker-mutator/core/schema/stryker-schema.json',
  // Mutate this repository, not the optional sibling generator checkout.
  mutate: ['packages/domain/src/puzzle.ts', 'packages/domain/src/session.ts'],
  testRunner: 'vitest',
  vitest: { configFile: 'vitest.mutation.config.mjs' },
  coverageAnalysis: 'perTest',
  concurrency: 2,
  reporters: ['clear-text', 'progress', 'html', 'json'],
  htmlReporter: { fileName: 'reports/mutation/index.html' },
  jsonReporter: { fileName: 'reports/mutation/mutation.json' },
  // Baseline from the measured run (59.64%): session.ts blocked-cell handling
  // is untestable against the current fixture topology (see TESTING.md debt).
  thresholds: { high: 80, low: 55, break: 55 },
  timeoutMS: 10000,
  timeoutFactor: 2,
};
