import { useEffect, useMemo, useRef, useState } from 'react';
import {
  checkSession,
  clearCell,
  createRealPuzzle,
  enterLetter,
  enterRebus,
  indexPuzzle,
  moveSelection,
  pauseSession,
  revealCell,
  resumeSession,
  selectCell,
  touchSession,
  toggleDirection,
  updateActiveTime,
  type CellId,
  type Direction,
  type Entry,
  type PuzzleDocument,
  type SolveSessionSnapshot
} from '@crossword/domain';
import { createSessionUseCases } from '@crossword/application';
import {
  createContinuityExport,
  createIndexedDbContinuityRepository,
  createIndexedDbSessionRepository,
  parseContinuityExport
} from '@crossword/persistence';
import type { ModelState } from '@crossword/model-runtime';
import { ClueColumn } from './components/legacy/ClueColumn';
import { LegacyGrid } from './components/legacy/LegacyGrid';
import { SolveClock } from './components/SolveClock';
import { createBrowserModelWorkerClient, type ModelWorkerClient } from './workers/modelClient';
import { browserRuntimeProbe, localModelManifest } from './modelConfig';
import { createNytCrosswordClient, type NytWeekday } from './nytApi';

const initialPuzzle = createRealPuzzle();
const initialIndex = indexPuzzle(initialPuzzle);
const sessionUseCases = createSessionUseCases(createIndexedDbSessionRepository());
const nytClient = createNytCrosswordClient();
const continuityRepository = createIndexedDbContinuityRepository();

function focusInput(cellId: CellId) {
  // scoped to the grid: clue-column answer cells share data-cell-id
  document
    .querySelector<HTMLInputElement>(`#crossword-container input[data-cell-id="${cellId}"]`)
    ?.focus({ preventScroll: true });
}

