# Generator repository boundary

Crossword remains one browser-delivered product. Generation is developed in the separate local repository `../crossword-generator`; it is not a network service and does not depend on React or Vue.

## Ownership

- Generator repo: `@crossword/construction` (deterministic fill and protocol), `@crossword/model-runtime` (WebLLM broker, adapter, engine worker and protocol), and `@crossword/generator` (construction orchestration and browser worker clients/entry points).
- Crossword repo: active Vue UI, puzzle loading/parsing, framework-independent solve state and persistence. The application export remains a compatibility shim into generator packages. React UI, worker shims and product-specific model configuration are preserved on `backup/react-generator-integration-ed519f5`.
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

Copy the three generated archives from its `artifacts/` directory into `vendor/generator/` here. Update file dependency paths/version references in the root and `packages/application` manifests when releasing a new version, then run `npm install --ignore-scripts` to regenerate the lockfile. Do not reuse a release version for changed package content.

Validate this repo:

```sh
npm test -- --runInBand
make build
make legacy-smoke
make core-test
```

`npm run test:generator` and `npm run test:mutation` are opt-in extras that run in the sibling repository and require `../crossword-generator` to exist; the continuous local checks above never depend on it. Mutation configuration and tooling are owned by the generator repository, not this frontend.

The generator packages export TypeScript source for bundling, matching the previous workspace contract. A consumer needs a TypeScript-aware browser bundler; they are not direct unbundled Node or Vue 2 script-tag imports. The backup React branch demonstrates Vite integration, including `worker.format: 'es'` for the nested WebLLM worker.

## Vue restoration

Vue is now the sole active frontend and `make run` serves it on port 5001. The Vue JS/CSS/templates match the pre-React `origin/rebuild` baseline (`8523664`); the stash is untouched. React and its working package integration are preserved on `backup/react-generator-integration-ed519f5`. The generator repository, vendored archives and application compatibility exports remain here, but generation is not yet wired into the Vue UI. That requires a separate bundling adapter. Existing tests validate covered behavior, not complete UI correctness or real WebGPU generation.
