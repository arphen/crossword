import React, { useEffect, useState } from 'react';
import { recordAssociationPreference } from './episteme';

const FLAG_COPY = {
  'unsupported-factual-surface': 'factual surface is unverified',
  'answer-giveaway': 'answer giveaway removed',
  'answer-form-in-clue': 'answer form was removed',
  'generic-clue': 'generic clue was replaced',
  'anagram-mismatch': 'anagram needs repair',
  'reversal-mismatch': 'reversal needs repair',
  'language-answer-mismatch': 'language relation needs repair',
  'past-tense-marker-with-nonpast-shape': 'past-tense marker does not match answer shape',
  'unbalanced-quotation': 'quotation mark was normalized',
  'unbalanced-brackets': 'brackets were normalized',
  'bracket-scope': 'bracket scope was normalized',
  'question-mark-placement': 'question mark was normalized',
  'model-review-recommended': 'local challenger recommends review',
  'model-fallback-recommended': 'local challenger recommends a safer foothold',
};

const SIGNAL_COPY = {
  quote: 'quotation marks',
  brackets: 'brackets',
  'question-mark': 'question marks',
  'fill-blank': 'fill blanks',
  'abbreviation-indicator': 'abbreviation markers',
  'language-indicator': 'language labels',
};

function legacyEntryId(entry) {
  if (!entry || !Number.isFinite(Number(entry.clue_number))) return null;
  return `${Number(entry.clue_number)}${entry.direction === 'down' ? 'D' : 'A'}`;
}

function labelForFlag(flag) {
  return FLAG_COPY[flag] || flag.replaceAll('-', ' ');
}

