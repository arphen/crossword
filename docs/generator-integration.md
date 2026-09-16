# Generator repository boundary

Crossword remains one browser-delivered product. Generation is developed in the separate local repository `../crossword-generator`; it is not a network service and does not depend on React or Vue.

## Ownership

- Generator repo: `@crossword/construction` (deterministic fill and protocol), `@crossword/model-runtime` (WebLLM broker, adapter, engine worker and protocol), and `@crossword/generator` (construction orchestration and browser worker clients/entry points).
- Crossword repo: Vue and React UI, puzzle loading/parsing, solve state, persistence, and product-specific model configuration. Existing application and worker exports are compatibility shims into the generator packages.
- Source history before extraction remains in the crossword repository, including the untouched stash. Extraction source: `9c964ab917b1ba42915cd034b53d2718179ebb0d`. The new repository starts with a snapshot; it does not pretend to contain filtered historical commits.

## Reproducible integration

The frontend consumes versioned npm archives committed under `vendor/generator/`, with integrity recorded in `package-lock.json`. A clean frontend checkout can run `npm ci` without the sibling repository, a private registry, symlinks, or network access to a generator service. Normal npm dependencies still require the npm registry or cache.

In the generator repo:

```sh
npm ci
npm test
npm run build
npm run pack:packages
```

Copy the three generated archives from its `artifacts/` directory into `vendor/generator/` here. Update file dependency paths/version references in the root, `apps/web`, and `packages/application` manifests when releasing a new version, then run `npm install --ignore-scripts` to regenerate the lockfile. Do not reuse a release version for changed package content.

Validate this repo:

```sh
npm test -- --runInBand
npm run web:test
npm run web:build
make core-test
```

`npm run test:generator` and `npm run test:mutation` are opt-in extras that run in the sibling repository and require `../crossword-generator` to exist; the continuous local checks above never depend on it. Mutation configuration and tooling are owned by the generator repository, not this frontend.

The generator packages export TypeScript source for bundling, matching the previous workspace contract. A consumer needs a TypeScript-aware browser bundler (currently Vite); they are not direct unbundled Node or Vue 2 script-tag imports. Web workers remain browser modules; Vite's `worker.format: 'es'` is required for the nested WebLLM worker. The frontend retains lightweight worker entry shims so the existing bundler worker URLs remain stable.

## Vue recovery is separate

This extraction does not switch the active frontend, implement missing generation features, change `make run`, or apply the preserved stash. Vue can later consume the same framework-independent packages through a bundling adapter. Existing tests and builds validate packaging and covered behavior, not full Vue/React parity or actual WebGPU model generation.
