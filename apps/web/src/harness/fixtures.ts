import {
  checkSession,
  createFixturePuzzle,
  createRealPuzzle,
  createSession,
  enterLetter,
  indexPuzzle,
  selectCell,
  type CellId,
  type PuzzleDocument,
  type PuzzleIndex,
  type SolveSessionSnapshot
} from '@crossword/domain';

export type HarnessMode = 'light' | 'dark' | 'forced' | 'zoom';

export type HarnessFixture = Readonly<{
  id: string;
  title: string;
  build: () => Readonly<{
    puzzle: PuzzleDocument;
    index: PuzzleIndex;
    session: SolveSessionSnapshot;
    incorrectCellIds: readonly CellId[];
  }>;
  notes: readonly string[];
}>;

function createSessionFor(puzzle: PuzzleDocument, index: PuzzleIndex): SolveSessionSnapshot {
  // Fixed epoch keeps every fixture deterministic; event timestamps are not
  // part of rendered markup.
  return createSession(puzzle, index, 0);
}

function fillAcross0(session: SolveSessionSnapshot, puzzle: PuzzleDocument, index: PuzzleIndex) {
  let current = selectCell(session, index, 'cell-0-0' as CellId, 'across');
  for (const letter of 'CARE') current = enterLetter(current, puzzle, index, letter);
  return current;
}

export const harnessFixtures: readonly HarnessFixture[] = [
  {
    id: 'empty-15',
    title: 'Empty 15×15',
    notes: ['Fresh session on the local 15×15 fixture; nothing selected beyond the first cell.'],
    build: () => {
      const puzzle = createRealPuzzle();
      const index = indexPuzzle(puzzle);
      return { puzzle, index, session: createSessionFor(puzzle, index), incorrectCellIds: [] };
    }
  },
  {
    id: 'active-across',
    title: 'Active Across with affected Down',
    notes: ['Across entry 1A selected: every crossing Down clue is quiet-affected and its shared cell ringed.'],
    build: () => {
      const puzzle = createFixturePuzzle();
      const index = indexPuzzle(puzzle);
      const session = selectCell(createSessionFor(puzzle, index), index, 'cell-0-0' as CellId, 'across');
      return { puzzle, index, session, incorrectCellIds: [] };
    }
  },
  {
    id: 'active-down-typed',
    title: 'Active Down with typed crossings',
    notes: ['Down entry selected at 1D with three letters typed; Across clues show the shared letters.'],
    build: () => {
      const puzzle = createFixturePuzzle();
      const index = indexPuzzle(puzzle);
      let session = selectCell(createSessionFor(puzzle, index), index, 'cell-0-0' as CellId, 'down');
      for (const letter of 'CAR') session = enterLetter(session, puzzle, index, letter);
      return { puzzle, index, session, incorrectCellIds: [] };
    }
  },
  {
    id: 'check-error',
    title: 'Check error',
    notes: ['Entry 1A checked with wrong letters; error state shows on row, answer cells, and grid cells.'],
    build: () => {
      const puzzle = createFixturePuzzle();
      const index = indexPuzzle(puzzle);
      let session = selectCell(createSessionFor(puzzle, index), index, 'cell-0-0' as CellId, 'across');
      for (const letter of 'XXXX') session = enterLetter(session, puzzle, index, letter);
      const result = checkSession(session, puzzle, index, 'entry');
      return { puzzle, index, session: result.snapshot, incorrectCellIds: result.incorrectCellIds };
    }
  },
  {
    id: 'half-collapsed',
    title: 'Half complete with default collapsed clues',
    notes: [
      '1A and 1D solved: solved rows quiet under the default collapsed policy.',
      'The Down spine demonstrates the paired rule: its top row holds two solved entries and shrinks; the Across top row holds only one, so it keeps its height.'
    ],
    build: () => {
      const puzzle = createFixturePuzzle();
      const index = indexPuzzle(puzzle);
      let session = fillAcross0(createSessionFor(puzzle, index), puzzle, index);
      session = selectCell(session, index, 'cell-0-1' as CellId, 'down');
      for (const letter of 'AREA') session = enterLetter(session, puzzle, index, letter);
      return { puzzle, index, session, incorrectCellIds: [] };
    }
  },
  {
    id: 'long-clue',
    title: 'Long clue and 15-letter answer',
    notes: [
      'Placeholder: the longest current legal fixture entry is 11 letters (ARTHURWYNNE).',
      'A dedicated manifest with a 15-letter answer waits on the fixture-pack slice; this fixture renders the longest available entries on the 15×15.'
    ],
    build: () => {
      const puzzle = createRealPuzzle();
      const index = indexPuzzle(puzzle);
      return { puzzle, index, session: createSessionFor(puzzle, index), incorrectCellIds: [] };
    }
  },
  {
    id: 'special-cells',
    title: 'Circled and shaded cells',
    notes: [
      'Fixture cells 1A and 4D are circled; 3A column 2 is shaded.',
      'Rebus entry is supported: right-click a rebus cell (see the rebus fixture) to enter a multi-letter token.'
    ],
    build: () => {
      const puzzle = createFixturePuzzle();
      const index = indexPuzzle(puzzle);
      return { puzzle, index, session: createSessionFor(puzzle, index), incorrectCellIds: [] };
    }
  },
  {
    id: 'rebus',
    title: 'Rebus cell',
    notes: [
      'Cell 1A carries the rebus token AN: right-click (context menu) accepts a multi-letter entry.',
      'The rebus indicator shows the token length in the cell corner.'
    ],
    build: () => {
      const puzzle = JSON.parse(JSON.stringify(createFixturePuzzle())) as import('@crossword/domain').PuzzleDocument;
      const target = puzzle.cells.find((cell) => cell.row === 0 && cell.column === 0);
      if (target) (target as { rebus?: string }).rebus = 'AN';
      const index = indexPuzzle(puzzle);
      return { puzzle, index, session: createSessionFor(puzzle, index), incorrectCellIds: [] };
    }
  }
];

export function resolveHarnessFixture(id: string | null): HarnessFixture {
  const fallback = harnessFixtures[0];
  if (!fallback) throw new Error('No harness fixtures are defined');
  return harnessFixtures.find((fixture) => fixture.id === id) ?? fallback;
}

export function resolveHarnessMode(mode: string | null): HarnessMode {
  return (['light', 'dark', 'forced', 'zoom'] as const).find((candidate) => candidate === mode) ?? 'light';
}
