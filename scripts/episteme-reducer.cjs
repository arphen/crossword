/* Fixed local bridge to the shared TypeScript reducer; input cannot name code or files. */
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
const reducer = require('../packages/domain/src/episteme.ts');
const briefCompiler = require('../packages/domain/src/epistemeBrief.ts');

try {
  if (input.operation === 'create') {
    process.stdout.write(JSON.stringify({ profile: reducer.createEpistemeProfile(input.profileId, input.createdAt) }));
  } else if (input.operation === 'apply') {
    process.stdout.write(JSON.stringify(reducer.applyEpistemeUpdate(input.profile, input.command)));
  } else if (input.operation === 'project') {
    process.stdout.write(JSON.stringify({ profile: reducer.projectEpistemeProfile(input.profile, input.asOf) }));
  } else if (input.operation === 'brief') {
    process.stdout.write(JSON.stringify({
      brief: briefCompiler.compileEpistemeBrief(input.profile, input.candidates, input.options),
    }));
  } else {
    throw new Error('Unsupported operation');
  }
} catch (error) {
  process.stderr.write(JSON.stringify({ error: error instanceof Error ? error.message : 'Reducer failed' }));
  process.exitCode = 2;
}
