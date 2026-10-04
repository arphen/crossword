# ADR 0003: Build on React, Flask, Ollama, and the native constructor

Status: accepted direction, 25 September 2026, by explicit owner instruction. Implementation is planned, not yet delivered.

## Context

The owner has withdrawn the frontend-only requirement and instructed us to build the best working experience around the current implementation, with later ports informed by a working product. The product already runs React through Flask. The separate construction lab already invokes native Rust `xfill` and local Ollama. Requiring a browser model conversion or a WASM constructor before proving puzzle quality adds work without serving the present goal.

## Decision

1. Extend the active `apps/react` application and existing Flask backend. Do not restore `apps/web` or require a static-only deployment for this release.
2. Run model inference through Ollama on the application host. Use the native `xfill` engine as the initial full-size constructor. Benchmark exact model artifacts, including Qwen and Gemma; faster generation is expected to help, but actual speed remains measured evidence.
3. Extract the generator lab's reusable native/Ollama adapters into a Node-only generator package and versioned job runner. The lab and product use the same adapters. Vite middleware remains a development surface, not the deployed job server.
4. Flask owns the product API, access boundary, and durable SQLite records. A separately managed Python job worker claims durable jobs and invokes the product's Node runner, which imports the shared TypeScript domain/application code and versioned generator packages. It emits schema-validated JSON Lines over stdio. Do not make Flask requests wait synchronously for a full puzzle or duplicate the TypeScript knowledge reducers in Python.
5. Keep immediate solving and a durable outbox in the browser. SQLite on the application host is authoritative for accepted event journals, profiles, jobs, and prepared puzzles. IndexedDB holds cached puzzles, local checkpoints, and unsent events. Reconnect is explicit and idempotent.
6. First release is a loopback local application. Remote hosting or LAN access is a later deployment mode with authentication, transport security, and profile isolation; it must not inherit permissive legacy Socket.IO settings. The browser never connects directly to Ollama or supplies arbitrary runtime URLs/commands.
7. Preserve pure domain values, versioned messages, content provenance, exact model/engine receipts, immutable started puzzles, and exportability. These are the useful portability seams. Browser WebLLM and alternative fill engines may remain available for later experiments; they are not release gates or default fallbacks.
8. Keep private legacy-provider loading separated from original generation. Building on the existing application does not authorize redistributing provider content or using its puzzle corpus as training/evaluation data.

## Supersession

- Supersedes ADR 0002's browser-only/no-Ollama decision in full.
- Supersedes ADR 0001's static-only deployment and new-`apps/web` requirement. Its UI-independent domain and immutable puzzle principles remain applicable.
- Supersedes browser-only, backend-free, TypeScript-first full-size fill, and static-workspace-first execution instructions in the older plans. The revised [personal crossword plan](../plans/06_PERSONAL_EPISTEME.md) is the active implementation specification.

No further owner confirmation is required to plan or implement this runtime direction. Separate product/editorial proposals and release readiness still receive the review described in the implementation plan.

## Consequences

The application needs a managed local backend, worker process, Ollama installation/model, and native constructor artifact. Setup must diagnose these dependencies clearly. A prepared puzzle remains playable without inference, and queued jobs can continue after the browser closes while the application services remain alive. Machine sleep and terminated services still interrupt work; persisted stage checkpoints support recovery.

Personal data stays on the application host by default. When a phone connects to that host, the host is a different device: product language must describe that accurately. A single approved model at a time and bounded CPU/GPU concurrency are the initial scheduling policy.

## Acceptance evidence

- Existing React solver behavior survives the integration.
- One original 15×15 is generated end-to-end with an exact native engine/model receipt.
- Model unavailable, worker restart, duplicate request, browser disconnect, cancel, and stale profile revision paths preserve data and never publish incomplete puzzles.
- A clean setup uses versioned generator/runtime artifacts, not a mandatory sibling checkout or Vite development server.
- No profile data is sent to a hosted inference service by the default path.
- Browser-only and native-only adapters have separate imports/build targets; portability does not leak Node APIs into the UI bundle.
