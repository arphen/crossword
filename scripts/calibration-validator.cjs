/* Fixed host bridge for the shared TypeScript calibration trust boundary. */
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

try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  if (input.operation !== 'validate') throw new Error('Unsupported operation');
  const calibration = require('../packages/domain/src/calibration.ts');
  if (!calibration.validateCalibrationSession(input.session)) {
    throw new Error('Calibration session is invalid');
  }
  if (!Array.isArray(input.catalogStimuli)) {
    throw new Error('Calibration stimulus catalog is invalid');
  }
  const versions = new Map();
  for (const stimulus of input.catalogStimuli) {
    if (
      !stimulus ||
      typeof stimulus.id !== 'string' ||
      !Number.isSafeInteger(stimulus.version)
    ) {
      throw new Error('Calibration stimulus catalog is invalid');
    }
    versions.set(stimulus.id, String(stimulus.version));
  }
  for (const observation of input.session.observations) {
    for (const offered of observation.offered) {
      if (versions.get(offered.stimulusId) !== offered.stimulusVersion) {
        throw new Error('Calibration contains an unknown stimulus version');
      }
    }
  }
  process.stdout.write(JSON.stringify({ valid: true }));
} catch (error) {
  process.stderr.write(
    JSON.stringify({ error: error instanceof Error ? error.message : 'Calibration validation failed' }),
  );
  process.exitCode = 2;
}