export default function ClueQualityNotes({ provenance, entries = [], profileId }) {
  const storageKey = profileId
    ? `crossword.future.clue-flags.v1:${profileId}`
    : null;
  const [flags, setFlags] = useState(() => {
    if (!storageKey) return {};
    try {
      const value = JSON.parse(window.localStorage.getItem(storageKey) || '{}');
      return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    } catch {
      return {};
    }
  });
  const [pendingFlag, setPendingFlag] = useState('');
  const [flagError, setFlagError] = useState('');

  useEffect(() => {
    if (!storageKey) return;
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(flags));
    } catch {
      // The host episteme remains authoritative when browser storage is full.
    }
  }, [flags, storageKey]);

  const quality = provenance?.clueQuality;
  const grounding = quality?.grounding;
  const crossingSupport = provenance?.crossingSupport;
  const footholdSeedPlan = provenance?.constructionEvidence?.footholdSeedPlan;
  const modelChallenge = provenance?.semanticClueChallenge;
  const reviewedCluePack = provenance?.reviewedCluePack || quality?.reviewedCluePack;
  if (
    !quality ||
    !grounding ||
    !Array.isArray(grounding.entries) ||
    typeof quality.issueCount !== 'number'
  ) {
    return null;
  }

  const cluesById = new Map(
    entries.map((entry) => [legacyEntryId(entry), entry.clue_text]),
  );
  const flagged = grounding.entries
    .filter(
      (entry) =>
        Array.isArray(entry.riskFlags) && entry.riskFlags.length > 0,
    )
    .slice(0, 8);
  const groundedById = new Map(grounding.entries.map((entry) => [entry.id, entry]));
  const challenged =
    modelChallenge?.status === 'completed' &&
    modelChallenge.byId &&
    typeof modelChallenge.byId === 'object'
      ? Object.entries(modelChallenge.byId)
          .filter(([, recommendation]) => recommendation?.disposition !== 'keep')
          .slice(0, 8)
          .map(([id, recommendation]) => {
            const source = groundedById.get(id) || { id, riskFlags: [] };
            const challengeFlag =
              recommendation.disposition === 'fallback'
                ? 'model-fallback-recommended'
                : 'model-review-recommended';
            return {
              ...source,
              id,
              riskFlags: [
                ...(Array.isArray(source.riskFlags) ? source.riskFlags : []),
                challengeFlag,
              ],
              challenge: recommendation,
            };
          })
      : [];
  const noteEntries = [
    ...flagged.map((entry) => ({ ...entry, noteFlags: entry.riskFlags })),
    ...challenged.map((entry) => ({ ...entry, noteFlags: entry.riskFlags })),
  ].reduce((items, entry) => {
    const prior = items.find((item) => item.id === entry.id);
    if (!prior) return [...items, entry];
    prior.noteFlags = [...new Set([...prior.noteFlags, ...entry.noteFlags])];
    prior.challenge ||= entry.challenge;
    return items;
  }, []);
  const reviewedSourceCount = Number.isFinite(Number(grounding.reviewedCount))
    ? Number(grounding.reviewedCount)
    : grounding.entries.filter(
        (entry) => entry.semanticStatus === 'reviewed-source',
      ).length;
  const fallbackCount = Number.isFinite(Number(quality.fallbackCount))
    ? Number(quality.fallbackCount)
    : Number(grounding.fallbackCount) || 0;
  const fallbackSupport = quality.fallbackSupport;
  const label = quality.issueCount
    ? `${quality.issueCount} local clue note${quality.issueCount === 1 ? '' : 's'}`
    : 'Local clue notes';
  const familyCounts = grounding.familyCounts;
  const familySummary =
    familyCounts && typeof familyCounts === 'object'
      ? Object.entries(familyCounts)
          .filter(([, count]) => Number.isFinite(Number(count)) && Number(count) > 0)
          .sort(([left], [right]) => left.localeCompare(right))
          .map(([family, count]) => `${family.replaceAll('-', ' ')} ${count}`)
          .join(' · ')
      : '';
  const signalCounts =
    quality.signalCounts && typeof quality.signalCounts === 'object'
      ? quality.signalCounts
      : grounding.signalCounts && typeof grounding.signalCounts === 'object'
        ? grounding.signalCounts
        : {};
  const signalSummary = Object.entries(signalCounts)
    .filter(([, count]) => Number.isFinite(Number(count)) && Number(count) > 0)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([signal, count]) => `${SIGNAL_COPY[signal] || signal.replaceAll('-', ' ')} ${count}`)
    .join(' · ');
  const clueDiversity = provenance?.clueDiversity || grounding.diversity;
  async function toggleFlag(entry, flag) {
    if (!profileId) return;
    const flagKey = `${entry.id}:${flag}`;
    setPendingFlag(flagKey);
    setFlagError('');
    const phrase = `clue surfaces: ${labelForFlag(flag)}`;
    try {
      await recordAssociationPreference(
        profileId,
        phrase,
        flags[flagKey] ? 'clear' : 'exclude',
      );
      setFlags((value) => {
        const next = { ...value };
        if (next[flagKey]) delete next[flagKey];
        else next[flagKey] = true;
        return next;
      });
    } catch (error) {
      setFlagError(error instanceof Error ? error.message : 'This clue flag could not be saved.');
    } finally {
      setPendingFlag('');
    }
  }

  return (
    <details className="future-clue-quality-notes">
      <summary>
        <span>{label}</span>
        <small>Experimental local writing · semantic meaning unverified</small>
      </summary>
      <div className="future-clue-quality-body">
        <p>
          The grid and mechanical clue checks are fixed for this game. This
          note keeps model-written surfaces visible without interrupting play.
        </p>
        {crossingSupport?.status === 'measured' && (
          <p className="future-clue-quality-crossings">
            Structural crossings measured for {crossingSupport.entryCount} entries;
            {' '}
            {crossingSupport.weakWithoutCrossing?.length || 0} weak entries have
            no crossing foothold. Player support remains unmeasured.
          </p>
        )}
        {footholdSeedPlan?.version === 'private-foothold-seed-plan-v1' && (
          <p className="future-clue-quality-crossings">
            A structural seed is available for {footholdSeedPlan.seededTargetCount || 0}{' '}
            of {footholdSeedPlan.targetCount || 0} weaker entries. This only marks
            a candidate crossing neighbor; it does not predict an easy clue or
            a successful solve.
          </p>
        )}
        {fallbackCount > 0 && (
          <p className="future-clue-quality-reviewed">
            {fallbackCount} clue surface{fallbackCount === 1 ? '' : 's'} {fallbackCount === 1 ? 'uses' : 'use'} an
            answer-free crossing scaffold because no reviewed source supported
            the original surface. The puzzle remains playable through crossings
            and assistance.
          </p>
        )}
        {fallbackSupport?.entryCount > 0 && (
          <p className="future-clue-quality-crossings">
            Structural crossings are available for {fallbackSupport.withCrossingCount || 0}{' '}
            of {fallbackSupport.entryCount} scaffolded clue
            {fallbackSupport.entryCount === 1 ? '' : 's'}. Use a crossing or the
            assistance ladder as the next route; this metadata does not predict
            solve difficulty.
          </p>
        )}
        {familySummary && (
          <p className="future-clue-quality-families">
            Surface signals observed: {familySummary}. These labels describe
            visible conventions only; they do not establish a clue&apos;s meaning.
          </p>
        )}
        {signalSummary && (
          <p className="future-clue-quality-families">
            Literal clue markers observed: {signalSummary}. These counts describe
            the written surface, not the intended sense.
          </p>
        )}
        {clueDiversity?.repair?.status === 'repaired' && (
          <p className="future-clue-quality-families">
            A bounded local pass added {clueDiversity.repair.rewrittenCount || 0}{' '}
            visibly signalled clue surface
            {clueDiversity.repair.rewrittenCount === 1 ? '' : 's'}; the pass is
            advisory and does not establish meaning.
          </p>
        )}
        {clueDiversity?.status === 'varied-below-recipe-floor' && (
          <p className="future-clue-quality-reviewed">
            The writer reached {clueDiversity.nonDefinitionFamilies?.length || 0}{' '}
            of {clueDiversity.requiredNonDefinitionFamilies || 0} requested clue
            families and {clueDiversity.nonDefinitionCount || 0} of{' '}
            {clueDiversity.requiredNonDefinitionClues || 0} requested signalled
            clues. The board stays playable, but this recipe&apos;s visible variety
            target was not met.
          </p>
        )}
        {modelChallenge?.status === 'completed' && (
          <p className="future-clue-quality-model">
            An optional local challenger compared {modelChallenge.checkedCount || 0}{' '}
            clue surfaces. Its recommendations are advisory and unverified;
            they never gate this private game.
          </p>
        )}
        {modelChallenge?.status === 'failed' && (
          <p className="future-clue-quality-model">
            The optional local challenger was unavailable for this game. The
            deterministic clue notes remain the complete play-time check.
          </p>
        )}
        {reviewedCluePack?.matchedCount > 0 && (
          <p className="future-clue-quality-reviewed">
            {reviewedCluePack.matchedCount} clue surface
            {reviewedCluePack.matchedCount === 1 ? '' : 's'} came from the
            configured reviewed pack. The source receipt is retained locally;
            this private board is still not a publication claim.
          </p>
        )}
        {reviewedSourceCount > 0 && (
          <p className="future-clue-quality-reviewed">
            {reviewedSourceCount} exact visible clue
            {reviewedSourceCount === 1 ? '' : 's'} has a reviewed sense or fact
            join. This is source provenance, not evidence that the player knows
            the answer.
          </p>
        )}
        {reviewedCluePack?.contextCount > 0 && (
          <p className="future-clue-quality-reviewed">
            Reviewed senses or facts also supplied bounded context for{' '}
            {reviewedCluePack.contextCount} uncovered clue
            {reviewedCluePack.contextCount === 1 ? '' : 's'}; the model could
            not promote that context into an unreceipted factual claim.
          </p>
        )}
        {noteEntries.length > 0 ? (
          <ul>
            {noteEntries.map((entry) => (
              <li key={entry.id}>
                <strong>{entry.id}</strong>
                <span>{cluesById.get(entry.id) || 'Clue text unavailable'}</span>
                <small>{entry.noteFlags.map(labelForFlag).join(' · ')}</small>
                {entry.challenge && (
                  <small className="future-clue-quality-challenge-reason">
                    Local challenger: {entry.challenge.reason}
                  </small>
                )}
                <button
                  type="button"
                  className="future-clue-quality-flag"
                  disabled={!profileId || pendingFlag !== ''}
                  onClick={() => {
                    const flag = entry.noteFlags[0];
                    void toggleFlag(entry, flag);
                  }}
                >
                  {pendingFlag.startsWith(`${entry.id}:`)
                    ? 'Saving…'
                    : flags[`${entry.id}:${entry.noteFlags[0]}`]
                      ? 'Undo future-clue flag'
                      : entry.challenge
                        ? 'Keep this note for future puzzles'
                        : 'Flag for future puzzles'}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="future-clue-quality-clear">
            No deterministic clue issue was detected in this puzzle.
          </p>
        )}
        {flagError && <p className="future-clue-quality-error" role="alert">{flagError}</p>}
      </div>
    </details>
  );
}
