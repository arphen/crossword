import {
  getCellPosition,
  getEntryForCell,
  type CellId,
  type Direction,
  type Entry,
  type EntryId,
  type PuzzleDocument,
  type PuzzleIndex
} from './puzzle';
import type { ClueMechanism } from './puzzle';

export type Selection = Readonly<{
  cellId: CellId;
  direction: Direction;
  entryId: EntryId;
}>;

export type SessionStatus = 'in-progress' | 'complete';
export type MoveKey = 'ArrowUp' | 'ArrowDown' | 'ArrowLeft' | 'ArrowRight';
export type EntryStep = 'next' | 'previous';
export type CheckScope = 'cell' | 'entry' | 'puzzle';
export type SessionEventType =
  | 'session-started'
  | 'cell-entered'
  | 'cell-cleared'
  | 'checked'
  | 'revealed'
  | 'nudged'
  | 'paused'
  | 'resumed'
  | 'completed';

export type SolveEvent = Readonly<{
  id: string;
  type: SessionEventType;
  atMs: number;
  cellId?: CellId;
  entryId?: EntryId;
  scope?: CheckScope;
  value?: string;
}>;

export type SolveSessionSnapshot = Readonly<{
  puzzleId: string;
  entered: Readonly<Record<string, string>>;
  selection: Selection;
  checkedCellIds: readonly CellId[];
  revealedCellIds: readonly CellId[];
  clueVariantByEntryId: Readonly<Record<string, ClueMechanism>>;
  events: readonly SolveEvent[];
  startedAtMs: number;
  activeMs: number;
  lastClockAtMs: number;
  lastInteractionAtMs: number;
  paused: boolean;
  assistanceCount: number;
  status: SessionStatus;
}>;

export type CheckResult = Readonly<{
  snapshot: SolveSessionSnapshot;
  incorrectCellIds: readonly CellId[];
  checkedCellIds: readonly CellId[];
}>;

const emptyLetters = (puzzle: PuzzleDocument): Record<string, string> =>
  Object.fromEntries(puzzle.cells.filter((cell) => !cell.block).map((cell) => [cell.id, '']));

const uniqueCellIds = (cellIds: readonly CellId[]): CellId[] => [...new Set(cellIds)];

