import React, { useEffect, useRef, useState } from 'react';
import {
  catalog,
  changeObject,
  expandAssociations,
  freshDraft,
  readDraft,
  saveProfile,
  seedProfile,
  writeDraft,
} from './episteme';
import Signifier from './Signifier';
import FutureSolver from './FutureSolver';
import './future.css';

const chapters = ['Encounter', 'Company', 'Resonance', 'Rhythm', 'Beginning'];
const titles = [
  'Before the words,',
  'A curious company.',
  'Let a word find you.',
  'Find your rhythm.',
  'A beginning,',
];
const titleEnds = ['a little wonder.', '', '', '', 'not a definition.'];
const descriptions = [
  'Something here catches your eye. Take it with you.',
  'What belongs beside it? They don’t have to make sense together.',
  'Keep up to three. A sound, a shape, a passing thought.',
  'Choose the kind of crossword you feel like today.',
  'A few things to carry into the next puzzle. You can always change your mind.',
];

function Arrow({ back = false }) {
  return (
    <svg
      width="19"
      height="19"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      <path d={back ? 'M19 12H5m6-6-6 6 6 6' : 'M5 12h14m-6-6 6 6-6 6'} />
    </svg>
  );
}
function Mark() {
  return (
    <span className="future-mark" aria-hidden="true">
      <i />
      <i />
      <i />
      <i />
    </span>
  );
}

function ObjectChoice({ item, index, selected, onChoose }) {
  return (
    <button
      className={`future-object ${selected ? 'is-chosen' : ''}`}
      onClick={() => onChoose(item.id)}
      aria-pressed={selected}
      aria-label={item.label}
    >
      <span className="future-object-index">0{index + 1}</span>
      <Signifier kind={item.id} />
      <span className="future-object-label">{item.label}</span>
      <span className="future-object-check" aria-hidden="true">
        {selected ? '✓' : '+'}
      </span>
    </button>
  );
}

function ProfileField({ draft, update, editable = true }) {
  const profile = seedProfile(draft);
  const allWords = seedProfile({ ...draft, excluded: [] }).associations;
  return (
    <div className="future-field">
      <div className="future-field-objects" aria-hidden="true">
        {draft.object ? <Signifier kind={draft.object} /> : <Mark />}
        {draft.companion && (
          <>
            <span>+</span>
            <Signifier kind={draft.companion} />
          </>
        )}
      </div>
      <p className="future-field-prose">{profile.prose}</p>
      <p className="future-eyebrow">Your first constellation</p>
      <div className="future-associations">
        {allWords.length ? (
          allWords.map((word) => (
            <button
              key={word}
              disabled={!editable}
              aria-pressed={!draft.excluded.includes(word)}
              className={draft.excluded.includes(word) ? 'is-muted' : ''}
              onClick={() =>
                update({
                  excluded: draft.excluded.includes(word)
                    ? draft.excluded.filter((item) => item !== word)
                    : [...draft.excluded, word],
                })
              }
            >
              {word}
              <span aria-hidden="true">
                {draft.excluded.includes(word) ? '+' : '×'}
              </span>
            </button>
          ))
        ) : (
          <p className="future-small">
            An open field. Your first associations can arrive later.
          </p>
        )}
      </div>
      {allWords.length > 0 && editable && (
        <p className="future-small">
          Tap any word to leave it behind. Tap again to bring it back.
        </p>
      )}
      <div className="future-profile-facts">
        <span>
          <b>{catalog.days.find((day) => day.id === draft.weekday).label}</b>{' '}
          difficulty
        </span>
        <span>English crossword</span>
        {draft.learningLanguage !== 'None for now' && (
          <span>{draft.learningLanguage} learning interest</span>
        )}
      </div>
    </div>
  );
}

