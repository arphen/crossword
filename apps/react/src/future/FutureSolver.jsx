import React, {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react';
import { createController } from '../controller';
import { createOptions } from '../behavior/desktop';
import CrosswordView from '../CrosswordView';
import { catalog } from './episteme';
import { describeLegacyPuzzle, FutureSessionRecorder } from './sessionJournal';
import ReflectionCards from './ReflectionCards';
import PostgameAssociations from './PostgameAssociations';
import { loadPostgameAssociations } from './postgame_associations';
import PrivatePuzzleControls from './PrivatePuzzleControls';
import AssistancePanel from './AssistancePanel';
import ClueQualityNotes from './ClueQualityNotes';
import PrivatePuzzleReceipt from './PrivatePuzzleReceipt';
import { restorePrivatePuzzle } from './privatePuzzleStore';
import { createLanguageInputPolicy } from './languageInput';

const reflectionStoragePrefix = 'crossword.future.reflection.';

export function reflectionStorageKey(profileId) {
  return `${reflectionStoragePrefix}${profileId}`;
}

export function reflectionStorageValue(sessionId, puzzleIdentity) {
  if (!sessionId || !puzzleIdentity) return null;
  return JSON.stringify({ version: 1, sessionId, puzzleIdentity });
}

/**
 * Return a finished session only when it belongs to the currently restored
 * puzzle. Older raw session ids are intentionally ignored: they predate the
 * binding and could attach a reflection deck to a different board.
 */
export function savedReflectionSessionId(rawValue, puzzleIdentity) {
  if (typeof rawValue !== 'string' || !puzzleIdentity) return null;
  try {
    const saved = JSON.parse(rawValue);
    if (
      !saved ||
      saved.version !== 1 ||
      typeof saved.sessionId !== 'string' ||
      typeof saved.puzzleIdentity !== 'string' ||
      saved.puzzleIdentity !== puzzleIdentity
    )
      return null;
    return saved.sessionId;
  } catch {
    return null;
  }
}

export function futureOptions(
  dependencies,
  weekday,
  /** @type {(weekday: string) => void} */ onWeekdayChange = () => {},
) {
  const options = /** @type {Record<string, any>} */ (
    createOptions(dependencies)
  );
  // Only startup preferences differ. Every grid, clue, selection, keyboard,
  // check/reveal and multiplayer handler is the daily solver's own handler.
  options.watch.selectedWeekday = (newWeekday) => {
    if (catalog.days.some((day) => day.id === newWeekday)) {
      onWeekdayChange(newWeekday);
    }
  };
  options.computed.weekdayOptions = () =>
    catalog.days.map((day) => ({ value: day.id, label: day.label }));
  const originalData = options.data;
  options.data = () => ({
    ...originalData(),
    selectedWeekday: weekday,
    lastLoadedWeekday: weekday,
    currentPuzzleProvenance: null,
    currentPuzzleTokenManifest: null,
    currentPuzzleRequestSeed: null,
  });
  const dailyLoad = options.methods.loadCrossword;
  options.methods.loadCrossword = function (...args) {
    this.currentPuzzleProvenance = null;
    this.currentPuzzleTokenManifest = null;
    this.currentPuzzleRequestSeed = null;
    return dailyLoad.apply(this, args);
  };
  options.created = /** @this {Record<string, any>} */ function () {
    this.selectedWeekday = weekday;
    window.addEventListener('online', this.handleOnlineStatus);
    window.addEventListener('offline', this.handleOnlineStatus);
    this.isOffline = !navigator.onLine;
    this.updateCachedCounts();
    document.addEventListener('click', this.handleDocumentClick);
    dependencies.socket.on('cell_updated', (data) => {
      if (
        this.grid?.[data.row] &&
        typeof this.grid[data.row][data.col] !== 'undefined'
      )
        this.$set(this.grid[data.row], data.col, data.value);
    });
  };
  return options;
}

const journalMessages = {
  opening: 'Opening this game’s private record…',
  unsupported:
    'This puzzle can still be played, but its format is not yet available for personal history.',
  local: 'This game is being recorded in your browser profile.',
  syncing: 'Saving this game to the local crossword host…',
  saved: 'This game is saved on this device and the local crossword host.',
  offline:
    'Saved in this browser profile; waiting for the local crossword host.',
  conflict: 'The local record needs attention. Your browser copy is safe.',
  rejected: 'The host rejected the record. Your browser copy is safe.',
  'storage-error':
    'The game is still playable, but this action could not be recorded.',
  finished: 'This completed game is saved on the local crossword host.',
};

export default function FutureSolver({
  weekday,
  profileId,
  profileReady,
  onWeekdayChange,
  modelPreference,
  onModelPreferenceChange,
}) {
  const onWeekdayChangeRef = useRef(onWeekdayChange);
  onWeekdayChangeRef.current = onWeekdayChange;
  const [controller] = useState(() =>
    createController((deps) =>
      futureOptions(deps, weekday, (next) => onWeekdayChangeRef.current(next)),
    ),
  );
  useSyncExternalStore(controller.subscribe, controller.snapshot);
  const recorderRef = useRef(null);
  const profileReadyRef = useRef(profileReady);
  const [journalStatus, setJournalStatus] = useState('opening');
  const [finishedSessionId, setFinishedSessionId] = useState(null);
  const [reflectionDeck, setReflectionDeck] = useState(null);
  const [reflectionState, setReflectionState] = useState('idle');
  const [reflectionRetry, setReflectionRetry] = useState(0);
  const [associationDeck, setAssociationDeck] = useState(null);
  const [associationState, setAssociationState] = useState('idle');
  const app = controller.app;
  const puzzleIsCurrent = Boolean(
    app.currentPuzzleMetadata &&
      app.crossword?.length &&
      app.grid?.length,
  );
  const puzzle = puzzleIsCurrent ? describeLegacyPuzzle(app) : null;
  const languageCode =
    app.currentPuzzleProvenance?.languageLearning?.code ??
    app.currentPuzzleProvenance?.languageInterest ??
    null;
  const languageInput = languageCode
    ? createLanguageInputPolicy(languageCode)
    : null;
  const activeEntry =
    puzzleIsCurrent && app.activeClueNumber && app.activeDirection
      ? app.getEntryByClueNumber(app.activeClueNumber, app.activeDirection)
      : null;
  const puzzleKey = puzzle
    ? JSON.stringify({
        edition: puzzle.edition,
        puzzleHash: puzzle.puzzleHash || null,
        provenance: app.currentPuzzleProvenance?.source || null,
        requestSeed: app.currentPuzzleRequestSeed ?? null,
    })
    : '';
  // Manifest-backed editions use their answer-bearing digest. Legacy daily
  // editions fall back to their stable clue/topology descriptor so recovery
  // still cannot cross wires when no token manifest is available.
  const puzzleIdentity = puzzle
    ? puzzle.puzzleHash || JSON.stringify(puzzle.edition)
    : null;
  const displayWeekday =
    catalog.days.find((day) => day.id === weekday)?.label || weekday;

  async function enableHostSync(
    readiness,
    expectedRecorder = recorderRef.current,
  ) {
    if (!readiness) return;
    let saved = false;
    try {
      saved = await readiness;
    } catch {
      saved = false;
    }
    if (
      !saved ||
      !expectedRecorder ||
      expectedRecorder.destroyed ||
      recorderRef.current !== expectedRecorder
    )
      return;
    expectedRecorder.fetchImpl = globalThis.fetch?.bind(globalThis);
    await expectedRecorder.flush();
  }

  useLayoutEffect(() => controller.flush());
  useEffect(() => {
    controller.start();
    return () => controller.dispose();
  }, [controller]);
  useEffect(() => {
    if (
      !profileId ||
      app.currentPuzzleMetadata ||
      app.crossword?.length
    ) {
      return;
    }
    if (restorePrivatePuzzle(app, profileId)) controller.flush();
  }, [app, controller, profileId]);
  useEffect(() => {
    if (!profileId || !puzzleIdentity) {
      setFinishedSessionId(null);
      return;
    }
    try {
      const previousSession = savedReflectionSessionId(
        window.localStorage.getItem(reflectionStorageKey(profileId)),
        puzzleIdentity,
      );
      setFinishedSessionId(previousSession);
    } catch {
      // Reflection availability should not depend on localStorage.
      setFinishedSessionId(null);
    }
  }, [profileId, puzzleIdentity]);
  useEffect(() => {
    if (!profileId || !puzzle || !puzzleKey) return undefined;
    let active = true;
    let recorder;
    let handleOnline;
    let handleVisibility;
    setJournalStatus('opening');
    Promise.resolve().then(async () => {
      if (!active) return;
      recorder = new FutureSessionRecorder({
        profileId,
        puzzle,
        // Host session creation requires the starting profile to exist first.
        // Keep this recorder local until FutureApp confirms that save, then
        // enable the outbox transport in enableHostSync below.
        fetchImpl: null,
        onStatus: (state) => {
          if (active) setJournalStatus(state);
          if (state === 'finished' && recorder?.session?.sessionId) {
            const sessionId = recorder.session.sessionId;
            setFinishedSessionId(sessionId);
            const storedReflection = reflectionStorageValue(
              sessionId,
              puzzleIdentity,
            );
            if (storedReflection) {
              try {
                window.localStorage.setItem(
                  reflectionStorageKey(profileId),
                  storedReflection,
                );
              } catch {
                // The finished session remains available on the host.
              }
            }
          }
        },
      });
      recorderRef.current = recorder;
      try {
        await recorder.start(app);
        controller.flush();
        if (!active) return;
        handleOnline = () => recorder.flush();
        handleVisibility = () =>
          recorder.visibilityChanged(document.visibilityState === 'visible');
        window.addEventListener('online', handleOnline);
        document.addEventListener('visibilitychange', handleVisibility);
        void enableHostSync(profileReadyRef.current, recorder);
      } catch {
        if (active) setJournalStatus('storage-error');
      }
    });
    return () => {
      active = false;
      if (handleOnline) window.removeEventListener('online', handleOnline);
      if (handleVisibility)
        document.removeEventListener('visibilitychange', handleVisibility);
      if (recorderRef.current === recorder) recorderRef.current = null;
      recorder?.dispose();
    };
  }, [profileId, puzzleKey, app, controller]);

  useEffect(() => {
    profileReadyRef.current = profileReady;
    void enableHostSync(profileReady);
  }, [profileReady]);

  useEffect(() => {
    if (!finishedSessionId) return undefined;
    const abort = new AbortController();
    setReflectionState('loading');
    setReflectionDeck(null);
    Promise.resolve().then(async () => {
      try {
        const response = await fetch(
          `/api/future/sessions/${finishedSessionId}/reflections`,
          {
            signal: abort.signal,
            cache: 'no-store',
          },
        );
        const result = await response.json();
        const cards = result?.deck?.cards;
        if (
          !response.ok ||
          result.deck?.sessionId !== finishedSessionId ||
          !Array.isArray(cards) ||
          cards.length !== 3 ||
          cards.some(
            (card) =>
              card?.status !== 'approved' ||
              typeof card.cardId !== 'string' ||
              typeof card.text !== 'string',
          )
        ) {
          throw new Error(
            result?.error || 'The reflection deck could not be loaded.',
          );
        }
        const deck = {
          ...result.deck,
          responses: Array.isArray(result.responses) ? result.responses : [],
          analysisSummary: result.analysisSummary || null,
        };
        if (!abort.signal.aborted) {
          setReflectionDeck(deck);
          setReflectionState('ready');
        }
      } catch {
        if (!abort.signal.aborted) setReflectionState('unavailable');
      }
    });
    return () => abort.abort();
  }, [finishedSessionId, reflectionRetry]);

  useEffect(() => {
    // Association paths are an independent, optional postgame lane. A
    // missing reflection deck must not suppress them after a finished game.
    if (!finishedSessionId || !['ready', 'unavailable'].includes(reflectionState)) return undefined;
    const abort = new AbortController();
    setAssociationState('loading');
    setAssociationDeck(null);
    Promise.resolve().then(async () => {
      try {
        const result = await loadPostgameAssociations(finishedSessionId, {
          signal: abort.signal,
        });
        if (abort.signal.aborted) return;
        if (result.status === 'unavailable') {
          setAssociationState('unavailable');
          return;
        }
        if (!Array.isArray(result.paths) || result.paths.length === 0) {
          setAssociationState('empty');
          return;
        }
        setAssociationDeck(result);
        setAssociationState('ready');
      } catch {
        if (!abort.signal.aborted) setAssociationState('unavailable');
      }
    });
    return () => abort.abort();
  }, [finishedSessionId, reflectionState]);

  const onEntryFocused = (entry, reason) =>
    recorderRef.current?.focus(entry, app, reason);
  const onCellChanged = (change) =>
    recorderRef.current?.cellChanged(change, app);
  const onCheckAll = () => recorderRef.current?.checked(app);
  const onRevealAll = (before) =>
    recorderRef.current?.revealed(
      before,
      new Map(
        app.grid.flatMap((row, rowIndex) =>
          row.flatMap((value, cellIndex) =>
            value === null
              ? []
              : [[`r${rowIndex}c${cellIndex}`, value ? String(value) : null]],
          ),
        ),
      ),
    );
  const onCellRevealed = (cell, currentApp) =>
    recorderRef.current?.revealCell(cell, currentApp);
  const onHintShown = (hint) => recorderRef.current?.hintShown(hint);

  return (
    <>
      <PrivatePuzzleControls
        app={app}
        profileId={profileId}
        profileReady={profileReady}
        weekday={weekday}
        onWeekdayChange={onWeekdayChange}
        modelPreference={modelPreference}
        onModelPreferenceChange={onModelPreferenceChange}
        onPuzzleRestored={() => controller.flush()}
      />
      {puzzleIsCurrent ? (
        <CrosswordView
          app={app}
          languageInput={languageInput}
          onEntryFocused={onEntryFocused}
          onCellChanged={onCellChanged}
          onCheckAll={onCheckAll}
          onRevealAll={onRevealAll}
          onCellRevealed={onCellRevealed}
          onComplete={() => recorderRef.current?.finish('complete')}
          displayWeekday={displayWeekday}
          annotateClueGrammar
        />
      ) : (
        <section className="future-first-puzzle" aria-live="polite">
          <span className="future-eyebrow">A board without a borrowed beginning</span>
          <h2>Your word field is ready to become a crossword.</h2>
          <p>
            The local model will choose a few threads from your opening and
            build a fresh grid around them. Nothing leaves this device.
          </p>
        </section>
      )}
      {puzzleIsCurrent && (
        <AssistancePanel
          app={app}
          entry={activeEntry}
          onHintShown={onHintShown}
          onCellRevealed={onCellRevealed}
        />
      )}
      {puzzleIsCurrent && (
        <ClueQualityNotes
          provenance={app.currentPuzzleProvenance}
          entries={app.crossword}
          profileId={profileId}
        />
      )}
      <div
        className="future-journal-status"
        role="status"
        aria-live="polite"
        data-state={journalStatus}
      >
        <span className="future-status-dot" aria-hidden="true" />
        {puzzleIsCurrent
          ? journalMessages[journalStatus] || journalMessages.opening
          : 'Your personal solve history will begin with this puzzle.'}
      </div>
      {reflectionState === 'loading' && (
        <p className="future-reflection-loading" role="status">
          Gathering a few last impressions from this puzzle…
        </p>
      )}
      {reflectionState === 'unavailable' && (
        <div className="future-reflection-retry" role="status">
          <span>The reflection cards are unavailable right now.</span>
          <button onClick={() => setReflectionRetry((value) => value + 1)}>
            Try again
          </button>
        </div>
      )}
      {reflectionState === 'ready' && reflectionDeck && (
        <ReflectionCards key={reflectionDeck.sessionId} deck={reflectionDeck} />
      )}
      {finishedSessionId && profileId && (
        <PrivatePuzzleReceipt
          key={`receipt-${finishedSessionId}`}
          sessionId={finishedSessionId}
          profileId={profileId}
        />
      )}
      {associationState === 'loading' && (
        <p className="future-reflection-loading" role="status">
          Following a few threads from this game…
        </p>
      )}
      {associationState === 'unavailable' && (
        <p className="future-reflection-loading" role="status">
          The game was saved; its optional word paths can appear after the
          local model is available.
        </p>
      )}
      {associationState === 'ready' && associationDeck && (
        <PostgameAssociations
          key={`postgame-${associationDeck.sessionId}`}
          deck={associationDeck}
        />
      )}
    </>
  );
}