const sessionEventTypes: readonly SessionEventType[] = [
  'session-started',
  'cell-entered',
  'cell-cleared',
  'checked',
  'revealed',
  'nudged',
  'paused',
  'resumed',
  'completed'
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isStringRecord(value: unknown): value is Record<string, string> {
  return isRecord(value) && Object.values(value).every((item) => typeof item === 'string');
}

export function validateSolveEvent(value: unknown): value is SolveEvent {
  if (!isRecord(value) || typeof value.id !== 'string' || !sessionEventTypes.includes(value.type as SessionEventType) || !isFiniteNumber(value.atMs)) return false;
  if (value.cellId !== undefined && typeof value.cellId !== 'string') return false;
  if (value.entryId !== undefined && typeof value.entryId !== 'string') return false;
  if (value.scope !== undefined && !['cell', 'entry', 'puzzle'].includes(value.scope as string)) return false;
  return value.value === undefined || typeof value.value === 'string';
}

export function validateSessionSnapshot(value: unknown): value is SolveSessionSnapshot {
  if (!isRecord(value) || typeof value.puzzleId !== 'string' || !isStringRecord(value.entered)) return false;
  if (!isRecord(value.selection) || typeof value.selection.cellId !== 'string' || !['across', 'down'].includes(value.selection.direction as string) || typeof value.selection.entryId !== 'string') return false;
  if (!Array.isArray(value.checkedCellIds) || !value.checkedCellIds.every((cellId) => typeof cellId === 'string')) return false;
  if (!Array.isArray(value.revealedCellIds) || !value.revealedCellIds.every((cellId) => typeof cellId === 'string')) return false;
  if (!isStringRecord(value.clueVariantByEntryId) || !Object.values(value.clueVariantByEntryId).every((mechanism) => ['direct', 'standard', 'oblique', 'nudge'].includes(mechanism))) return false;
  if (!Array.isArray(value.events) || !value.events.every(validateSolveEvent)) return false;
  if (!isFiniteNumber(value.startedAtMs) || !isFiniteNumber(value.activeMs) || !isFiniteNumber(value.lastClockAtMs) || !isFiniteNumber(value.lastInteractionAtMs) || !isFiniteNumber(value.assistanceCount)) return false;
  if (value.activeMs < 0 || value.assistanceCount < 0 || !Number.isInteger(value.assistanceCount)) return false;
  return typeof value.paused === 'boolean' && ['in-progress', 'complete'].includes(value.status as string);
}

function firstSelection(puzzle: PuzzleDocument, index: PuzzleIndex): Selection {
  const entry = puzzle.entries.find((candidate) => candidate.direction === 'across');
  if (!entry) {
    throw new Error('Puzzle has no across entry');
  }
  const cellId = entry.cellIds[0];
  if (!cellId || !getEntryForCell(index, cellId, 'across')) {
    throw new Error('Puzzle has no selectable starting cell');
  }
  return { cellId, direction: 'across', entryId: entry.id };
}

export function createSession(
  puzzle: PuzzleDocument,
  index: PuzzleIndex,
  startedAtMs = 0
): SolveSessionSnapshot {
  const startedEvent: SolveEvent = {
    id: `session-started:${startedAtMs}`,
    type: 'session-started',
    atMs: startedAtMs
  };
  return {
    puzzleId: puzzle.id,
    entered: emptyLetters(puzzle),
    selection: firstSelection(puzzle, index),
    checkedCellIds: [],
    revealedCellIds: [],
    clueVariantByEntryId: {},
    events: [startedEvent],
    startedAtMs,
    activeMs: 0,
    lastClockAtMs: startedAtMs,
    lastInteractionAtMs: startedAtMs,
    paused: false,
    assistanceCount: 0,
    status: 'in-progress'
  };
}

function addEvent(
  snapshot: SolveSessionSnapshot,
  type: SessionEventType,
  atMs: number,
  details: Omit<SolveEvent, 'id' | 'type' | 'atMs'> = {}
): SolveSessionSnapshot {
  const event: SolveEvent = {
    ...details,
    id: `${type}:${atMs}:${snapshot.events.length}`,
    type,
    atMs
  };
  return { ...snapshot, events: [...snapshot.events, event] };
}

function withStatus(snapshot: SolveSessionSnapshot, puzzle: PuzzleDocument): SolveSessionSnapshot {
  const complete = puzzle.cells
    .filter((cell) => !cell.block)
    .every((cell) => snapshot.entered[cell.id] === answerAt(puzzle, cell.id));
  const next: SolveSessionSnapshot = {
    ...snapshot,
    status: complete ? 'complete' : 'in-progress'
  };
  return complete && snapshot.status !== 'complete'
    ? addEvent(next, 'completed', snapshot.lastInteractionAtMs)
    : next;
}

function answerAt(puzzle: PuzzleDocument, cellId: CellId): string {
  const entry = puzzle.entries.find((candidate) => candidate.cellIds.includes(cellId));
  if (!entry) {
    throw new Error(`Cell ${cellId} is not part of an entry`);
  }
  const position = getCellPosition(entry, cellId);
  return entry.answer[position] ?? '';
}

function chooseDirection(
  index: PuzzleIndex,
  cellId: CellId,
  preferred: Direction,
  allowToggle = false
): Direction {
  const across = getEntryForCell(index, cellId, 'across');
  const down = getEntryForCell(index, cellId, 'down');
  if (allowToggle && across && down) {
    return preferred === 'across' ? 'down' : 'across';
  }
  if (preferred === 'across' && across) return 'across';
  if (preferred === 'down' && down) return 'down';
  return across ? 'across' : 'down';
}

export function selectCell(
  snapshot: SolveSessionSnapshot,
  index: PuzzleIndex,
  cellId: CellId,
  preferredDirection = snapshot.selection.direction,
  toggleDirection = false
): SolveSessionSnapshot {
  const direction = chooseDirection(index, cellId, preferredDirection, toggleDirection);
  const entry = getEntryForCell(index, cellId, direction);
  if (!entry) {
    throw new Error(`Cell ${cellId} has no ${direction} entry`);
  }
  return {
    ...snapshot,
    selection: { cellId, direction, entryId: entry.id }
  };
}

function coordinateForCell(index: PuzzleIndex, cellId: CellId): { row: number; column: number } {
  const cell = index.cellsById.get(cellId);
  if (!cell) throw new Error(`Unknown cell ${cellId}`);
  return { row: cell.row, column: cell.column };
}

function cellAtCoordinate(
  puzzle: PuzzleDocument,
  row: number,
  column: number
): CellId | undefined {
  return puzzle.cells.find((cell) => cell.row === row && cell.column === column && !cell.block)?.id;
}

export function moveSelection(
  snapshot: SolveSessionSnapshot,
  puzzle: PuzzleDocument,
  index: PuzzleIndex,
  key: MoveKey
): SolveSessionSnapshot {
  const { row, column } = coordinateForCell(index, snapshot.selection.cellId);
  const deltas: Record<MoveKey, readonly [number, number]> = {
    ArrowUp: [-1, 0],
    ArrowDown: [1, 0],
    ArrowLeft: [0, -1],
    ArrowRight: [0, 1]
  };
  const delta = deltas[key];
  if (!delta) return snapshot;
  const nextCellId = cellAtCoordinate(puzzle, row + delta[0], column + delta[1]);
  if (!nextCellId) return snapshot;
  return selectCell(snapshot, index, nextCellId, snapshot.selection.direction);
}

function orderedEntries(puzzle: PuzzleDocument, direction: Direction): Entry[] {
  return puzzle.entries
    .filter((entry) => entry.direction === direction)
    .sort((left, right) => left.number - right.number);
}

function firstOpenCell(entry: Entry, snapshot: SolveSessionSnapshot): CellId {
  return entry.cellIds.find((cellId) => !snapshot.entered[cellId]) ?? entry.cellIds[0]!;
}

export function stepEntry(
  snapshot: SolveSessionSnapshot,
  puzzle: PuzzleDocument,
  index: PuzzleIndex,
  step: EntryStep
): SolveSessionSnapshot {
  const entries = orderedEntries(puzzle, snapshot.selection.direction);
  const currentIndex = entries.findIndex((entry) => entry.id === snapshot.selection.entryId);
  if (currentIndex < 0 || entries.length === 0) return snapshot;
  const offset = step === 'next' ? 1 : -1;
  const nextIndex = (currentIndex + offset + entries.length) % entries.length;
  const entry = entries[nextIndex];
  if (!entry) return snapshot;
  return selectCell(snapshot, index, firstOpenCell(entry, snapshot), entry.direction);
}

export function toggleDirection(
  snapshot: SolveSessionSnapshot,
  index: PuzzleIndex
): SolveSessionSnapshot {
  return selectCell(
    snapshot,
    index,
    snapshot.selection.cellId,
    snapshot.selection.direction,
    true
  );
}

function advanceWithinEntry(
  snapshot: SolveSessionSnapshot,
  index: PuzzleIndex,
  entry: Entry
): SolveSessionSnapshot {
  const position = getCellPosition(entry, snapshot.selection.cellId);
  const nextCellId = entry.cellIds[position + 1];
  return nextCellId ? selectCell(snapshot, index, nextCellId, entry.direction) : snapshot;
}

export function enterLetter(
  snapshot: SolveSessionSnapshot,
  puzzle: PuzzleDocument,
  index: PuzzleIndex,
  value: string
): SolveSessionSnapshot {
  if (snapshot.paused) return snapshot;
  const letter = value.trim().slice(0, 1).toUpperCase();
  if (!/^[A-Z]$/.test(letter)) return snapshot;
  const entered = { ...snapshot.entered, [snapshot.selection.cellId]: letter };
  const entry = index.entriesById.get(snapshot.selection.entryId);
  if (!entry) throw new Error(`Unknown entry ${snapshot.selection.entryId}`);
  return withStatus(addEvent(
    advanceWithinEntry({ ...snapshot, entered }, index, entry),
    'cell-entered',
    snapshot.lastInteractionAtMs,
    { cellId: snapshot.selection.cellId, entryId: entry.id, value: letter }
  ), puzzle);
}

export function enterRebus(
  snapshot: SolveSessionSnapshot,
  puzzle: PuzzleDocument,
  index: PuzzleIndex,
  value: string
): SolveSessionSnapshot {
  if (snapshot.paused) return snapshot;
  const token = value.trim().toUpperCase();
  if (!/^[A-Z]{1,10}$/.test(token)) return snapshot;
  const entered = { ...snapshot.entered, [snapshot.selection.cellId]: token };
  const entry = index.entriesById.get(snapshot.selection.entryId);
  if (!entry) throw new Error(`Unknown entry ${snapshot.selection.entryId}`);
  return withStatus(addEvent(
    advanceWithinEntry({ ...snapshot, entered }, index, entry),
    'cell-entered',
    snapshot.lastInteractionAtMs,
    { cellId: snapshot.selection.cellId, entryId: entry.id, value: token }
  ), puzzle);
}

export function clearCell(
  snapshot: SolveSessionSnapshot,
  puzzle: PuzzleDocument,
  index: PuzzleIndex,
  moveBackward = true
): SolveSessionSnapshot {
  if (snapshot.paused) return snapshot;
  const entered = { ...snapshot.entered, [snapshot.selection.cellId]: '' };
  let next: SolveSessionSnapshot = { ...snapshot, entered, status: 'in-progress' };
  if (moveBackward) {
    const entry = index.entriesById.get(snapshot.selection.entryId);
    if (!entry) throw new Error(`Unknown entry ${snapshot.selection.entryId}`);
    const position = getCellPosition(entry, snapshot.selection.cellId);
    const previousCellId = entry.cellIds[position - 1];
    if (previousCellId) next = selectCell(next, index, previousCellId, entry.direction);
  }
  return withStatus(addEvent(
    next,
    'cell-cleared',
    snapshot.lastInteractionAtMs,
    { cellId: snapshot.selection.cellId, entryId: snapshot.selection.entryId }
  ), puzzle);
}

function cellsForScope(
  snapshot: SolveSessionSnapshot,
  puzzle: PuzzleDocument,
  index: PuzzleIndex,
  scope: CheckScope
): CellId[] {
  if (scope === 'cell') return [snapshot.selection.cellId];
  if (scope === 'entry') {
    return [...(index.entriesById.get(snapshot.selection.entryId)?.cellIds ?? [])];
  }
  return puzzle.cells.filter((cell) => !cell.block).map((cell) => cell.id);
}

export function checkSession(
  snapshot: SolveSessionSnapshot,
  puzzle: PuzzleDocument,
  index: PuzzleIndex,
  scope: 'cell' | 'entry' | 'puzzle'
): CheckResult {
  const scopeCellIds = cellsForScope(snapshot, puzzle, index, scope);
  const incorrectCellIds = scopeCellIds.filter(
    (cellId) => Boolean(snapshot.entered[cellId]) && snapshot.entered[cellId] !== answerAt(puzzle, cellId)
  );
  const checkedCellIds = uniqueCellIds([...snapshot.checkedCellIds, ...scopeCellIds]);
  return {
    snapshot: addEvent(
      { ...snapshot, checkedCellIds },
      'checked',
      snapshot.lastInteractionAtMs,
      { entryId: snapshot.selection.entryId, scope }
    ),
    incorrectCellIds,
    checkedCellIds
  };
}

export function revealCell(
  snapshot: SolveSessionSnapshot,
  puzzle: PuzzleDocument,
  index: PuzzleIndex,
  scope: CheckScope
): SolveSessionSnapshot {
  const cellIds = cellsForScope(snapshot, puzzle, index, scope);
  const entered = { ...snapshot.entered };
  for (const cellId of cellIds) entered[cellId] = answerAt(puzzle, cellId);
  return withStatus(addEvent(
    {
      ...snapshot,
      entered,
      revealedCellIds: uniqueCellIds([...snapshot.revealedCellIds, ...cellIds]),
      assistanceCount: snapshot.assistanceCount + 1
    },
    'revealed',
    snapshot.lastInteractionAtMs,
    { entryId: snapshot.selection.entryId, scope }
  ), puzzle);
}

export function nudgeEntry(
  snapshot: SolveSessionSnapshot,
  puzzle: PuzzleDocument,
  entryId = snapshot.selection.entryId
): SolveSessionSnapshot {
  const clueSet = puzzle.clues.find((candidate) => candidate.entryId === entryId);
  const nudge = clueSet?.variants.find((variant) => variant.mechanism === 'nudge');
  if (!nudge) return snapshot;
  return addEvent(
    {
      ...snapshot,
      clueVariantByEntryId: { ...snapshot.clueVariantByEntryId, [entryId]: 'nudge' },
      assistanceCount: snapshot.assistanceCount + 1
    },
    'nudged',
    snapshot.lastInteractionAtMs,
    { entryId }
  );
}

export function pauseSession(
  snapshot: SolveSessionSnapshot,
  nowMs: number
): SolveSessionSnapshot {
  if (snapshot.paused) return snapshot;
  const timed = updateActiveTime(snapshot, nowMs);
  return addEvent({ ...timed, paused: true }, 'paused', timed.lastClockAtMs);
}

export function resumeSession(
  snapshot: SolveSessionSnapshot,
  nowMs: number
): SolveSessionSnapshot {
  if (!snapshot.paused) return snapshot;
  const nextClock = Math.max(snapshot.lastClockAtMs, nowMs);
  return addEvent(
    { ...snapshot, paused: false, lastClockAtMs: nextClock, lastInteractionAtMs: nextClock },
    'resumed',
    nextClock
  );
}

export function touchSession(
  snapshot: SolveSessionSnapshot,
  nowMs: number
): SolveSessionSnapshot {
  if (snapshot.paused) return snapshot;
  const timed = updateActiveTime(snapshot, nowMs);
  return { ...timed, lastInteractionAtMs: timed.lastClockAtMs };
}

export function updateActiveTime(
  snapshot: SolveSessionSnapshot,
  nowMs: number,
  inactivityLimitMs = 30_000
): SolveSessionSnapshot {
  const nextClock = Math.max(snapshot.lastClockAtMs, nowMs);
  const elapsed = nextClock - snapshot.lastClockAtMs;
  const recentlyActive = nextClock - snapshot.lastInteractionAtMs <= inactivityLimitMs;
  return {
    ...snapshot,
    activeMs: recentlyActive && !snapshot.paused ? snapshot.activeMs + elapsed : snapshot.activeMs,
    lastClockAtMs: nextClock
  };
}

export function patternForEntry(
  entry: Entry,
  snapshot: SolveSessionSnapshot
): readonly string[] {
  return entry.cellIds.map((cellId) => snapshot.entered[cellId] || '_');
}
