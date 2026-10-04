import React, { useEffect, useState } from 'react';

const languageNames = {
  de: 'German',
  es: 'Spanish',
  fr: 'French',
  it: 'Italian',
  ja: 'Japanese',
  nl: 'Dutch',
  pt: 'Portuguese',
};

export default function LearningReview({ profileId, profileReady }) {
  const [due, setDue] = useState([]);
  const [remaining, setRemaining] = useState(0);
  const [taskPack, setTaskPack] = useState(null);
  const [dueLimit, setDueLimit] = useState(3);
  const [answers, setAnswers] = useState({});
  const [attempts, setAttempts] = useState({});
  const [state, setState] = useState('loading');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    let active = true;
    setState('loading');
    setError('');
    setAttempts({});
    // FutureApp creates the profile asynchronously on first play. Waiting for
    // that same promise prevents an initial 404 from permanently hiding the
    // delayed-review lane. Tests and embedders may omit the prop, which keeps
    // the component immediately usable.
    if (profileReady === null) return () => { active = false; };
    Promise.resolve(profileReady === undefined ? true : profileReady)
      .then((ready) => {
        if (!active || !ready) return;
        return fetch(`/api/future/profile/${encodeURIComponent(profileId)}/learning-review`)
          .then(async (response) => {
            const body = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(body.error || 'The recall thread is unavailable.');
            return body;
          })
          .then((body) => {
            if (!active) return;
            setDue(Array.isArray(body.due) ? body.due : []);
            setRemaining(Number.isInteger(body.remaining) ? Math.max(0, body.remaining) : 0);
            setTaskPack(body.policy?.taskPack || null);
            setDueLimit(3);
            setState('ready');
          });
      })
      .catch((reason) => {
        if (!active) return;
        setError(reason instanceof Error ? reason.message : 'The recall thread is unavailable.');
        setState('error');
      });
    return () => {
      active = false;
    };
  }, [profileId, profileReady]);

  async function showMore() {
    const nextLimit = dueLimit === 3 ? 6 : 12;
    setLoadingMore(true);
    setError('');
    try {
      const url = `/api/future/profile/${encodeURIComponent(profileId)}/learning-review?limit=${nextLimit}`;
      const response = await fetch(url);
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.error || 'The recall thread is unavailable.');
      const incoming = Array.isArray(body.due) ? body.due : [];
      setDue((current) => {
        const merged = new Map(current.map((item) => [item.taskId, item]));
        incoming.forEach((item) => {
          if (item?.taskId) merged.set(item.taskId, item);
        });
        return [...merged.values()];
      });
      setRemaining(Number.isInteger(body.remaining) ? Math.max(0, body.remaining) : 0);
      setTaskPack(body.policy?.taskPack || taskPack);
      setDueLimit(nextLimit);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The recall thread is unavailable.');
    } finally {
      setLoadingMore(false);
    }
  }

  async function reveal(item) {
    setBusy(item.taskId);
    try {
      const url = `/api/future/profile/${encodeURIComponent(profileId)}/learning-review/answer?taskId=${encodeURIComponent(item.taskId)}`;
      const response = await fetch(url);
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.error || 'The answer could not be shown.');
      setAnswers((current) => ({ ...current, [item.taskId]: body.answer }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The answer could not be shown.');
    } finally {
      setBusy(null);
    }
  }

  async function respond(item, responseValue) {
    setBusy(item.taskId);
    setError('');
    const assisted = Object.prototype.hasOwnProperty.call(answers, item.taskId);
    try {
      const response = await fetch(
        `/api/future/profile/${encodeURIComponent(profileId)}/learning-review`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({
            taskId: item.taskId,
            response: responseValue,
            mode: assisted ? 'assisted' : 'independent',
          }),
        },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.error || 'The recall response could not be saved.');
      setDue((current) => current.filter((candidate) => candidate.taskId !== item.taskId));
      setAnswers((current) => {
        const next = { ...current };
        delete next[item.taskId];
        return next;
      });
      setAttempts((current) => {
        const next = { ...current };
        delete next[item.taskId];
        return next;
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The recall response could not be saved.');
    } finally {
      setBusy(null);
    }
  }

  if (state === 'loading' || state === 'error' || (due.length === 0 && remaining === 0)) return null;

  return (
    <section className="future-learning-review" aria-labelledby="future-learning-review-title">
      <div className="future-learning-review-heading">
        <div>
          <p className="future-eyebrow">A thread returns</p>
          <h2 id="future-learning-review-title">A quiet recall.</h2>
        </div>
        <span className="future-learning-review-count">
          {remaining ? `${due.length} of ${due.length + remaining} due` : `${due.length} due`}
        </span>
      </div>
      <p className="future-small">
        Try without help first. Seeing the answer is still useful, and is recorded separately.
      </p>
      {taskPack?.status === 'reviewed-admitted' ? (
        <p className="future-small future-learning-review-provenance-copy">
          This thread uses an admitted language task pack; its source receipt is retained locally.
        </p>
      ) : (
        <p className="future-small future-learning-review-provenance-copy">
          This thread uses a local language fixture; meaning and mastery remain unverified.
        </p>
      )}
      <div className="future-learning-review-list">
        {due.map((item) => {
          const answer = answers[item.taskId];
          const attempt = attempts[item.taskId] || '';
          const language = languageNames[item.language] || item.language.toUpperCase();
          return (
            <article className="future-learning-review-card" key={item.taskId}>
              <div className="future-learning-review-meta">
                <span>{language}</span>
                <span>{item.length} letters</span>
                <span>{item.reviewStage ? `Review ${item.reviewStage}` : 'First recall'}</span>
                {item.overdueHours >= 1 && (
                  <span className="future-learning-review-overdue">
                    {Math.round(item.overdueHours)}h overdue
                  </span>
                )}
                {item.taskPack?.reviewStatus === 'reviewed-admitted' ? (
                  <span className="future-learning-review-provenance">
                    Reviewed task
                  </span>
                ) : item.taskPack ? (
                  <span className="future-learning-review-provenance">
                    Local fixture · meaning unverified
                  </span>
                ) : null}
              </div>
              <p className="future-learning-review-clue">{item.clue}</p>
              {!answer && (
                <label className="future-learning-review-attempt">
                  <span>Try the form first</span>
                  <input
                    type="text"
                    value={attempt}
                    autoComplete="off"
                    spellCheck="false"
                    aria-label={`Your recall for ${item.clue}`}
                    placeholder="Type your recall (optional)"
                    onChange={(event) =>
                      setAttempts((current) => ({
                        ...current,
                        [item.taskId]: event.target.value.slice(0, 80),
                      }))
                    }
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && attempt.trim()) {
                        event.preventDefault();
                        void respond(item, 'remembered');
                      }
                    }}
                  />
                </label>
              )}
              {answer && <p className="future-learning-review-answer" aria-label="Answer">{answer}</p>}
              <div className="future-learning-review-actions">
                {!answer && (
                  <button
                    className="future-text-button"
                    onClick={() => void reveal(item)}
                    disabled={busy === item.taskId}
                  >
                    {busy === item.taskId ? 'Opening…' : 'Show answer'}
                  </button>
                )}
                <button
                  className="future-text-button"
                  onClick={() => void respond(item, 'remembered')}
                  disabled={busy === item.taskId}
                >
                  {answer ? 'Saw it' : 'I recalled it'}
                </button>
                <button
                  className="future-text-button"
                  onClick={() => void respond(item, 'not-yet')}
                  disabled={busy === item.taskId}
                >
                  Not yet
                </button>
                <button
                  className="future-text-button"
                  onClick={() => void respond(item, 'pass')}
                  disabled={busy === item.taskId}
                >
                  Pass
                </button>
              </div>
            </article>
          );
        })}
      </div>
      {remaining > 0 && (
        <button
          className="future-text-button"
          type="button"
          onClick={() => void showMore()}
          disabled={loadingMore}
        >
          {loadingMore ? 'Opening more…' : 'Show more recall threads'}
        </button>
      )}
      {error && <p className="future-small" role="alert">{error}</p>}
    </section>
  );
}
