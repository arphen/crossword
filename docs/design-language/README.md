# Afterglow: the design language, made portable

This folder distils the Crossword app's styling philosophy into material you can drop into other projects, so that even a less capable AI agent can apply it coherently.

| File | Use it when |
| --- | --- |
| [`DESIGN_LANGUAGE.md`](DESIGN_LANGUAGE.md) | The full guide (about 29k tokens): the philosophy, the psychoanalytic reasoning, the colour system, motion, voice, 31 lessons from the commit history, and a step-by-step protocol for applying it. Self-contained, with all code inlined. |
| [`AGENT_CORE.md`](AGENT_CORE.md) | The agent has a small context window. A condensed extract (about 9k tokens): the 32 rules, the numbers, the protocol, the checklist. It is generated from the full guide and keeps its section numbers. |
| [`starter/`](starter) | The agent can copy files. Tested code: `afterglow.css`, `view-settings.js`, `view-panel.js`, `territory.js`, `fit-contour.mjs`, and `demo.html` that assembles them. |

## Dropping it into another project

1. Copy this folder (or just `DESIGN_LANGUAGE.md`, plus `starter/` if the agent can copy files) into the target repo.
2. Tell the agent: *"Read `docs/design-language/AGENT_CORE.md` (or `DESIGN_LANGUAGE.md`) completely, then do §16.1. Do not write code until you have shown me the filled-in Content Identity Brief."*
3. Review the brief, the keeps list, and the baseline screenshots before letting it implement slice S1.

The guide's §16.6 lists what to say when the agent stalls or goes off the rails.

## Try the starter

```bash
cd docs/design-language/starter
python3 -m http.server 8000      # ES modules do not load from file://
# open http://localhost:8000/demo.html   (try ?theme=light  ?luma=dim  ?vibrance=soft  ?open=1)
```

## The four scales

The View panel in the app has three reader-facing tiers: **Mini** (comfort), **Micro** (reading aids), **Nano** (fine cues). The guide adds **Macro**, the composition the designer owns (ground, figure, floating instruments, ambient light), so that every adjustment has a scale to live on. See §5 of the guide.

## Maintenance

`DESIGN_LANGUAGE.md` inlines the files in `starter/`. If you change a starter file, update the inlined copy in §14 as well and regenerate `AGENT_CORE.md`'s excerpts so the three stay in step.

The psychoanalytic reading in §4 is an interpretive design lens, not a claim that an interface measures the unconscious. Every rule in the guide is also stated in plain terms.
