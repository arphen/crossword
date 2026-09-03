# Forbidden-content scan

Status: skeleton (backlog PR 3). Not wired into CI yet.

## What it does

`scripts/scan-forbidden-content.mjs` scans the **deployable graph** — `apps/`,
`packages/`, and `apps/web/dist/` when present — for strings that must never
ship in a public artifact: NYT hosts and syndication paths, XWord Info links,
local inference servers (`ollama`), the loopback inference port, and legacy
provider routes. Patterns live in `scripts/forbidden-content.json` so the list
grows without code edits.

## What it does not scan

`src/crossword` — the private Flask/NYT continuity bridge — is explicitly
exempt: it is a local-only household surface and is never part of a release
artifact (docs/plans/00 §Baseline decisions).

## Exemptions policy

Every exemption in the JSON config carries `reason` and `until`. An exemption
is a tracked debt, not a permission:

| Path | Patterns | Reason | Until |
| --- | --- | --- | --- |
| `apps/web/src/nytApi.ts` | `legacy-provider-route` | Continuity bridge loading during migration | M4.1 release allowlist |
| `apps/web/src/nytApi.test.ts` | `legacy-provider-route` | Tests for the continuity loader; removed with nytApi.ts | M4.1 release allowlist |
| `apps/web/vite.config.ts` | `legacy-provider-route` | Dev-server proxy to the local Flask bridge | M4.1 release allowlist |
| `apps/web/dist` | `legacy-provider-route` | Development bundle still embeds the continuity loader | M4.1 release allowlist |
| `apps/web/e2e/` | `legacy-provider-route` | Negative network assertions cite the banned route to prove absence | M4.1 release allowlist (specs never ship) |

Note: `nyt-syndication` matches endpoint forms (`syndication/`, `nytsyn`), not
the bare English word SYNDICATION — legitimate lexicon entries must not trip
the gate.

Removing exemptions is part of the M4.1 release checklist; release candidates
are re-scanned without them.

## Usage

```bash
node scripts/scan-forbidden-content.mjs            # exit 1 on violations
npm run scan:content                               # same via package script
node scripts/scan-forbidden-content.mjs --report reports/content-scan.json
```

Output marks each hit `VIOLATION` (fails the run) or `exempt` (tracked debt),
followed by a scanned-file summary. The ADR 0002 verification gate
(`grep -ri ollama apps packages`) is subsumed by the `local-inference-server`
pattern here.
