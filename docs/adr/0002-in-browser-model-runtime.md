# ADR 0002: In-browser model runtime only (no Ollama adapter)

Status: superseded, 25 September 2026, by [ADR 0003](0003-local-ollama-native-runtime.md), following the owner's explicit instruction to use Ollama and the current native implementation. The former decision below is historical and must not block the new runtime work.

## Context

`docs/plans/03_ARCHITECTURE_MIGRATION.md` and `docs/plans/02_PUZZLE_INTELLIGENCE.md`
mandate a local model broker running in-browser through a dedicated worker
(WebLLM/WebGPU). The M1 workspace instead grew an Ollama loopback adapter
(`packages/model-runtime/src/ollamaAdapter.ts`) and shipped
`VITE_LOCAL_MODEL_URL` (default `http://127.0.0.1:11434`) in
`apps/web/src/modelConfig.ts`. That requires a separate server process to be
installed and running, contradicts the one-URL static deployment story, and
splits the onboarding flow ("install the pinned model in-app") across two
runtimes.

The owner has decided: the product runs inference **entirely in the browser**.

## Decision

1. The only supported model runtime is in-browser inference (WebGPU via
   WebLLM) inside the dedicated model worker.
2. The Ollama adapter and all loopback-inference configuration are removed
   from the deployable graph (`apps/`, `packages/`). No HTTP inference calls
   to localhost services.
3. `packages/model-runtime` keeps the `LocalModelAdapter` port and the
   deterministic fake adapter for tests. The real WebLLM adapter is isolated
   in one module and loaded through dynamic import so the bundle stays lazy.
4. The model worker owns the engine lifecycle: install (weight download into
   browser storage), load, generate, cancel, unload. Model bytes are never
   committed to the repository; weights are fetched from the pinned model
   host at install time and cached by the runtime.
5. First-run onboarding must verify WebGPU compatibility and storage quota
   before install, per `docs/plans/03_ARCHITECTURE_MIGRATION.md` §Mandatory AI
   capability flow. Unsupported devices get an honest capability failure, not
   a fallback.
6. A future runtime (native, WASM, remote-with-consent) requires a new ADR.

## Consequences

- Product promise "private, one URL, no server" is now literally true for
  construction as well as solving.
- Device floor is a WebGPU browser; Safari/WebKit WebGPU status becomes a
  release gate to track (already required by `docs/plans/04_QUALITY_DELIVERY.md`).
- `RuntimeProbe` keeps its shape; `distribution` becomes `webllm-mlc` and
  shards/`runtimeVersion` reflect the MLC manifest.
- The specific pinned model ID and supported device/memory floor remain an
  open owner decision (plans README); a dev-default pinned MLC model ID is
  acceptable until that spike lands.

## Verification

- `grep -ri ollama apps packages` returns nothing (legacy Flask bridge in
  `src/crossword` is exempt as a private local continuity surface).
- `packages/model-runtime` and `apps/web` test suites pass with the fake
  adapter; `npm run web:build` succeeds with the dynamic import.

## References

- `docs/adr/0001-static-react-solver-boundary.md`
- `docs/plans/03_ARCHITECTURE_MIGRATION.md` — model worker boundary
- `docs/plans/02_PUZZLE_INTELLIGENCE.md` — required local-model runtime
