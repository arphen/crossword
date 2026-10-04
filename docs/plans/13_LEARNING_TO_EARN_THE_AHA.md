# Learning to earn the “aha”

Design proposal, 27 September 2026. Extends [editorial intelligence](12_EDITORIAL_INTELLIGENCE_AND_LLMs.md) and the [active specification](06_PERSONAL_EPISTEME.md), especially its candidate evaluation, crossing support, and repair loop. This is a plan for improving private experimental puzzles, not a claim that an evaluator has been implemented or validated.

## The objective: an interpretation the player can reach

Two ideas guide this proposal:

> It can let someone encounter a possibility in their own language that they had not previously been able to reach.

> Before the answer, several possibilities can circulate. Afterward, the player should feel that the wording earns this particular resolution.

Generate several candidates and learn to choose among them: yes. But evaluate the relationship between clue, intended sense, player, and available crossings. An isolated answer–clue pair cannot tell us the whole experience. The same clue can be a delightful switch for one player, straightforward for another, and inaccessible to a third.

The desired pattern is an initially reasonable reading, enough resistance to invite reconsideration, a reachable alternative, and a satisfying explanation that the wording itself supports. This is one valuable kind of clue; a whole puzzle also needs direct recognition, factual discovery, and breathing room.

## Jev fits the proposed evaluation role