function App() {
  const [puzzle, setPuzzle] = useState<PuzzleDocument>(initialPuzzle);
  const index = useMemo(() => indexPuzzle(puzzle), [puzzle]);
  const [session, setSession] = useState<SolveSessionSnapshot>(() =>
    sessionUseCases.restart(initialPuzzle, initialIndex, Date.now())
  );
  const [incorrectCellIds, setIncorrectCellIds] = useState<readonly CellId[]>([]);
  const [checking, setChecking] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);
  const [dataNotice, setDataNotice] = useState('');
  const [weekday, setWeekday] = useState<NytWeekday>('monday');
  const [puzzleLoading, setPuzzleLoading] = useState(false);
  const [isDarkMode, setDarkMode] = useState<boolean>(() => {
    try {
      return localStorage.getItem('crossword-dark') === '1';
    } catch {
      return false;
    }
  });
  const [modelState, setModelState] = useState<ModelState>('uninstalled');
  const [modelBusy, setModelBusy] = useState(false);
  const modelClientRef = useRef<ModelWorkerClient | null>(null);
  const [showSolvedModal, setShowSolvedModal] = useState(false);
  const [solvedList, setSolvedList] = useState<readonly { id: string; title: string; activeMs: number; completedAt: string }[]>(
    () => {
      try {
        return JSON.parse(localStorage.getItem('crossword-solved') ?? '[]');
      } catch {
        return [];
      }
    }
  );

  useEffect(() => {
    let cancelled = false;
    sessionUseCases.load(puzzle, index)
      .then((loaded) => {
        if (!cancelled) setSession(loaded);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [index, puzzle]);

  useEffect(() => () => modelClientRef.current?.dispose(), []);

  // completion flow: when the grid fills (or the owner marks it complete),
  // record the solve and open the solved modal
  const completedRecorded = useRef('');
  function recordCompletion(force = false) {
    if (!force && session.status !== 'complete') return;
    setShowSolvedModal(true);
    if (!force && completedRecorded.current === puzzle.id) return;
    completedRecorded.current = puzzle.id;
    const record = {
      id: puzzle.id,
      title: puzzle.title,
      activeMs: session.activeMs,
      completedAt: new Date().toISOString()
    };
    setSolvedList((current) => {
      const next = [record, ...current.filter((item) => item.id !== puzzle.id)].slice(0, 50);
      try {
        localStorage.setItem('crossword-solved', JSON.stringify(next));
      } catch {
        // restricted storage: the modal still shows this session
      }
      return next;
    });
  }

  useEffect(() => {
    if (session.status === 'complete') recordCompletion();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.status]);

  // legacy hook: body[data-active-direction] drives the grid highlight
  // color (blue when Down is active, orange otherwise)
  useEffect(() => {
    document.body.dataset.activeDirection = session.selection.direction;
  }, [session.selection.direction]);

  // legacy night-mode mechanism: color-scheme on :root flips the ported
  // stylesheet's dark tokens
  useEffect(() => {
    document.documentElement.style.colorScheme = isDarkMode ? 'dark' : 'light';
    try {
      localStorage.setItem('crossword-dark', isDarkMode ? '1' : '0');
    } catch {
      // restricted storage: night mode still applies for this session
    }
  }, [isDarkMode]);

  // Roving focus inside the grid only: after arrows, focus follows the
  // selection. Clue-list clicks focus manually (focus starts outside).
  const selectedCellId = session.selection.cellId;
  useEffect(() => {
    if (!selectedCellId) return;
    const active = document.activeElement;
    if (active instanceof HTMLInputElement && active.closest('#crossword-container')) {
      focusInput(selectedCellId);
    }
  }, [selectedCellId]);

  useEffect(() => {
    const persist = () => {
      const stamped = updateActiveTime(session, Date.now());
      void sessionUseCases.save(puzzle, index, stamped).catch(() => undefined);
    };
    const timer = window.setTimeout(persist, 250);
    const flush = () => persist();
    document.addEventListener('visibilitychange', flush);
    window.addEventListener('pagehide', flush);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener('visibilitychange', flush);
      window.removeEventListener('pagehide', flush);
    };
  }, [session, puzzle, index]);

  const acrossEntries = puzzle.entries.filter((entry) => entry.direction === 'across');
  const downEntries = puzzle.entries.filter((entry) => entry.direction === 'down');

  const solvedCount = puzzle.entries.filter((entry) =>
    entry.cellIds.every((cellId) => Boolean(session.entered[cellId]))
  ).length;
  const totalEntries = puzzle.entries.length;
  const halfCompleted = totalEntries > 0 && solvedCount / totalEntries >= 0.5;
  const checksUsed = session.events.filter((event) => event.type === 'checked').length;
  const revealsUsed = session.events.filter((event) => event.type === 'revealed').length;
  const score = Math.max(0, 100 - checksUsed * 5 - revealsUsed * 10);

  function handleSelectCell(cellId: CellId) {
    // already selected (native focus after a move): do not re-enter state
    if (session.selection.cellId === cellId) return;
    const current: Direction = session.selection.direction;
    const keepsDirection = index.entryAt.get(cellId)?.[current];
    const nextDirection: Direction = keepsDirection
      ? current
      : index.entryAt.get(cellId)?.across
        ? 'across'
        : 'down';
    setSession((currentSession) => selectCell(touchSession(currentSession, Date.now()), index, cellId, nextDirection));
  }

  function handleSelectEntry(entry: Entry) {
    const cellId = entry.cellIds.find((candidate) => !session.entered[candidate]) ?? entry.cellIds[0];
    if (!cellId) return;
    setSession((current) => selectCell(touchSession(current, Date.now()), index, cellId, entry.direction));
    focusInput(cellId);
  }

  function handleSelectPattern(entry: Entry, position: number) {
    const cellId = entry.cellIds[position];
    if (!cellId) return;
    setSession((current) => selectCell(touchSession(current, Date.now()), index, cellId, entry.direction));
    focusInput(cellId);
  }

  function handleEnterRebus(token: string) {
    setChecking(false);
    setSession((current) => enterRebus(touchSession(current, Date.now()), puzzle, index, token));
  }

  function handleEnter(letter: string) {
    setChecking(false);
    setSession((current) => enterLetter(touchSession(current, Date.now()), puzzle, index, letter));
  }

  function handleClear() {
    setChecking(false);
    setSession((current) => clearCell(touchSession(current, Date.now()), puzzle, index));
  }

  function handleMove(key: 'ArrowUp' | 'ArrowDown' | 'ArrowLeft' | 'ArrowRight') {
    setSession((current) => moveSelection(touchSession(current, Date.now()), puzzle, index, key));
  }

  function handleToggleDirection() {
    setSession((current) => toggleDirection(touchSession(current, Date.now()), index));
  }

  function handleCheckAll() {
    const result = checkSession(touchSession(session, Date.now()), puzzle, index, 'puzzle');
    setSession(result.snapshot);
    setIncorrectCellIds(result.incorrectCellIds);
    setChecking(true);
  }

  function handleRevealAll() {
    if (!window.confirm('Reveal the entire grid? This counts as assistance.')) return;
    setSession((current) => revealCell(touchSession(current, Date.now()), puzzle, index, 'puzzle'));
    setChecking(false);
  }

  function handlePauseToggle() {
    setSession((current) => current.paused ? resumeSession(current, Date.now()) : pauseSession(current, Date.now()));
  }

  function replacePuzzle(nextPuzzle: PuzzleDocument, notice: string) {
    setPuzzle(nextPuzzle);
    setSession(sessionUseCases.restart(nextPuzzle, indexPuzzle(nextPuzzle), Date.now()));
    setIncorrectCellIds([]);
    setChecking(false);
    setDataNotice(notice);
  }

  async function handleExport() {
    try {
      const serialized = await createContinuityExport({
        preferences: { theme: isDarkMode ? 'dark' : 'light' },
        profiles: {},
        puzzles: [puzzle],
        sessions: [session],
        events: session.events
      });
      const url = URL.createObjectURL(new Blob([serialized], { type: 'application/json' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = `crossword-${puzzle.id}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setDataNotice('Continuity archive exported.');
    } catch (error) {
      setDataNotice(error instanceof Error ? error.message : 'Export failed.');
    }
  }

  async function handleImport(file: File) {
    try {
      const archive = await parseContinuityExport(await file.text());
      const imported = archive.sessions.find((candidate) => candidate.puzzleId === puzzle.id);
      if (!imported) throw new Error('This archive does not contain a session for this puzzle.');
      const restored = sessionUseCases.restore(puzzle, index, imported);
      await continuityRepository.replace(JSON.stringify(archive));
      setSession(restored);
      setDataNotice('Continuity archive imported.');
    } catch (error) {
      setDataNotice(error instanceof Error ? error.message : 'Import failed.');
    }
  }

  async function handleLoadWeekday() {
    setPuzzleLoading(true);
    try {
      const nextPuzzle = await nytClient.loadRandom(weekday);
      replacePuzzle(nextPuzzle, `Loaded a ${weekday} puzzle.`);
    } catch (error) {
      setDataNotice(error instanceof Error ? error.message : 'Puzzle loading failed.');
    } finally {
      setPuzzleLoading(false);
    }
  }

  async function handleModelInstall() {
    setModelBusy(true);
    try {
      const estimate = await navigator.storage?.estimate();
      const probe = {
        ...browserRuntimeProbe(),
        storageQuotaBytes: estimate?.quota ?? 0,
        storageUsageBytes: estimate?.usage ?? 0
      };
      const client = modelClientRef.current ?? (modelClientRef.current = createBrowserModelWorkerClient());
      const configured = await client.configure({ manifest: localModelManifest, runtime: probe });
      if (!configured.ok) throw new Error(configured.error.message);
      const installed = await client.install(new AbortController().signal);
      if (!installed.ok) throw new Error(installed.error.message);
      setModelState('installed');
      const loaded = await client.load(new AbortController().signal);
      if (!loaded.ok) throw new Error(loaded.error.message);
      setModelState('loaded');
      setDataNotice('Local model loaded. Original construction is available to the queue.');
    } catch (error) {
      setDataNotice(error instanceof Error ? error.message : 'Local model setup failed.');
      setModelState(modelClientRef.current?.state() ?? 'uninstalled');
    } finally {
      setModelBusy(false);
    }
  }

  async function handleModelUnload() {
    const client = modelClientRef.current;
    if (!client) return;
    setModelBusy(true);
    try {
      const result = await client.unload();
      if (result.ok) {
        setModelState('installed');
        setDataNotice('Local model unloaded. Solving remains offline.');
      } else {
        setDataNotice(result.error.message);
      }
    } catch (error) {
      setDataNotice(error instanceof Error ? error.message : 'Local model unload failed.');
    } finally {
      setModelBusy(false);
    }
  }

  const infoAuthors = puzzle.provenance.records[0]?.source ?? 'local construction';
  // legacy red/green check marks show only while checking, cleared on edit
  const checkingIncorrect = checking ? incorrectCellIds : [];
  const checkingCorrect = checking ? session.checkedCellIds : [];

  return (
    <div id="app" className={halfCompleted ? 'half-completed' : ''}>
      <div id="notmenu">
        <ClueColumn
          checkedCellIds={checkingCorrect}
          direction="across"
          entries={acrossEntries}
          incorrectCellIds={checkingIncorrect}
          index={index}
          label="ACROSS"
          onSelectEntry={handleSelectEntry}
          onSelectPattern={handleSelectPattern}
          session={session}
        />

        <div className="center-column">
          <div id="menu-top" className="menu-section">
            <div className="menu-row info-bar">
              <span className="puzzle-date">{puzzle.id.replace(/^nyt-/, '')}</span>
              <span className="puzzle-separator">•</span>
              <span className="puzzle-weekday">{puzzle.provenance.source === 'import' ? 'imported' : 'original'}</span>
              <span className="puzzle-separator">•</span>
              <span className="puzzle-authors" title={infoAuthors}>{infoAuthors}</span>
              {puzzle.subtitle && <div className="puzzle-notepad">{puzzle.subtitle}</div>}
            </div>

            <div className="menu-row indicator-bar">
              <div className="stat-item blue-stat">
                <span className="stat-label">Completed</span>
                <span className="stat-value">{solvedCount} / {totalEntries}</span>
              </div>
              <div className="stat-item blue-stat">
                <span className="stat-label">Checks</span>
                <span className="stat-value">{checksUsed}</span>
              </div>
              <div className="stat-item blue-stat">
                <span className="stat-label">Reveals</span>
                <span className="stat-value">{revealsUsed}</span>
              </div>
              <div className="stat-item orange-stat">
                <span className="stat-label">Score</span>
                <span className="stat-value">{score}</span>
              </div>
              <div className="stat-item orange-stat">
                <span className="stat-label">Time</span>
                <span className="stat-value">
                  <SolveClock
                    activeMs={session.activeMs}
                    lastClockAtMs={session.lastClockAtMs}
                    lastInteractionAtMs={session.lastInteractionAtMs}
                    paused={session.paused}
                  />
                </span>
              </div>
              <button className="action-button blue-action" type="button" onClick={handlePauseToggle}>
                {session.paused ? 'Resume' : 'Pause'}
              </button>
            </div>

            <div className="menu-row action-bar">
              <button className="action-button blue-action" id="check-all" title="Check all" type="button" onClick={handleCheckAll}>
                <span>Check</span>
              </button>
              <button className="action-button blue-action" id="reveal-all" title="Reveal all" type="button" onClick={handleRevealAll}>
                <span>Reveal</span>
              </button>
              <button className="action-button orange-action" id="complete-button" title="Mark as Complete" type="button" onClick={() => recordCompletion(true)}>
                <span>Complete</span>
              </button>
            </div>
          </div>

          <LegacyGrid
            checkedCellIds={checkingCorrect}
            index={index}
            incorrectCellIds={checkingIncorrect}
            onClear={handleClear}
            onEnter={handleEnter}
            onEnterRebus={handleEnterRebus}
            onMove={handleMove}
            onSelectCell={handleSelectCell}
            onToggleDirection={handleToggleDirection}
            puzzle={puzzle}
            session={session}
          />

          <div id="menu-bottom" className="menu-section">
            <div className="menu-row selection-row">
              <div className="field-group weekday-group">
                <label className="field-label" htmlFor="weekday-select">Weekday</label>
                <div className="select-wrapper">
                  <select
                    id="weekday-select"
                    onChange={(event) => setWeekday(event.target.value as NytWeekday)}
                    value={weekday}
                  >
                    {['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].map((option) => (
                      <option key={option} value={option}>{option.charAt(0).toUpperCase() + option.slice(1)}</option>
                    ))}
                  </select>
                </div>
              </div>
              <button aria-label="Get new puzzle" disabled={puzzleLoading} id="get-puzzle-button" type="button" onClick={handleLoadWeekday}>
                {puzzleLoading ? '…' : '→'}
              </button>
              <button className="action-button blue-action" title="Export continuity archive" type="button" onClick={handleExport}>
                Export
              </button>
              <button
                className="action-button blue-action"
                title="Import continuity archive"
                type="button"
                onClick={() => document.getElementById('import-archive-input')?.click()}
              >
                Import
              </button>
              <input
                accept="application/json,.json"
                aria-label="Import continuity archive"
                id="import-archive-input"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void handleImport(file);
                  event.target.value = '';
                }}
                style={{ display: 'none' }}
                type="file"
              />
              <div className="menu-spacer" />
              <button className="icon-button" title="Solved puzzles" type="button" onClick={() => setShowSolvedModal(true)}>S</button>
              <button className="icon-button" title="Model setup" type="button" onClick={() => setSetupOpen(true)}>M</button>
              <div className="theme-switch">
                <label className="switch">
                  <input
                    aria-label="Toggle dark mode"
                    checked={isDarkMode}
                    onChange={(event) => setDarkMode(event.target.checked)}
                    type="checkbox"
                  />
                  <span>{isDarkMode ? 'Night' : 'Day'}</span>
                </label>
              </div>
            </div>
          </div>
        </div>

        <ClueColumn
          checkedCellIds={checkingCorrect}
          direction="down"
          entries={downEntries}
          incorrectCellIds={checkingIncorrect}
          index={index}
          label="DOWN"
          onSelectEntry={handleSelectEntry}
          onSelectPattern={handleSelectPattern}
          session={session}
        />
      </div>

      {dataNotice && <p className="data-notice" role="status">{dataNotice}</p>}

      {showSolvedModal && (
        <div
          className="modal-overlay"
          onClick={(event) => { if (event.target === event.currentTarget) setShowSolvedModal(false); }}
          onKeyDown={(event) => { if (event.key === 'Escape') setShowSolvedModal(false); }}
        >
          <div aria-labelledby="solved-modal-title" aria-modal="true" className="modal-content" role="dialog">
            <div className="modal-header">
              <h2 id="solved-modal-title">Solved puzzles</h2>
              <button
                autoFocus
                className="modal-close-button"
                type="button"
                aria-label="Close solved puzzles"
                onClick={() => setShowSolvedModal(false)}
              >
                &times;
              </button>
            </div>
            <div className="modal-body">
              {session.status === 'complete' && (
                <p><strong>{puzzle.title}</strong> — complete in {Math.round(session.activeMs / 1000)}s with {checksUsed} checks and {revealsUsed} reveals.</p>
              )}
              {solvedList.length === 0 && <p>No solved puzzles yet.</p>}
              {solvedList.length > 0 && (
                <ul className="solved-puzzles-list">
                  {solvedList.map((item) => (
                    <li className="solved-puzzle-item" key={item.id + item.completedAt}>
                      <div className="puzzle-info">
                        <div className="puzzle-header">
                          <strong className="puzzle-title">{item.title}</strong>
                          <span className="puzzle-date">{new Date(item.completedAt).toLocaleString()}</span>
                        </div>
                        <span className="puzzle-authors">{Math.round(item.activeMs / 1000)}s</span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              <div className="setup-actions">
                <button className="action-button blue-action" type="button" onClick={() => { void handleLoadWeekday(); setShowSolvedModal(false); }}>
                  New {weekday} puzzle
                </button>
                <button className="action-button" type="button" onClick={() => setShowSolvedModal(false)}>Close</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {setupOpen && (
        <div
          className="modal-overlay"
          onClick={(event) => { if (event.target === event.currentTarget) setSetupOpen(false); }}
          onKeyDown={(event) => { if (event.key === 'Escape') setSetupOpen(false); }}
        >
          <div aria-labelledby="setup-title" aria-modal="true" className="modal-content" role="dialog">
            <div className="modal-header">
              <h2 id="setup-title">Model setup</h2>
              <button
                autoFocus
                className="modal-close-button"
                type="button"
                aria-label="Close model setup"
                onClick={() => setSetupOpen(false)}
              >
                &times;
              </button>
            </div>
            <div className="modal-body">
              <p>Original construction stays on this device. WebGPU in-browser via the pinned local model — no server, no cloud inference.</p>
              <div className="setup-status"><span /> Local model {modelState}</div>
              <div className="setup-actions">
                <button
                  className="action-button blue-action"
                  disabled={modelBusy || modelState === 'loaded'}
                  type="button"
                  onClick={handleModelInstall}
                >
                  {modelBusy ? 'Working…' : modelState === 'installed' ? 'Load model' : 'Install model'}
                </button>
                <button
                  className="action-button"
                  disabled={modelBusy || modelState !== 'loaded'}
                  type="button"
                  onClick={handleModelUnload}
                >
                  Unload
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
