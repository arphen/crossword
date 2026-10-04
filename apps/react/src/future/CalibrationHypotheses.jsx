import React, { useEffect, useRef, useState } from 'react';

const choices = [
  { response: 'keep', label: 'Keep this thread' },
  { response: 'not-for-me', label: 'Not for me' },
  { response: 'pass', label: 'Pass' },
];

const responseLabels = {
  keep: 'You kept this possible path for now.',
  'not-for-me': 'You set this possible path aside for now.',
  pass: 'You passed on this path; passing adds no preference.',
};

function getResponse(responses, proposalId) {
  if (responses instanceof Map) return responses.get(proposalId);
  return responses?.[proposalId];
}

function initialResponseActivity(responses) {
  const entries =
    responses instanceof Map ? [...responses.entries()] : Object.entries(responses ?? {});
  return Object.fromEntries(
    entries
      .filter(([, response]) => response?.active === false)
      .map(([, response]) => [response.responseId, true]),
  );
}

function responseActivityKey(responses) {
  const entries =
    responses instanceof Map ? [...responses.entries()] : Object.entries(responses ?? {});
  return JSON.stringify(
    entries
      .map(([proposalId, response]) => [
        proposalId,
        response?.responseId,
        response?.active,
      ])
      .sort(([left], [right]) => String(left).localeCompare(String(right))),
  );
}

