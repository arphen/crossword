# Afterglow: the design language, made portable

This folder distils the Crossword app's styling philosophy into material you can drop into other projects, so that even a less capable AI agent can apply it coherently, and **prove** it did with a Playwright suite that runs in CI.

| File or folder | Use it when |
| --- | --- |
| [`DESIGN_LANGUAGE.md`](DESIGN_LANGUAGE.md) | The full guide (large: the whole test suite is inlined at the end). The philosophy, the psychoanalytic reasoning, the colour system, motion, 37 lessons, and a step-by-step protocol for applying it. Self-contained. |
| [`AGENT_CORE.md`](AGENT_CORE.md) | The agent has a small context window. A condensed extract (about 12k tokens): the 32 rules, the numbers, the protocol, the testing contract, the checklist. Generated from the full guide; keeps its section numbers. |
| [`starter/`](starter) | Tested code to copy: `afterglow.css`, `view-settings.js`, `view-panel.js`, `territory.js`, `fit-contour.mjs`, `demo.html`; **`e2e/`** (Playwright config, helpers, design and journey specs, `JOURNEYS.md`); **`ui/audit-static.mjs`**; **`ci/`** (GitHub Actions workflows). |

## Dropping it into another project

1. Copy this folder (or `DESIGN_LANGUAGE.md` plus `starter/`) into the target repo.
2. Tell the agent: *"Read `docs/design-language/AGENT_CORE.md` (or `DESIGN_LANGUAGE.md`) completely, then do §16.1. Your acceptance test is `npm run design:check` plus a green `design-e2e` job in CI. Do not write code until you have shown me the filled-in Content Identity Brief."*
3. Review the brief, the keeps list, `JOURNEYS.md` and the baseline screenshots before letting it implement slice S1.
4. Add the script to `package.json` (§17.2) and make the `design-e2e` job a required check.

## Why the testing is built this way

A capable agent can still stop early and call the work done. So "done" is not the agent's opinion: it is `npm run design:check` exiting 0 (a static audit whose core checks stay red until the identity ramp, View settings and territory exist, then every user journey, design contract and screenshot under Playwright) **and** CI being green. Skipped tests, blind snapshot updates, "no browser tooling" and debt lists all have a named failure status (INCOMPLETE or BLOCKED). See §17.

## Try the starter

```bash
cd docs/design-language/starter
python3 -m http.server 8000      # ES modules do not load from file://
# open http://localhost:8000/demo.html   (try ?theme=light  ?luma=dim  ?vibrance=soft  ?open=1)

# the e2e suite against the demo (needs @playwright/test and a Chromium)
npx playwright install chromium
npx playwright test -c e2e/playwright.config.mjs --update-snapshots   # first run writes baselines
npx playwright test -c e2e/playwright.config.mjs                      # then compare
```

## The four scales

The View panel has three reader-facing tiers: **Mini** (comfort), **Micro** (reading aids), **Nano** (fine cues). The guide adds **Macro**, the composition the designer owns (ground, figure, floating instruments, ambient light), so every adjustment has a scale to live on. See §5.

## Maintenance

`DESIGN_LANGUAGE.md` inlines the files in `starter/`, and `AGENT_CORE.md` is extracted from it. If you change a starter file, update the inlined copy in §14 or §17.13 and regenerate the core's excerpts so they stay in step.

The psychoanalytic reading in §4 is an interpretive design lens, not a claim that an interface measures the unconscious. Every rule in the guide is also stated in plain terms.
