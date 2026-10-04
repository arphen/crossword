import React, { useEffect, useRef, useState } from 'react';
import { expandPostgameAssociation, respondToPostgameAssociation } from './postgame_associations';

const choices = [
  { response: 'keep', label: 'Keep this thread' },
  { response: 'not-for-me', label: 'Set it aside' },
  { response: 'pass', label: 'Pass' },
];

const responseLabels = {
  keep: 'Kept as a possible thread for future puzzles.',
  'not-for-me': 'Set aside for now; the path remains visible in history.',
  pass: 'Passed without adding a preference.',
};

function initialResponses(values) {
  return Object.fromEntries(
    Object.entries(values || {}).map(([associationId, value]) => [associationId, value]),
  );
}

function AssociationCard({ item, index, saved, busy, onRespond, onExpand, expanded }) {
  const isBusy = busy === item.associationId;
  const canExpand = saved?.response === 'keep' && !expanded;
  const pointerStart = useRef(null);

  function finishSwipe(event) {
    const start = pointerStart.current;
    pointerStart.current = null;
    if (
      !start ||
      start.pointerId !== event.pointerId ||
      start.pointerType !== 'touch' ||
      saved ||
      busy
    ) {
      return;
    }
    const distance = event.clientX - start.clientX;
    if (Math.abs(distance) < 64) return;
    // A right swipe keeps the path; a left swipe sets it aside. Passing and
    // the explicit controls remain available for a deliberate undecided path.
    onRespond(item, distance > 0 ? 'keep' : 'not-for-me');
  }

  return (
    <article
      className={`future-hypothesis-card ${saved ? 'has-response' : ''}`}
      aria-labelledby={`future-postgame-path-${index + 1}`}
      onPointerDown={(event) => {
        if (event.pointerType === 'touch' && !saved && !busy) {
          pointerStart.current = {
            pointerId: event.pointerId,
            pointerType: event.pointerType,
            clientX: event.clientX,
          };
        }
      }}
      onPointerUp={finishSwipe}
      onPointerCancel={() => {
        pointerStart.current = null;
      }}
    >
      <span className="future-hypothesis-index" aria-hidden="true">
        {String(index + 1).padStart(2, '0')}
      </span>
      <p className="future-hypothesis-kicker">
        {item.relation || 'possible crossing'}{item.depth ? ' · followed thread' : ''}
      </p>
      <h3 id={`future-postgame-path-${index + 1}`} className="future-hypothesis-phrase">
        {item.phrase}
      </h3>
      <dl className="future-hypothesis-reading">
        <div>
          <dt>A possible connection</dt>
          <dd>{item.explanation}</dd>
        </div>
      </dl>
      {saved ? (
        <>
          <p className="future-hypothesis-state" role="status">
            {responseLabels[saved.response] || 'Response saved locally.'}
          </p>
          {canExpand && (
            <button
              type="button"
              className="future-text-button"
              disabled={Boolean(busy)}
              onClick={() => void onExpand(item)}
            >
              {isBusy ? 'Following…' : 'Follow this thread'} <span aria-hidden="true">↗</span>
            </button>
          )}
          {expanded && <p className="future-small">A second path has opened below.</p>}
        </>
      ) : (
        <>
          <p className="future-hypothesis-swipe-hint" aria-hidden="true">
            Swipe right to keep · left to set aside
          </p>
          <div className="future-hypothesis-actions" role="group" aria-label={`Respond to word path ${index + 1}`}>
          {choices.map((choice) => (
            <button
              type="button"
              key={choice.response}
              className={`future-hypothesis-choice future-hypothesis-choice-${choice.response}`}
              disabled={Boolean(busy)}
              onClick={() => void onRespond(item, choice.response)}
            >
              {isBusy ? 'Saving…' : choice.label}
            </button>
          ))}
          </div>
        </>
      )}
    </article>
  );
}

export default function PostgameAssociations({ deck }) {
  const [responses, setResponses] = useState(() => initialResponses(deck.responses));
  const [expansions, setExpansions] = useState(() => deck.expansions || {});
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    setResponses(initialResponses(deck.responses));
    setExpansions(deck.expansions || {});
    setBusy(null);
    setError('');
  }, [deck.sessionId, JSON.stringify(deck.responses), JSON.stringify(deck.expansions)]);

  async function respond(item, value) {
    if (busy || responses[item.associationId]) return;
    setBusy(item.associationId);
    setError('');
    try {
      const { result } = await respondToPostgameAssociation({
        sessionId: deck.sessionId,
        associationId: item.associationId,
        response: value,
      });
      setResponses((current) => ({
        ...current,
        [item.associationId]: {
          response: value,
          responseId: result.responseId,
          active: true,
        },
      }));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'This word path could not be saved. Try again.');
    } finally {
      setBusy(null);
    }
  }

  async function expand(item) {
    if (busy || !responses[item.associationId] || responses[item.associationId].response !== 'keep') return;
    setBusy(item.associationId);
    setError('');
    try {
      const result = await expandPostgameAssociation({ sessionId: deck.sessionId, associationId: item.associationId });
      setExpansions(result.expansions || {});
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'This word path could not be expanded.');
    } finally {
      setBusy(null);
    }
  }

  if (!Array.isArray(deck.paths) || !deck.paths.length) return null;
  return (
    <section
      className="future-hypotheses future-postgame-associations"
      aria-labelledby="future-postgame-associations-title"
      aria-describedby="future-postgame-associations-intro"
    >
      <div className="future-hypotheses-heading">
        <div>
          <p className="future-eyebrow">A trace from this game</p>
          <h2 id="future-postgame-associations-title">Where might it lead?</h2>
        </div>
        <p id="future-postgame-associations-intro">
          The local model offers a few possible crossings between this puzzle and your growing word field. Keep one, set it aside, or let it pass.
        </p>
      </div>
      <ol className="future-hypothesis-list" aria-label="Postgame word paths">
        {deck.paths.map((item, index) => {
          const children = expansions[item.associationId] || [];
          return (
            <React.Fragment key={item.associationId}>
              <li className="future-hypothesis-item">
                <AssociationCard
                  item={item}
                  index={index}
                  saved={responses[item.associationId]}
                  busy={busy}
                  onRespond={respond}
                  onExpand={expand}
                  expanded={children.length > 0}
                />
              </li>
              {children.map((child, childIndex) => (
                <li className="future-hypothesis-item future-hypothesis-item-expanded" key={child.associationId}>
                  <AssociationCard
                    item={child}
                    index={index + childIndex + 1}
                    saved={responses[child.associationId]}
                    busy={busy}
                    onRespond={respond}
                    onExpand={expand}
                    expanded={false}
                  />
                </li>
              ))}
            </React.Fragment>
          );
        })}
      </ol>
      <p className="future-hypotheses-footer">
        These are invitations, not conclusions. The game remains the source of the trace; your response decides what becomes a signal.
      </p>
      {error && <p className="future-hypotheses-error" role="alert">{error}</p>}
    </section>
  );
}