export default function FutureApp() {
  const [draft, setDraft] = useState(readDraft);
  const [playing, setPlaying] = useState(() => draft.complete);
  const [profileOpen, setProfileOpen] = useState(false);
  const [storageOkay, setStorageOkay] = useState(true);
  const [saveState, setSaveState] = useState('idle');
  const [reflectionState, setReflectionState] = useState('idle');
  const heading = useRef(null);
  const dialog = useRef(null);
  const request = useRef(null);
  const reflectionRequest = useRef(null);
  const saveRevision = useRef(0);
  const step = draft.step;
  const selectedObject = catalog.objects.find(
    (item) => item.id === draft.object,
  );
  const selectedDay = catalog.days.find((day) => day.id === draft.weekday);
  const update = (patch) => {
    setDraft((value) => ({ ...value, ...patch }));
    if (playing) {
      request.current?.abort();
      saveRevision.current++;
      setSaveState('idle');
    }
  };

  useEffect(() => {
    document.title = 'Crossword · A personal beginning';
    return () => {
      document.title = 'Crossword Puzzle';
    };
  }, []);
  useEffect(() => {
    setStorageOkay(writeDraft(draft));
  }, [draft]);
  useEffect(() => {
    if (!playing) heading.current?.focus({ preventScroll: true });
  }, [step, playing]);
  useEffect(
    () => () => {
      request.current?.abort();
      reflectionRequest.current?.abort();
    },
    [],
  );
  useEffect(() => {
    reflectionRequest.current?.abort();
    reflectionRequest.current = null;
    setReflectionState('idle');
  }, [draft.object, draft.companion, draft.traces]);
  useEffect(() => {
    if (profileOpen) dialog.current?.showModal();
    else dialog.current?.close();
  }, [profileOpen]);

  async function persist(value) {
    request.current?.abort();
    const revision = ++saveRevision.current;
    const controller = new AbortController();
    request.current = controller;
    setSaveState('saving');
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    try {
      await saveProfile(value, controller.signal);
      if (revision === saveRevision.current) setSaveState('saved');
    } catch {
      if (revision === saveRevision.current) setSaveState('offline');
    } finally {
      window.clearTimeout(timeout);
    }
  }
  function enter() {
    reflectionRequest.current?.abort();
    const value = { ...draft, complete: true };
    setDraft(value);
    setPlaying(true);
    void persist(value);
  }
  async function reflect() {
    reflectionRequest.current?.abort();
    const controller = new AbortController();
    reflectionRequest.current = controller;
    setReflectionState('thinking');
    const timeout = window.setTimeout(() => controller.abort(), 45000);
    try {
      const reflection = await expandAssociations(draft, controller.signal);
      if (!controller.signal.aborted) {
        update({ reflection });
        setReflectionState('ready');
      }
    } catch {
      if (reflectionRequest.current === controller)
        setReflectionState('unavailable');
    } finally {
      window.clearTimeout(timeout);
    }
  }
  function advance() {
    if (step === 4) {
      enter();
      return;
    }
    update({ step: step + 1 });
  }
  function skip() {
    if (step === 0)
      update({
        object: null,
        companion: null,
        traces: [],
        excluded: [],
        reflection: null,
        step: 3,
      });
    else if (step === 1) update({ companion: null, reflection: null, step: 2 });
    else if (step === 2)
      update({ traces: [], excluded: [], reflection: null, step: 3 });
  }
  const canContinue =
    step === 0
      ? Boolean(draft.object)
      : step === 1
        ? Boolean(draft.companion)
        : true;
  const previousStep = step === 2 && !draft.object ? 0 : step - 1;
  const saveMessage =
    saveState === 'saving'
      ? 'Saving your beginning…'
      : saveState === 'saved'
        ? 'Saved on this device and your local server.'
        : saveState === 'offline'
          ? 'Kept on this device. The local server is unavailable.'
          : 'Kept on this device. Save changes to keep a copy on your local server.';

  return (
    <div className={`future-root ${playing ? 'future-playing' : ''}`}>
      <header className="future-header">
        <a
          className="future-brand"
          href="/future"
          aria-label="Crossword future"
        >
          <Mark />
          <span>
            crossword<span className="future-brand-divider">/</span>
            <em>future</em>
          </span>
        </a>
        <span className="future-header-note">
          {playing
            ? 'A more personal beginning'
            : 'Every word begins somewhere'}
        </span>
        {playing ? (
          <button
            className="future-text-button"
            onClick={() => setProfileOpen(true)}
          >
            <span className="future-status-dot" />
            Your constellation <span aria-hidden="true">↗</span>
          </button>
        ) : (
          <a className="future-text-button" href="/">
            Daily crossword <span aria-hidden="true">↗</span>
          </a>
        )}
      </header>

      {playing ? (
        <>
          <div className="future-solver">
            <FutureSolver weekday={draft.weekday} />
          </div>
          <dialog
            className="future-profile-dialog"
            ref={dialog}
            onCancel={() => setProfileOpen(false)}
            onClose={() => setProfileOpen(false)}
            aria-labelledby="future-profile-title"
          >
            <div className="future-dialog-top">
              <span className="future-eyebrow">The starting episteme</span>
              <button
                aria-label="Close constellation"
                className="future-close"
                onClick={() => setProfileOpen(false)}
              >
                ×
              </button>
            </div>
            <h2 id="future-profile-title">Room to become.</h2>
            <ProfileField draft={draft} update={update} />
            <p className="future-small">
              Your weekday sets the puzzle you play now. These associations and
              your language interest are saved for future personalized
              generation; today’s puzzle still comes from the daily collection.
            </p>
            <p className="future-save-status" role="status">
              {saveMessage}
            </p>
            <div className="future-dialog-actions">
              <button
                className="future-text-button"
                onClick={() => {
                  if (
                    !window.confirm(
                      'Begin setup again? This will close the current puzzle and clear its unsaved letters. Your saved starting profile will be replaced when you finish setup.',
                    )
                  )
                    return;
                  const value = {
                    ...freshDraft(),
                    id: draft.id,
                    weekday: draft.weekday,
                    learningLanguage: draft.learningLanguage,
                  };
                  setDraft(value);
                  setProfileOpen(false);
                  setPlaying(false);
                  setSaveState('idle');
                }}
              >
                Begin again
              </button>
              <button
                className="future-primary"
                onClick={() => void persist(draft)}
                disabled={saveState === 'saving'}
              >
                {saveState === 'saving' ? 'Saving…' : 'Save changes'}
                <Arrow />
              </button>
            </div>
          </dialog>
        </>
      ) : (
        <>
          <div className="future-stage-layout">
            <aside className="future-left-rail" aria-label="Setup progress">
              <p className="future-eyebrow">A personal crossword</p>
              <ol className="future-chapters">
                {chapters.map((chapter, index) => (
                  <li
                    key={chapter}
                    className={
                      index === step
                        ? 'is-current'
                        : index < step
                          ? 'is-past'
                          : ''
                    }
                    aria-current={index === step ? 'step' : undefined}
                  >
                    <span>0{index + 1}</span>
                    {chapter}
                    {index < step && <i aria-hidden="true">·</i>}
                  </li>
                ))}
              </ol>
              <div className="future-rail-word" aria-hidden="true">
                ACROSS
              </div>
              <p className="future-rail-foot">
                A few small choices.
                <br />
                An opening, all your own.
              </p>
            </aside>
            <main className="future-main">
              <div className="future-step-label">
                <span className="future-eyebrow">
                  0{step + 1} / 05 <span>—</span> {chapters[step]}
                </span>
                <span className="future-step-dots" aria-hidden="true">
                  {chapters.map((chapter, index) => (
                    <i
                      key={chapter}
                      className={index <= step ? 'is-lit' : ''}
                    />
                  ))}
                </span>
              </div>
              <section
                key={step}
                className={`future-scene future-scene-${step}`}
                aria-labelledby="future-heading"
              >
                <h1 id="future-heading" ref={heading} tabIndex={-1}>
                  {titles[step]}
                  {titleEnds[step] && (
                    <>
                      <br />
                      <em>{titleEnds[step]}</em>
                    </>
                  )}
                </h1>
                <p className="future-introduction">{descriptions[step]}</p>
                {step === 0 && (
                  <div className="future-object-grid">
                    {catalog.objects.map((item, index) => (
                      <ObjectChoice
                        key={item.id}
                        item={item}
                        index={index}
                        selected={draft.object === item.id}
                        onChoose={(object) =>
                          setDraft((value) => changeObject(value, object))
                        }
                      />
                    ))}
                  </div>
                )}
                {step === 1 && (
                  <div className="future-company">
                    <div className="future-held-object">
                      <span className="future-eyebrow">You brought</span>
                      <Signifier kind={draft.object} />
                      <span>{selectedObject?.label}</span>
                      <span
                        className="future-company-line"
                        aria-hidden="true"
                      />
                    </div>
                    <div className="future-companion-grid">
                      {(selectedObject?.companions ?? []).map((id, index) => (
                        <ObjectChoice
                          key={id}
                          item={catalog.companions.find(
                            (item) => item.id === id,
                          )}
                          index={index}
                          selected={draft.companion === id}
                          onChoose={(companion) =>
                            update({
                              companion,
                              excluded: [],
                              reflection: null,
                            })
                          }
                        />
                      ))}
                    </div>
                  </div>
                )}
                {step === 2 && (
                  <>
                    <div
                      className="future-traces"
                      role="group"
                      aria-label="Keep up to three traces"
                    >
                      {catalog.traces.map((word, index) => (
                        <button
                          key={word}
                          className={`future-trace trace-${index} ${draft.traces.includes(word) ? 'is-chosen' : ''}`}
                          aria-pressed={draft.traces.includes(word)}
                          disabled={
                            draft.traces.length === 3 &&
                            !draft.traces.includes(word)
                          }
                          onClick={() =>
                            update({
                              traces: draft.traces.includes(word)
                                ? draft.traces.filter((item) => item !== word)
                                : [...draft.traces, word],
                              excluded: [],
                              reflection: null,
                            })
                          }
                        >
                          {word}
                          <span aria-hidden="true">
                            {draft.traces.includes(word) ? '·' : ''}
                          </span>
                        </button>
                      ))}
                    </div>
                    <p className="future-choice-count" role="status">
                      {draft.traces.length} of 3 kept <span>·</span> No need to
                      explain.
                    </p>
                  </>
                )}
                {step === 3 && (
                  <div className="future-rhythm">
                    <div
                      className="future-days"
                      role="group"
                      aria-label="Crossword difficulty"
                    >
                      {catalog.days.map((day) => (
                        <button
                          key={day.id}
                          className={
                            draft.weekday === day.id ? 'is-chosen' : ''
                          }
                          aria-pressed={draft.weekday === day.id}
                          aria-label={day.label}
                          onClick={() => update({ weekday: day.id })}
                        >
                          <span>{day.short}</span>
                          <span className="future-day-bars" aria-hidden="true">
                            {Array.from({ length: 6 }, (_, index) => (
                              <i
                                key={index}
                                className={index < day.level ? 'is-lit' : ''}
                              />
                            ))}
                          </span>
                        </button>
                      ))}
                    </div>
                    <div className="future-day-story" aria-live="polite">
                      <span className="future-day-monogram" aria-hidden="true">
                        {selectedDay.short[0]}
                      </span>
                      <div>
                        <p className="future-eyebrow">{selectedDay.label}</p>
                        <h2>{selectedDay.title}</h2>
                        <p>{selectedDay.description}</p>
                      </div>
                    </div>
                    <p className="future-small">
                      A difficulty, not a date. Every day is available every
                      day.
                    </p>
                    <div className="future-language">
                      <div>
                        <label htmlFor="future-learning">
                          Leave a little room for another language?
                        </label>
                        <p>
                          Optional. An interest to carry into future puzzles.
                        </p>
                      </div>
                      <select
                        id="future-learning"
                        value={draft.learningLanguage}
                        onChange={(event) =>
                          update({ learningLanguage: event.target.value })
                        }
                      >
                        {catalog.languages.map((language) => (
                          <option key={language}>{language}</option>
                        ))}
                      </select>
                    </div>
                    <details className="future-conventions">
                      <summary>
                        A few signs along the way{' '}
                        <span aria-hidden="true">+</span>
                      </summary>
                      <p>
                        Clues and answers agree in tense and number. Quotation
                        marks often ask for something you could say. Square
                        brackets can describe a sound or a gesture. A question
                        mark often hints at wordplay. Thursday may ask you to
                        discover a new rule.
                      </p>
                    </details>
                  </div>
                )}
                {step === 4 && (
                  <>
                    <ProfileField draft={draft} update={update} />
                    <div className="future-reflection">
                      <button
                        className="future-text-button"
                        disabled={reflectionState === 'thinking'}
                        onClick={() => void reflect()}
                      >
                        {reflectionState === 'thinking'
                          ? 'Following a few threads…'
                          : 'Let these words wander'}
                        <span aria-hidden="true">✧</span>
                      </button>
                      <span className="future-small" role="status">
                        {reflectionState === 'unavailable'
                          ? 'Local imagination is resting. You’re ready to play.'
                          : draft.reflection
                            ? 'A few extra associations, imagined locally.'
                            : 'An optional detour with your local AI.'}
                      </span>
                    </div>
                    <p className="future-honest-note">
                      Your weekday is ready to play. Your constellation is saved
                      for the personalized puzzles to come.
                    </p>
                  </>
                )}
              </section>
              <footer className="future-navigation">
                <div>
                  {step > 0 && (
                    <button
                      className="future-text-button"
                      onClick={() => update({ step: previousStep })}
                    >
                      <Arrow back />
                      Back
                    </button>
                  )}
                </div>
                <div className="future-forward">
                  {step < 3 && (
                    <button
                      className="future-text-button future-skip"
                      onClick={skip}
                    >
                      {step === 0
                        ? 'Go straight to a puzzle'
                        : 'Let this one pass'}
                    </button>
                  )}
                  <button
                    className="future-primary"
                    disabled={!canContinue}
                    onClick={advance}
                  >
                    {step === 4
                      ? 'Enter crossword'
                      : step === 3
                        ? 'See your beginning'
                        : 'Continue'}
                    <Arrow />
                  </button>
                </div>
              </footer>
              {!storageOkay && (
                <p className="future-storage-warning" role="alert">
                  This browser cannot keep your progress. You can still
                  continue; keep this tab open until your profile is saved to
                  the local server.
                </p>
              )}
            </main>
            <aside className="future-right-rail">
              <div className="future-rail-word" aria-hidden="true">
                DOWN
              </div>
              <div className="future-marginalia">
                <span className="future-tiny-cross" aria-hidden="true">
                  +
                </span>
                <p>
                  {step === 0
                    ? 'Before a word has meaning, something draws us toward it.'
                    : step === 1
                      ? 'Meaning begins in the space between things.'
                      : step === 2
                        ? 'Some words feel familiar before we know why.'
                        : step === 3
                          ? 'A little resistance. Then the pleasure of a way through.'
                          : 'The next word might take you somewhere new.'}
                </p>
                <span className="future-eyebrow">
                  {step === 4
                    ? 'Always unfinished'
                    : 'There is no right answer'}
                </span>
              </div>
            </aside>
          </div>
          <footer className="future-page-footer">
            <span>Made of words. Shaped by you.</span>
            <span>No account. No right answers. Just a beginning.</span>
          </footer>
        </>
      )}
    </div>
  );
}