The user's reference is TypeSafe AI's Jev, not JEPA. Jev evaluates supplied state through typed questions and returns choices, scores, and probabilities. Its documented interface supports several questions evaluated separately against the same state. That is directly relevant to evaluating candidates on several editorial dimensions. Its usefulness on subtle crossword judgments remains an empirical question. [Official introduction](https://docs.typesafe.ai/introduction).

For the immediate problem, distinguish three jobs:

| Job | Useful model form | What its output means |
| --- | --- | --- |
| Detect recognizable defects | A classifier with several defect labels | Evidence of an agreement error, unsupported relation, awkward phrase, giveaway, or another defined problem |
| Choose between viable alternatives | A pairwise or listwise ranker | A preference among candidates under an explicit editorial brief |
| Estimate access during play | A model conditioned on clue, language, familiarity, and actual letter positions | An uncertain estimate of retrieval under those conditions |

A cross-encoder reads the relevant texts together and can be adapted to scoring or classification. It is a plausible candidate for the first two jobs, with crossword-specific supervision. A general retrieval ranker measures relevance to its training task; it must not be mistaken for a ready-made judge of wit or fairness. [Official cross-encoder training documentation](https://sbert.net/examples/cross_encoder/training/rerankers/README.html).

My proposed order is to compare Jev-style typed evaluation with a prompted LLM judge, then train a smaller local critic if the collected judgments support it, then adapt the generator if useful candidates remain scarce. The first custom model should probably learn what makes a candidate worth keeping. Jev is a possible external benchmark or optional evaluator; adopting its design does not require replacing the project's local runtime or sending player histories to a hosted service.

## Concrete Jev questions and what they would establish

TypeSafe recommends narrow judgments that software composes, and distinguishes unordered Choice options, ordered Score levels, and a Noul probability for a yes/no proposition. The following are proposed crossword uses, not evaluated model capabilities. [Primitive reference](https://docs.typesafe.ai/primitives).

| Editorial question | Primitive | Proposed interpretation |
| --- | --- | --- |
| Does the clue's grammatical number agree with the intended answer sense? | Noul | A focused defect signal, checked mechanically too where possible |
| Does the supplied factual evidence support the relation asserted in this clue? | Noul | Support within the supplied evidence, not independent fact verification |
| How directly does the wording support the intended reading after the answer is known? | Score | Ordered levels: unsupported; requires an unstated premise; defensible but loose; precise and natural |
| Which of these two clues better fits the stated editorial role? | Choice | A, B, equally suitable, neither suitable, or insufficient information |
| What should happen to this candidate? | Application decision | Keep, investigate, rewrite, or replace, based on several judgments and measured error rates |

The last row intentionally belongs to application logic. A high novelty score should not erase a confirmed factual error. A doubtful precision judgment should lead to examination rather than automatic rejection of an unusual but potentially excellent clue. Difficult, surprising material is exactly where an overcautious critic could flatten the product.

The post-reveal Score is a narrow approximation to one part of retrospective necessity. It does not establish that the player could arrive at the answer or would enjoy the route. Those questions need the separate evaluation views below.

TypeSafe's confidence field summarizes the concentration of the returned probability distribution. It is not an independent certificate of correctness. A Score is a position on described levels; it is not a probability that a player will enjoy a clue. Noul's probability concerns its particular proposition. On held-out crossword examples, check whether predicted probabilities agree with adjudicated outcomes, and report failures by clue family and audience rather than relying only on an overall average. [Confidence documentation](https://docs.typesafe.ai/confidence), [Score semantics](https://docs.typesafe.ai/primitives/score).

Three implications follow. Typed outputs prevent invalid output shapes, but a permitted label can still be wrong. Multiple judgments over one clue can have correlated errors, so multiplying their probabilities would not establish a probability that the puzzle is good. A sharp preference between two poor candidates does not establish that either deserves selection; preserve a “neither” outcome.

Jev can compare supplied answer candidates, but that is different from generating an answer without options. A multiple-choice probe gives the evaluator recognition help. Use a language model, a retrieval-based solver, or a person for the open-ended solving view; record recognition and generation as different tests.

Most importantly, every question in one Jev request sees the same state. Do not combine an answer-hidden solving probe and an answer-aware fit assessment in that request and merely instruct one question to ignore the target. Construct separate inputs. Dependent judgments also need a later request with the earlier result explicitly supplied. [Question isolation and composition](https://docs.typesafe.ai/primitives).

## Keep correctness, access, and delight distinguishable

“Rate this clue from 1 to 10” blends incompatible judgments. A valid but plain clue, a clever but strained clue, and a fair clue for the wrong audience should not receive interchangeable records.

Retain judgments about wording and sense correctness, naturalness, initial interpretation, access with crossings, precision after revelation, freshness, and fit with the intended audience. Each uncertain judgment should be allowed to remain uncertain. A classifier may detect some semantic defects; its approval is not proof of correctness.

Confirmed defects should not be compensated for by novelty. Once candidates meet the basic standards, compare their appeal and suitability. A conventional clue can win when its surrounding region needs an easy opening. The same clue can lose when the slot is intended to deliver the puzzle's major reinterpretation.

An aggregate selection score may eventually be convenient. Preserve the underlying judgments so the system can tell whether a low score calls for different wording, more accessible crossings, another intended sense, or different fill.

## Three evaluation views, with different information

The central precaution is to stop knowledge of the answer from contaminating every assessment. These are separate evaluation calls or human review views, not a requirement for three concurrently running agents.

**Before resolution: try to solve.** Provide the clue, answer length, audience assumptions, and a selected crossing pattern. Hide the target, intended sense, writer's explanation, and any theme information the player would not yet possess. Ask for plausible answers and a short account of the readings the wording permits. An answer-aware component can compare the returned candidates afterward; the solving view must not receive them in advance.

**After revelation: judge the fit.** In a fresh context, provide clue and answer, initially without the writer's explanation. Ask whether the relationship follows naturally, which words do the work, and what assumptions are needed. When factual support is relevant, check it separately. Then inspect the proposed explanation and ask whether it clarifies the clue or introduces a missing premise. A prepared long explanation must not rescue wording that does not support the relation.

**As a challenger: look for competing answers.** Search for other legitimate answers of the same length that fit the available letters and grammar. A candidate list is incomplete, so failure to find a competitor is evidence rather than a uniqueness proof. Multiple answers before crossings are normal. Persistent ambiguity at the stage where the player is expected to resolve the entry is the concern.

For the earlier “Current carrier?” → RIVERBED example, WATERWAY is also eight letters and is worth examining as a competitor. The issue is not that this proves the clue invalid. It demonstrates why an answer-aware explanation alone misses a relevant comparison. In a particular grid, crossings may distinguish them; the editor must still decide whether the selected relationship is exact and satisfying.

LLM solving probes are diagnostics, not simulated people with established psychological validity. A model may know far more trivia than the audience, recall a familiar clue, or miss an easy letter manipulation. Its performance needs comparison with actual play.

## Make retrospective necessity an editorial judgment

“Necessity” does not mean the clue alone has a mathematically unique solution. Crossword clues routinely require crossings. It means the resolved interpretation feels earned by the clue under the puzzle's conventions.

The assessment should distinguish four outcomes:

- Immediate recognition: the clue works, with little reinterpretation.
- Earned reinterpretation: another reading becomes available and accounts cleanly for the wording.
- Answer supplied by crossings: the entry is completed, but the clue may or may not have become intelligible.
- Post-hoc rationalization: the answer can be associated with the clue only after adding a charitable story.

The second is the special experience we want to cultivate. The first and third have legitimate places in a puzzle. The fourth is a candidate for repair.

A useful review question is “Once you know the answer, does the clue explain itself?” Another is “What changed in your reading?” A person need not articulate an elaborate mechanism; a short observation can be more revealing than a numeric cleverness score. Success plus delay does not establish an “aha.”

## Evaluate the usefulness of actual crossings

Test promising clues under several masks that could arise in their proposed grids: initially blank, after an accessible neighboring answer, and after further plausible progress. Record positions, not merely the percentage of letters revealed. A vowel in one position and a distinguishing consonant in another can have very different effects.

The crossing route must itself be reachable. Two unfamiliar entries cannot justify each other by assuming the other has already been solved. Nor should every supposed foothold depend on the same uncertain bit of specialist knowledge. A physics enthusiast's access to one theorist does not establish access to every physicist in the region.

For intended reinterpretation clues, look for improvement in access before the answer is almost entirely supplied. That is a hypothesis about a good experience, not a universal cutoff. Some unknown names are appropriately learned through crossings; classify that as a different experience.

Do not reward obscurity simply because it creates a large numerical improvement after revelation. Any arbitrary answer becomes “obvious” when disclosed. After-answer fit and before-answer reachability need independent support.

## Let editorial search influence construction

The proposed construction loop has five parts:

1. Propose a few theme or anchor packages containing an answer, intended sense, plausible clue approaches, and the role it would play for this audience.
2. Screen obvious weaknesses, then ask the existing solver for a bounded variety of fills around promising packages. Ordinary fill continues to draw from the broad lexicon.
3. Generate and compare clue variants for the actual entries. Spend more effort on marquee answers, uncertain clues, and regions with weak support.
4. Evaluate whole-puzzle composition and plausible routes through crossings. Repair wording first where appropriate; change a sense or refill a region when the answer cannot support a worthwhile clue. Recheck the complete puzzle after changes.
5. Select and freeze a complete puzzle before play. Later observations improve future candidates.

This is editorial search around the constraint solver. It requires no LLM request inside backtracking. It also avoids assuming every structurally valid fill can be made excellent through clue writing alone.

Individual winners do not necessarily form a good puzzle together. Too many puns, several clues relying on the same ambiguity, or a cluster of inaccessible names can make excellent individual entries exhausting as a set. Whole-puzzle selection must account for rhythm, redundancy, and the placement of accessible entries.

## Generate diversity, not merely volume

For important entries, request distinct approaches: direct definition, grounded fact, conversational equivalent, alternate sense, or a particular kind of wordplay when supported. Several stylistic rewrites of one weak idea are not meaningful candidate diversity.

Use inexpensive structural checks first, a fast critic for broad screening, and richer evaluation on a few finalists. Cache judgments that remain applicable, but recompute access estimates when clues, audience assumptions, or crossing patterns change. This is a way to concentrate expensive language-model work, not a promise of specific runtime gains.

Larger candidate pools can expose a judge's blind spots: selecting the highest score may select the candidate that most exploits the evaluator. Research on reward-model overoptimization demonstrates this general proxy problem; it does not establish a crossword-specific optimum. Track whether human preference improves as the search budget increases. [Reward-model overoptimization](https://arxiv.org/abs/2210.10760).

A fast critic's additional value is deciding where further work could matter. Spend a slower evaluation on uncertainty about a promising candidate's precision; generate more alternatives when every candidate is weak; stop when the remaining uncertainty cannot plausibly change selection. Check samples of confident approvals and rejections too, since confidence itself can be mistaken. This makes the critic a way to allocate editorial attention as well as a way to rank outputs.

## The data that would make a custom model valuable

Collect comparisons that are difficult for a generic language model: a sound pun versus a strained one, a natural phrase versus a fluent invention, correct grammatical agreement versus a near miss, precise factual attribution versus a plausible error, and two valid clues with different suitability for a player.

Same-answer comparisons help isolate clue quality from answer popularity. Preserve both alternatives, the editorial context, the preference, defect labels, and ties or “neither.” Follow the label sources separately: human editorial review, actual play, model proposals, and mechanical checks provide different kinds of evidence. Synthetic corruptions can supply candidate mistakes; review them because an edit intended to break a clue may leave it valid.

Pairwise comparisons are a proposed labeling strategy, not immunity to bias. Randomize or reverse presentation order, hide generator identity, and withhold persuasive writer explanations. LLM judges have documented position, verbosity, and self-enhancement biases; multiple judges can share them. [LLM-as-judge study](https://arxiv.org/abs/2306.05685).

Hold out answer families, near-duplicate clue templates, and theme families when evaluating generalization. Otherwise a learned critic can appear perceptive by recognizing familiar material. Keep an untouched human-reviewed set and examine held-out domains and language backgrounds separately. Agreement with the model that created the training labels is insufficient validation.

An existing language model can later be adapted to produce better candidates or to serve as a critic. LoRA offers a way to train relatively few added parameters; preference training such as DPO can use preferred/rejected outputs. Neither method supplies the editorial target or guarantees transfer to novel wordplay. Training a foundation model from scratch is not justified by the current need. [LoRA](https://arxiv.org/abs/2106.09685), [DPO](https://arxiv.org/abs/2305.18290).

## Learn personal surprise without claiming to read the mind

Treat a predicted first reading as a hypothesis. A player who knows physics might read SPIN technically, but context, mood, and clue wording can override that expectation. A successful solve does not identify their original interpretation.

Occasional optional feedback can distinguish “I knew it immediately,” “I saw another meaning,” “the crossings supplied it,” and “I still don't see why.” Use such responses to refine candidate selection without turning play into an interview. A general editorial model with a modest player-specific context is a better initial proposal than separately fine-tuning a model on each player's sparse history.

To test whether a clue helps someone reach a new possibility, compare results under different clue routes with real players. A later, differently worded encounter may provide evidence that a new sense has become available. One delighted reaction is valuable as entertainment evidence, but it does not prove a durable change in the person's conceptual repertoire.

## A small experiment before a large training effort

Start with a manageable editorial study: roughly 50 varied answers with four genuinely different clue proposals each, including ordinary clues, polysemy, names, and long established phrases. These numbers define a pilot, not an adequate training corpus or a statistical guarantee.

Compare four selection methods on the same candidate pools: the generator's first proposal, a prompted LLM's answer-aware overall rating, Jev's decomposed typed judgments, and the separated solve/fit/challenge approach using the same typed judgments plus answer-hidden probes. This separates the value of a different judge from the value of giving evaluation a better structure. Keep the generation and evaluation budgets visible. For actual solving, assign only one variant of a given answer to a participant so earlier exposure does not reveal the later answer. Editorial comparisons can be performed separately after disclosure. If Jev access is unavailable, run the other arms and leave its result unknown.

Assess soundness, supported retrieval, post-reveal fit, enjoyment, and cost. Then place promising selections into a few full grids and check that local improvements survive whole-puzzle play. An isolated-clue result cannot establish crossing fairness or a satisfying solving rhythm.

If sound candidates are present but poorly selected, invest in the critic. If nearly every proposal is weak, improve generation, grounding, or answer selection. If individual clues are good but the solve stalls, improve construction and support. This distinction tells us which custom model, if any, would address the real bottleneck.

The eventual asset is a growing record of which linguistic possibilities were reachable, precise, and rewarding under particular conditions. A specialized evaluator can learn from that record. The first task is to make the distinction between a clever explanation and an earned discovery observable enough to teach.
