import React, { useRef, useState } from 'react';
import { submitReflectionAction, submitReflectionResponse } from './reflection';

const responseButtons = [
  { value: 'keep', label: 'Keep this', aria: 'Keep this impression' },
  {
    value: 'not-for-me',
    label: 'Turn away',
    aria: 'Turn away from this impression',
  },
  {
    value: 'pass',
    label: 'Let it pass',
    aria: 'Pass on this impression without adding a preference',
  },
];

function restoredAnswers(deck) {
  return Object.fromEntries(
    (deck.responses || [])
      .map((item) => [
        item.response?.cardId,
        {
          response: item.response?.response,
          responseId: item.response?.responseId,
          evidence: item.evidence,
          epistemeRevision: item.epistemeRevision,
          actionEpistemeRevision: item.latestActionEpistemeRevision,
          latestAction: item.latestAction,
          retracted: item.state === 'retracted',
        },
      ])
      .filter(
        ([cardId, answer]) => cardId && answer.responseId && answer.response,
      ),
  );
}

function signalReceipt(saved) {
  if (!saved?.evidence) return null;
  if (saved.response === 'pass') {
    return 'Undecided: no preference mapping was added.';
  }
  const mappings = saved.evidence.mappings?.[saved.response] || [];
  const labels = mappings
    .map((mapping) => mapping.concept?.label)
    .filter(Boolean);
  if (!labels.length) return 'Recorded without a preference mapping.';
  const stance = saved.response === 'keep' ? 'seek' : 'avoid';
  return `${stance}: ${labels.join(' · ')}`;
}