/** @param {{deck: {deckId: string, expired?: boolean, items: Array<{proposalId: string, phrase: string, relation: string, connection: string, ambiguity: string, sourceObservationIds: string[]}>}, responses: Record<string, {response: 'keep'|'not-for-me'|'pass', responseId: string, active: boolean}>|Map<string, {response: 'keep'|'not-for-me'|'pass', responseId: string, active: boolean}>, busyProposalId: string|null, loading?: boolean, disabled?: boolean, error?: string, onRespond: (proposalId: string, response: 'keep'|'not-for-me'|'pass') => void|Promise<unknown>, onAction: (proposalId: string, responseId: string, action: 'retract'|'restore') => unknown}} props */
export default function CalibrationHypotheses({
  deck,
  responses = {},
  busyProposalId = null,
  loading = false,
  disabled = false,
  error: externalError = '',
  onRespond,
  onAction,
}) {
  const [retractedResponseIds, setRetractedResponseIds] = useState(() =>
    initialResponseActivity(responses),
  );
  const [busyActionId, setBusyActionId] = useState(null);
  const [localError, setLocalError] = useState('');
  const swipeStarts = useRef(new Map());
  const activityKey = responseActivityKey(responses);

  useEffect(() => {
    setRetractedResponseIds(initialResponseActivity(responses));
    setBusyActionId(null);
    setLocalError('');
  }, [deck.deckId, activityKey]);

  function respond(proposalId, response) {
    setLocalError('');
    try {
      const result = onRespond(proposalId, response);
      if (result && typeof result.then === 'function') {
        result.catch((failure) => {
          setLocalError(
            failure instanceof Error
              ? failure.message
              : 'That response could not be saved. You can try again.',
          );
        });
      }
    } catch (failure) {
      setLocalError(
        failure instanceof Error
          ? failure.message
          : 'That response could not be saved. You can try again.',
      );
    }
  }

  async function revise(proposalId, responseId, action) {
    if (busyActionId) return;
    setLocalError('');
    setBusyActionId(proposalId);
    try {
      await onAction(proposalId, responseId, action);
      setRetractedResponseIds((current) => ({
        ...current,
        [responseId]: action === 'retract',
      }));
    } catch (failure) {
      setLocalError(
        failure instanceof Error
          ? failure.message
          : 'That change could not be saved. You can try again.',
      );
    } finally {
      setBusyActionId(null);
    }
  }

  function startSwipe(proposalId, event, blocked) {
    if (event.pointerType !== 'touch' || blocked) return;
    swipeStarts.current.set(proposalId, {
      pointerId: event.pointerId,
      clientX: event.clientX,
    });
  }

  function finishSwipe(proposalId, event, blocked) {
    const start = swipeStarts.current.get(proposalId);
    swipeStarts.current.delete(proposalId);
    if (!start || start.pointerId !== event.pointerId || blocked) return;
    const distance = event.clientX - start.clientX;
    if (Math.abs(distance) < 64) return;
    respond(proposalId, distance > 0 ? 'keep' : 'not-for-me');
  }

  return (
    <section
      className="future-hypotheses"
      aria-labelledby="future-hypotheses-title"
      aria-describedby="future-hypotheses-intro"
      aria-busy={loading || undefined}
    >
      <div className="future-hypotheses-heading">
        <div>
          <p className="future-eyebrow">The opening</p>
          <h2 id="future-hypotheses-title">Possible word paths.</h2>
        </div>
        <p id="future-hypotheses-intro">
          These are suggestions, not conclusions. You decide whether they lead
          anywhere. Keep one, set it aside, or pass; there is no need to answer
          every card.
        </p>
      </div>

      {loading && (
        <p className="future-hypotheses-loading" role="status" aria-live="polite">
          Gathering a few possible word paths…
        </p>
      )}

      {deck.expired && (
        <p className="future-hypotheses-expired" role="status">
          These paths have expired. You can still undo an active response, but
          new responses and restores are closed.
        </p>
      )}

      <ol className="future-hypothesis-list" aria-label="Possible word paths">
        {deck.items.map((item, index) => {
          const saved = getResponse(responses, item.proposalId);
          const isRetracted = Boolean(
            saved && retractedResponseIds[saved.responseId],
          );
          const busy =
            disabled ||
            loading ||
            busyProposalId === item.proposalId ||
            busyActionId === item.proposalId;
          const phraseId = `future-hypothesis-${index + 1}-phrase`;
          return (
            <li className="future-hypothesis-item" key={item.proposalId}>
              <article
                className={`future-hypothesis-card ${saved && !isRetracted ? 'has-response' : ''} ${isRetracted ? 'is-retracted' : ''}`}
                aria-labelledby={phraseId}
                onPointerDown={(event) =>
                  startSwipe(item.proposalId, event, busy || Boolean(deck.expired))
                }
                onPointerUp={(event) =>
                  finishSwipe(item.proposalId, event, busy || Boolean(deck.expired))
                }
                onPointerCancel={() => swipeStarts.current.delete(item.proposalId)}
              >
                <span className="future-hypothesis-index" aria-hidden="true">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <p className="future-hypothesis-kicker">A possible crossing</p>
                <h3 id={phraseId} className="future-hypothesis-phrase">
                  {item.phrase}
                </h3>

                <dl className="future-hypothesis-reading">
                  <div>
                    <dt>Relation</dt>
                    <dd>{item.relation}</dd>
                  </div>
                  <div>
                    <dt>A possible connection</dt>
                    <dd>{item.connection}</dd>
                  </div>
                  <div>
                    <dt>Still uncertain</dt>
                    <dd>{item.ambiguity}</dd>
                  </div>
                </dl>

                {saved ? (
                  <div className="future-hypothesis-response">
                    <p className="future-hypothesis-state" role="status">
                      {isRetracted
                        ? 'Set aside. The original response remains in your history.'
                        : responseLabels[saved.response] ??
                          'You responded to this possible path.'}
                    </p>
                    <div className="future-hypothesis-revision">
                      <button
                        type="button"
                        className="future-hypothesis-revision-button"
                        disabled={busy || (deck.expired && isRetracted)}
                        onClick={() =>
                          void revise(
                            item.proposalId,
                            saved.responseId,
                            isRetracted ? 'restore' : 'retract',
                          )
                        }
                      >
                        {busy
                          ? 'Saving…'
                          : isRetracted
                            ? 'Restore this response'
                            : 'Undo this response'}
                      </button>
                    </div>
                  </div>
                ) : null}

                {(!saved || isRetracted) && !deck.expired && (
                  <>
                    <p className="future-hypothesis-swipe-hint" aria-hidden="true">
                      Swipe right to keep · left to set aside
                    </p>
                    <div
                      className="future-hypothesis-actions"
                      role="group"
                      aria-label={`Respond to possible path ${index + 1}`}
                    >
                      {choices.map((choice) => (
                        <button
                          type="button"
                          key={choice.response}
                          className={`future-hypothesis-choice future-hypothesis-choice-${choice.response}`}
                          disabled={busy}
                          aria-pressed={Boolean(
                            saved && !isRetracted && saved.response === choice.response,
                          )}
                          onClick={() => respond(item.proposalId, choice.response)}
                        >
                          {choice.label}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </article>
            </li>
          );
        })}
      </ol>

      <p className="future-hypotheses-footer">
        You can leave the rest open. A pass is simply a pass.
      </p>
      {(externalError || localError) && (
        <p className="future-hypotheses-error" role="alert">
          {externalError || localError}
        </p>
      )}
    </section>
  );
}
