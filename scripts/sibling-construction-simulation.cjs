/* Fixed lab bridge. It loads only the pinned sibling simulator source/export. */
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

require.extensions['.ts'] = (module, filename) => {
  const source = fs.readFileSync(filename, 'utf8');
  const result = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
    fileName: filename,
  });
  module._compile(result.outputText, filename);
};

function loadSimulator() {
  try {
    const exported = require('@crossword/construction');
    if (typeof exported.simulateFinalistSolve === 'function') {
      return { fn: exported.simulateFinalistSolve, source: 'package-export' };
    }
  } catch {
    // The product archive can be a construction-only version. Try the pinned
    // sibling source below; if it is absent the adapter fails closed.
  }
  const configured = process.env.CROSSWORD_SIBLING_CONSTRUCTION_SOURCE;
  const source = configured || path.resolve(__dirname, '../../crossword-generator/packages/construction/src/solveSimulation.ts');
  if (!path.isAbsolute(source) || !fs.existsSync(source)) return undefined;
  const exported = require(source);
  if (typeof exported.simulateFinalistSolve !== 'function') return undefined;
  return { fn: exported.simulateFinalistSolve, source: 'pinned-sibling-source' };
}

try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const simulator = loadSimulator();
  if (!simulator) {
    process.stdout.write(JSON.stringify({ version: 1, status: 'unavailable', reason: 'construction-simulator-export-unavailable' }));
  } else {
    const result = simulator.fn(input);
    process.stdout.write(JSON.stringify({
      version: 1,
      status: 'invoked',
      simulator: { package: '@crossword/construction', source: simulator.source, protocol: 'explicit-estimates-greedy-v1' },
      result,
    }));
  }
} catch (error) {
  process.stdout.write(JSON.stringify({ version: 1, status: 'unavailable', reason: error instanceof Error ? error.message : 'simulator-failed' }));
}
