/* Emit the bounded synthetic seek/avoid retrieval evaluation report. */
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');
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

const evaluation = require('../packages/domain/src/epistemeBriefEvaluation.ts');

function digest(value) {
  return `sha256:${crypto.createHash('sha256').update(evaluation.canonicalEvaluationJson(value), 'utf8').digest('hex')}`;
}

function parseArgs(argv) {
  const outputIndex = argv.indexOf('--out');
  return { output: outputIndex >= 0 ? argv[outputIndex + 1] : undefined };
}

function buildReport() {
  const fixture = evaluation.createEpistemeBriefEvaluationFixture();
  const draft = evaluation.evaluateEpistemeBriefFixture(fixture);
  const reportWithoutDigest = {
    ...draft,
    fixtureDigest: digest({
      fixtureVersion: fixture.fixtureVersion,
      asOf: fixture.asOf,
      options: fixture.options,
      candidates: fixture.candidates,
    }),
    profileDigests: fixture.profiles.map(({ label, profile }) => ({ label, digest: digest(profile) })),
    briefDigests: draft.profiles.map(({ label, brief }) => ({ label, digest: digest(brief) })),
    digestAlgorithm: 'sha256',
    canonicalization: 'stable-episteme-json-v1',
  };
  return {
    ...reportWithoutDigest,
    reportDigest: digest(reportWithoutDigest),
  };
}

const { output } = parseArgs(process.argv.slice(2));
const report = buildReport();
const serialized = `${JSON.stringify(report, null, 2)}\n`;
if (output) {
  const target = path.resolve(process.cwd(), output);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, serialized);
}
process.stdout.write(serialized);
