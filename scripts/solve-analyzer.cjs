/* Fixed host bridge to the shared deterministic solve-session analyzer. */
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
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

// Domain source uses ESM-style `.js` specifiers that resolve to `.ts` files
// in the workspace build. Mirror that resolution only inside this bridge.
const resolveFilename = Module._resolveFilename;
const domainSourceRoot = path.resolve(__dirname, '../packages/domain/src') + path.sep;
Module._resolveFilename = function (request, parent, isMain, options) {
  try {
    return resolveFilename.call(this, request, parent, isMain, options);
  } catch (error) {
    if (
      typeof request === 'string' &&
      request.endsWith('.js') &&
      parent?.filename?.startsWith(domainSourceRoot)
    ) {
      return resolveFilename.call(
        this,
        `${request.slice(0, -3)}.ts`,
        parent,
        isMain,
        options,
      );
    }
    throw error;
  }
};

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const analyzer = require('../packages/domain/src/solveV2.ts');

async function main() {
  try {
    let analysis;
    if (input.operation === 'analyze') {
      analysis = analyzer.analyzeSessionV2(input.session, input.puzzle);
    } else if (input.operation === 'analyze-v2-document') {
      analysis = await analyzer.analyzeSessionV2Document(input.session, input.puzzle);
    } else if (input.operation === 'validate-v2-document') {
      // Load the V2 schema validator only for this explicit operation. The V1
      // bridge remains isolated from PuzzleDocumentV2 module resolution.
      const puzzleV2 = require('../packages/domain/src/puzzleV2.ts');
      const validation = await puzzleV2.validatePuzzleDocumentV2(input.puzzle);
      if (!validation.valid) {
        const issue = validation.issues[0];
        throw new Error(
          issue
            ? `Invalid PuzzleDocumentV2 (${issue.code}${issue.path ? ` at ${issue.path}` : ''}): ${issue.message}`
            : 'Invalid PuzzleDocumentV2',
        );
      }
      process.stdout.write(JSON.stringify({
        validation: {
          puzzleId: input.puzzle.id,
          puzzleHash: input.puzzle.integrity.value,
        },
      }));
      return;
    } else if (input.operation === 'evaluate-v2-publication') {
      // This is a pure evidence-shape gate only. The gate itself always marks
      // reviewer claims unverified; this bridge accepts no verification flag
      // or host receipt and exposes no publication operation.
      const expectedKeys = ['candidate', 'operation', 'packet'];
      const inputKeys = Object.keys(input).sort();
      if (
        inputKeys.length !== expectedKeys.length ||
        inputKeys.some((key, index) => key !== expectedKeys[index])
      ) {
        throw new Error('Publication gate accepts only candidate and packet inputs');
      }
      const publicationV2 = require('../packages/domain/src/publicationV2.ts');
      const evaluation = await publicationV2.evaluatePuzzleV2PublicationGate(
        input.candidate,
        input.packet,
      );
      process.stdout.write(JSON.stringify({ evaluation }));
      return;
    } else {
      throw new Error('Unsupported operation');
    }
    process.stdout.write(JSON.stringify({ analysis }));
  } catch (error) {
    process.stderr.write(JSON.stringify({ error: error instanceof Error ? error.message : 'Analyzer failed' }));
    process.exitCode = 2;
  }
}

void main();
