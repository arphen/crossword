/* Fixed host bridge for the shared TypeScript reflection evidence conversion. */
const fs = require('node:fs');
const ts = require('typescript');

require.extensions['.ts'] = (module, filename) => {
  const source = fs.readFileSync(filename, 'utf8');
  const result = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
    fileName: filename,
  });
  module._compile(result.outputText, filename);
};

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const reflection = require('../packages/domain/src/reflection.ts');

try {
  if (input.operation === 'convert-response') {
    const evidence = reflection.reflectionResponseToEvidence(input.card, input.response);
    process.stdout.write(JSON.stringify({ evidence }));
  } else if (input.operation === 'convert-action') {
    const action = reflection.reflectionActionToEvidenceAction(input.action);
    process.stdout.write(JSON.stringify({ action }));
  } else if (input.operation === 'validate-cards') {
    if (!Array.isArray(input.cards) || !input.cards.every(reflection.isPlayableReflectionCard)) {
      throw new Error('Reflection deck contains an invalid or unapproved card');
    }
    process.stdout.write(JSON.stringify({ valid: true }));
  } else {
    throw new Error('Unsupported operation');
  }
} catch (error) {
  process.stderr.write(JSON.stringify({ error: error instanceof Error ? error.message : 'Reflection conversion failed' }));
  process.exitCode = 2;
}
