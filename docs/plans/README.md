# Crossword implementation planning index

Status: updated 26 September 2026. The local Ollama/native runtime direction is accepted by owner instruction; the detailed implementation plan remains available for review.

## Active specification

Read [The personal crossword: implementation plan](06_PERSONAL_EPISTEME.md) first. It defines the unusual visual/symbolic opening, initial episteme calibration, weekday difficulty, learned clue grammar, crossing scaffolding, gameplay evidence, evolving profiles, reflection, learning, runtime and execution backlog.

[ADR 0003: local Ollama and native construction](../adr/0003-local-ollama-native-runtime.md) supersedes the previous frontend-only implementation requirement. Build on the existing React/Flask application and the native/Ollama construction lab. Keep portable interfaces; establish an excellent working product before requiring a browser port.

## Current decisions

- Extend `apps/react` and Flask rather than restoring a new static `apps/web` workspace.
- Use Ollama and native `xfill` on the application host, through shared versioned adapters and durable jobs.
- Keep SQLite authoritative for accepted journals, profiles, jobs and prepared puzzles; use IndexedDB for responsive solving, cached puzzles and an outbox.
- Start softly with objects, colors, shapes, numerals and other signs. Interpret choices as tentative associative directions, not fixed personality labels.
- Offer selectable Monday–Saturday editorial recipes; Sunday is a larger midweek-level format after its size/mechanic gate. Wednesday and a genuine Thursday are early quality proof points.
- Preserve reliable clue grammar: number/tense agreement, spoken quotations, nonverbal brackets, wordplay signals, abbreviation/language cues, cross-references and coherent special mechanics.
- Keep user memory evidence-backed, open-ended, inspectable, editable, exportable and resettable.
- Keep source eligibility, accurate grounding, immutable started puzzles, fair crossings and independent validators authoritative.
- Preserve current solving behavior and original-content boundaries. Private provider routes/data are not a source for released puzzles or benchmark fixtures.

## Execution entry point

The first onboarding slice is implemented under `/future`: illustrated signifier choices, companion branching, word traces, explicit weekday difficulty, editable initial associations, optional local Ollama expansion, and local/SQLite persistence. See [implementation and verification notes](../future-onboarding.md). It reuses the daily solver; personalized grid generation and play-event learning remain subsequent work.

Use sections 21–23 of the active plan: 22 bounded work packages, dependencies, acceptance evidence and review decisions. Start with evidence contracts, the authored calibration slice in the current UI, canonical storage/outbox and native runtime integration. Then prove excellent full-size Monday, Wednesday and Thursday experiences before expanding breadth.

## Historical/contextual plans

The following documents retain useful reasoning and earlier audits. Browser-only, backend-free, static-workspace-first and obsolete sequencing instructions in them are superseded by ADR 0003 and the active specification.

1. [Legacy audit](00_LEGACY_AUDIT.md).
2. [Earlier product experience](01_PRODUCT_EXPERIENCE.md).
3. [Earlier puzzle intelligence](02_PUZZLE_INTELLIGENCE.md).
4. [Earlier architecture migration](03_ARCHITECTURE_MIGRATION.md).
5. [Earlier quality/delivery plan](04_QUALITY_DELIVERY.md).
6. [Earlier execution backlog](05_EXECUTION_BACKLOG.md).
7. [Earlier implementation prompts](LUNA_PROMPTS.md).

No agent should re-request approval for the already authorized move to Ollama/native construction. Detailed editorial defaults are proposals to test and review; claims of runtime readiness, puzzle quality and learning require the evidence in the active plan.
