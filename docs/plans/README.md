# Crossword implementation planning index

Status: updated 1 October 2026. The local Ollama/native runtime direction is accepted, and private profile-seeded play now works end to end. The next run improves clue/theme quality and generation time; that queue is [note 16](16_CLUE_QUALITY_RECOVERY.md).

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
- Keep started puzzle grids immutable and structurally valid. Source admission, factual grounding and editorial receipts govern later sharing/publication; they do not block private local experimental play.
- Preserve current solving behavior and original-content boundaries. Private provider routes/data are not a source for released puzzles or benchmark fixtures.

## Execution entry point

The `/future` path begins without requesting a daily crossword. The player
chooses a weekday and explicitly makes a local puzzle from the saved profile;
Ollama writes theme answers and clues, native xfill makes the 15×15 grid, and
the existing solver records the play. A real Gemma 4 26B browser run took 58
seconds and returned a 78-entry Wednesday puzzle. The private board, typed
letter and solve journal restored after reload. The six Playwright checks pass
using an isolated synthetic creation fixture and cover the complete solve and
reflection flow. `/` keeps its daily feed. See
[implementation notes](../future-onboarding.md) and the
[current Luna handoff](LUNA_PROMPTS.md).

The next implementation work improves actual theme/clue play and shortens the
generation wait. The separate admitted-content worker, V2 candidate storage,
diagnostics and publication packet belong to later sharing work; they are not
requirements for making or playing a private puzzle.

## Next-slice plan (clue quality)

[Clue quality recovery](16_CLUE_QUALITY_RECOVERY.md) is the execution queue for
the complaint that clues are still trivial: five named defects with the code that
produces each, the model tiers reachable on a 16 GB host, and slices `Q01`–`Q08`
in backlog-table form. It amends `E05`, `E06`, `E10` and `E18` rather than
replacing them, and it is the operational half of
[note 15](15_THE_SELF_CRITIQUE_OF_THE_CONCEPT.md) §4–§7.

## Conceptual correspondence

The following notes develop the product's underlying ideas from the 27 September conversation. They are conceptual arguments and editorial hypotheses, not a new execution backlog or a replacement for the active specification. Read them in order, or start with the subject closest to the current question. Note 13 is the critique of notes 07–12 rather than another note in the sequence; notes 07–12 each carry a closing dialectical postscript recording what that critique changed.

1. [Expertise as a way into the world](07_EXPERTISE_AND_THE_GENERAL_CROSSWORD.md): the studium generale, personal footholds, and how crossings carry knowledge beyond its home discipline.
2. [An international crossword needs a situated audience](08_AN_INTERNATIONAL_AUDIENCE.md): cultural specificity, language competence, and fairness across different starting points.
3. [Association, constraint, and the retrospective “of course”](09_SIGNIFICATION_AND_THE_AHA.md): the signifying chain, Lacanian and Hegelian analogies, clue grammar, and long-answer recognition.
4. [The episteme as an evolving relation](10_EPISTEME_AS_AN_EVOLVING_RELATION.md): calibration, contextual knowledge, personal resonance, and the feedback loop created by adaptation.
5. [Domain lexicons: acquiring material with ways into it](11_DOMAIN_LEXICONS_AND_SOURCES.md): what additional lists should contain, concrete source options, and why names, facts, associations, and fill are different resources.
6. [Editorial intelligence beyond a valid grid](12_EDITORIAL_INTELLIGENCE_AND_LLMs.md): what LLMs contribute, what a theme must earn, and what quality means in the actual solve.
These six documents are implementation inputs to `06_PERSONAL_EPISTEME.md`, not
separate features waiting to be ticked off. The active backlog carries their
operational consequences: E08/E09 cover expertise-aware retrieval and crossing
support; E10 and E20 cover clue meaning and convention fluency; E12/E13/E19
cover the evolving episteme and indirect preference evidence; E04/E17 cover
domain and language packs; and E05/E18/E21 cover model, editorial, weekday, and
mechanic evaluation. Their unresolved human-review and source-admission limits
remain visible in those rows. Private local play can therefore use experimental
model material, while any claim of reviewed or publishable content still needs
the evidence gates in the active plan.

## Editorial research proposals

[Learning to earn the “aha”](13_LEARNING_TO_EARN_THE_AHA.md) develops the conceptual notes into a bounded research direction: Jev-style typed evaluation, candidate generation and ranking, separate solving and answer-aware evaluation, retrospective necessity, crossing support, and a path toward a specialized critic or adapted language model. It proposes an initial comparison study rather than a new implementation mandate.

[Clue grammar, meaning, and the enjoyment of an unyielding world](14_CLUE_GRAMMAR_MEANING_AND_ENJOYMENT.md) catalogs NYT-style American clue conventions and their semantic roles, connects them to the pleasure of stable rules and earned resolution, and specifies how generation and evaluation can preserve those relationships. It distinguishes documented conventions, proposed house commitments, and psychoanalytic interpretation, including the limits of claiming a complete publisher grammar.

## Self-critique

[The self-critique of the concept](15_THE_SELF_CRITIQUE_OF_THE_CONCEPT.md) is an immanent critique of notes 07–12: where each note's own success is its limit, the seams that appear only between them, the two terms the set leaves unthought (production and the unmarked cell), and the proposed result: one realized grid as the unit of generality. It was written against 07–12 as they stand and does not assess the two research proposals above. Read it after whichever note you are working with.

## Historical/contextual plans

The following documents retain useful reasoning and earlier audits. Browser-only, backend-free, static-workspace-first and obsolete sequencing instructions in them are superseded by ADR 0003 and the active specification.

1. [Legacy audit](00_LEGACY_AUDIT.md).
2. [Earlier product experience](01_PRODUCT_EXPERIENCE.md).
3. [Earlier puzzle intelligence](02_PUZZLE_INTELLIGENCE.md).
4. [Earlier architecture migration](03_ARCHITECTURE_MIGRATION.md).
5. [Earlier quality/delivery plan](04_QUALITY_DELIVERY.md).
6. [Earlier execution backlog](05_EXECUTION_BACKLOG.md).
7. [Luna launch prompt and archived assignments](LUNA_PROMPTS.md).

No agent should re-request approval for the already authorized move to Ollama/native construction. Detailed editorial defaults are proposals to test during play; claims of runtime readiness, puzzle quality and learning require the evidence in the active plan.