export default function ReflectionCards({ deck }) {
  const [answers, setAnswers] = useState(() => restoredAnswers(deck));
  const [pending, setPending] = useState({});
  const [error, setError] = useState('');
  const swipeStarts = useRef(new Map());

  async function respond(card, shownPosition, response) {
    if (pending[card.cardId] || answers[card.cardId]) return;
    setError('');
    setPending((value) => ({ ...value, [card.cardId]: response }));
    try {
      const { payload, result } = await submitReflectionResponse({
        sessionId: deck.sessionId,
        card,
        shownPosition,
        response,
      });
      setAnswers((value) => ({
        ...value,
        [card.cardId]: {
          response,
          responseId: payload.responseId,
          evidence: result?.evidence,
          epistemeRevision: result?.revision,
          retracted: false,
        },
      }));
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : 'This impression could not be saved.',
      );
    } finally {
      setPending((value) => ({ ...value, [card.cardId]: false }));
    }
  }

  async function revise(card, action) {
    const answer = answers[card.cardId];
    if (!answer || pending[card.cardId]) return;
    setError('');
    setPending((value) => ({ ...value, [card.cardId]: action }));
    try {
      const { result } = await submitReflectionAction({
        sessionId: deck.sessionId,
        cardId: card.cardId,
        responseId: answer.responseId,
        action,
      });
      setAnswers((value) => ({
        ...value,
        [card.cardId]: {
          ...answer,
          actionEpistemeRevision: result?.revision,
          latestAction: { action },
          retracted: action === 'retract',
        },
      }));
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : 'This revision could not be saved.',
      );
    } finally {
      setPending((value) => ({ ...value, [card.cardId]: false }));
    }
  }

  function startSwipe(card, event) {
    if (event.pointerType !== 'touch' || answers[card.cardId] || pending[card.cardId]) return;
    swipeStarts.current.set(card.cardId, {
      pointerId: event.pointerId,
      clientX: event.clientX,
    });
  }

  function finishSwipe(card, event) {
    const start = swipeStarts.current.get(card.cardId);
    swipeStarts.current.delete(card.cardId);
    if (
      !start ||
      start.pointerId !== event.pointerId ||
      answers[card.cardId] ||
      pending[card.cardId]
    ) return;
    const distance = event.clientX - start.clientX;
    if (Math.abs(distance) < 64) return;
    // Keep and turn-away are the two directional preferences. Pass remains
    // an explicit choice so an undecided gesture never writes a signal.
    void respond(card, indexFor(card), distance > 0 ? 'keep' : 'not-for-me');
  }

  function indexFor(card) {
    return deck.cards.findIndex((candidate) => candidate.cardId === card.cardId);
  }

  const complete = deck.cards.every((card) => answers[card.cardId]);
  const analysis = deck.analysisSummary;
  const hasAnalysis =
    analysis &&
    analysis.version === 'private-session-analysis-summary-v1' &&
    Number.isInteger(analysis.entryCount);
  return (
    <section
      className="future-reflections"
      aria-labelledby="future-reflections-title"
    >
      {hasAnalysis && (
        <section
          className="future-game-analysis"
          aria-labelledby="future-game-analysis-title"
        >
          <div className="future-game-analysis-heading">
            <div>
              <p className="future-eyebrow">What this game left behind</p>
              <h2 id="future-game-analysis-title">A trace, not a verdict.</h2>
            </div>
            <p>
              The replay keeps the route you took visible while leaving mastery
              open. Only the difficulty signal steers the next local puzzle.
            </p>
          </div>
          <div className="future-game-analysis-stats" role="list">
            <span role="listitem">
              <strong>{analysis.independentCount || 0}</strong>
              independent
            </span>
            <span role="listitem">
              <strong>{analysis.supportedCount || 0}</strong>
              crossing-supported
            </span>
            <span role="listitem">
              <strong>{analysis.assistedCount || 0}</strong>
              check or reveal
            </span>
            <span role="listitem">
              <strong>{analysis.incorrectAttemptCount || 0}</strong>
              wrong turns
            </span>
            <span role="listitem">
              <strong>{analysis.untouchedCount || 0}</strong>
              left untouched
            </span>
          </div>
          <small>
            {analysis.entryCount} entries replayed · exposure and recall remain
            separate from preference signals
          </small>
        </section>
      )}
      <div className="future-reflections-heading">
        <div>
          <p className="future-eyebrow">After the puzzle</p>
          <h2 id="future-reflections-title">A few last impressions.</h2>
        </div>
        <p>
          Keep one, turn away, or let it pass. Passing carries no preference.
        </p>
      </div>
      {deck.languageLearning && (
        <div className="future-language-review" role="status">
          <span className="future-eyebrow">Language thread</span>
          <strong>
            {deck.languageLearning.state === 'review'
              ? `A few ${deck.languageLearning.language} forms are ready to revisit.`
              : `A small ${deck.languageLearning.language} doorway was opened.`}
          </strong>
          <small>
            This is gentle recurrence from your setup, not a claim of mastery.
          </small>
        </div>
      )}
      <div className="future-reflection-cards">
        {deck.cards.map((card, index) => {
          const saved = answers[card.cardId];
          const answer = saved?.response;
          const interpretation =
            answer === 'keep'
              ? card.interpretation.keep
              : answer === 'not-for-me'
                ? card.interpretation.notForMe
                : answer === 'pass'
                  ? card.interpretation.pass
                  : '';
          return (
            <article
              className="future-reflection-card"
              key={card.cardId}
              onPointerDown={(event) => startSwipe(card, event)}
              onPointerUp={(event) => finishSwipe(card, event)}
              onPointerCancel={() => swipeStarts.current.delete(card.cardId)}
            >
              <span className="future-reflection-index">0{index + 1}</span>
              {card.source === 'model' && (
                <>
                  <span className="future-reflection-source">
                    Local mirror · wording suggestion
                  </span>
                  {card.generationReceipt?.model && (
                    <small className="future-reflection-model-receipt">
                      {card.generationReceipt.model}
                      {card.generationReceipt.promptVersion
                        ? ` · ${card.generationReceipt.promptVersion}`
                        : ''}
                    </small>
                  )}
                </>
              )}
              <p className="future-reflection-text">{card.text}</p>
              {answer ? (
                <div className="future-reflection-saved" role="status">
                  {saved.retracted ? (
                    <span>
                      This impression is no longer steering your profile.
                    </span>
                  ) : (
                    <span>{interpretation}</span>
                  )}
                  <small>
                    {saved.retracted
                      ? 'The original response remains in the history.'
                      : 'Saved to this local episteme.'}
                  </small>
                  <small className="future-reflection-receipt">
                    {saved.retracted
                      ? `Retraction recorded at episteme revision ${saved.actionEpistemeRevision ?? '—'}.`
                      : saved.latestAction?.action === 'restore'
                        ? `Restoration recorded at episteme revision ${saved.actionEpistemeRevision ?? '—'}.`
                      : `Episteme receipt · revision ${saved.epistemeRevision ?? '—'} · ${signalReceipt(saved) || 'reversible local signal recorded.'}`}
                  </small>
                  <button
                    type="button"
                    className="future-reflection-revision"
                    disabled={Boolean(pending[card.cardId])}
                    onClick={() =>
                      revise(card, saved.retracted ? 'restore' : 'retract')
                    }
                  >
                    {pending[card.cardId]
                      ? 'Saving…'
                      : saved.retracted
                        ? 'Restore this signal'
                        : 'Undo this signal'}
                  </button>
                </div>
              ) : (
                <>
                  <p className="future-reflection-swipe-hint" aria-hidden="true">
                    Swipe right to keep · left to turn away
                  </p>
                  <div
                    className="future-reflection-actions"
                    role="group"
                    aria-label={`Respond to impression ${index + 1}`}
                  >
                    {responseButtons.map((button) => (
                      <button
                        key={button.value}
                        type="button"
                        aria-label={button.aria}
                        disabled={Boolean(pending[card.cardId])}
                        onClick={() => respond(card, index, button.value)}
                      >
                        {pending[card.cardId] === button.value
                          ? 'Saving…'
                          : button.label}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </article>
          );
        })}
      </div>
      {error && (
        <p className="future-reflection-error" role="alert">
          {error}
        </p>
      )}
      {complete && (
        <p className="future-reflection-complete" role="status">
          All three impressions are saved in your local episteme.
        </p>
      )}
    </section>
  );
}
