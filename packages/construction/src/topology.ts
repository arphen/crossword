/**
 * Topology: grid block masks, entry-slot derivation, and invariants.
 *
 * Topology and answer fill are separate problems (docs/plans/02
 * "Topology before fill"). This module owns mask validation and the
 * projection from a block mask into fill-engine inputs; it owns no lexicon
 * and no fill logic. The application layer assembles domain puzzles from the
 * derived values.
 *
 * Mask format: rows of `#` (block) and `.` (white). Cell IDs use the `r-c`
 * convention shared with the fixture puzzles in `@crossword/domain`.
 */

export type TopologyCell = Readonly<{
  id: string;
  row: number;
  column: number;
  block: boolean;
}>;

export type TopologyEntry = Readonly<{
  id: string;
  direction: 'across' | 'down';
  row: number;
  column: number;
  length: number;
  cellIds: readonly string[];
}>;

export type TopologySlot = Readonly<{
  id: string;
  length: number;
  importance?: number;
}>;

export type TopologyIntersection = Readonly<{
  slotId: string;
  position: number;
  otherSlotId: string;
  otherPosition: number;
}>;

export type DerivedTopology = Readonly<{
  templateId: string;
  width: number;
  height: number;
  minEntryLength: number;
  cells: readonly TopologyCell[];
  entries: readonly TopologyEntry[];
  slots: readonly TopologySlot[];
  intersections: readonly TopologyIntersection[];
  numberByCellId: ReadonlyMap<string, number>;
  blockedCellIds: readonly string[];
  whiteCellCount: number;
}>;

export type TopologyViolationCode =
  | 'empty-mask'
  | 'ragged-rows'
  | 'bad-character'
  | 'short-run'
  | 'unchecked-cell'
  | 'disconnected'
  | 'no-entries';

export type TopologyViolation = Readonly<{
  code: TopologyViolationCode;
  message: string;
}>;

export type DeriveTopologyResult =
  | { ok: true; topology: DerivedTopology }
  | { ok: false; violations: readonly TopologyViolation[] };

export type DeriveTopologyOptions = Readonly<{
  templateId?: string;
  minEntryLength?: number;
}>;

export const DEFAULT_MIN_ENTRY_LENGTH = 3;

type LineRun = Readonly<{ start: number; length: number }>;

function runsInLine(line: readonly boolean[]): readonly LineRun[] {
  const runs: LineRun[] = [];
  let start = -1;
  for (let index = 0; index <= line.length; index += 1) {
    const white = index < line.length && line[index];
    if (white && start < 0) start = index;
    if (!white && start >= 0) {
      runs.push({ start, length: index - start });
      start = -1;
    }
  }
  return runs;
}

function acrossRunsOf(mask: readonly string[], row: number, width: number): readonly LineRun[] {
  return runsInLine(Array.from({ length: width }, (_, column) => mask[row]?.[column] !== '#'));
}

function downRunsOf(mask: readonly string[], column: number, height: number): readonly LineRun[] {
  return runsInLine(Array.from({ length: height }, (_, row) => mask[row]?.[column] !== '#'));
}

function violationsFor(mask: readonly string[], minEntryLength: number): readonly TopologyViolation[] {
  const violations: TopologyViolation[] = [];
  const height = mask.length;
  if (height === 0) return [{ code: 'empty-mask', message: 'Topology mask has no rows' }];
  const width = mask[0]?.length ?? 0;
  if (width === 0) return [{ code: 'empty-mask', message: 'Topology mask has no columns' }];

  for (const [rowIndex, row] of mask.entries()) {
    if (row.length !== width) {
      violations.push({ code: 'ragged-rows', message: `Row ${rowIndex} has length ${row.length}, expected ${width}` });
      continue;
    }
    if (/[^.#]/.test(row)) {
      violations.push({ code: 'bad-character', message: `Row ${rowIndex} contains characters other than # and .` });
    }
  }
  if (violations.length > 0) return violations;

  const block = (row: number, column: number): boolean => mask[row]?.[column] === '#';

  let sawEntry = false;
  for (let row = 0; row < height; row += 1) {
    for (const { start, length } of acrossRunsOf(mask, row, width)) {
      if (length >= minEntryLength) sawEntry = true;
      if (length > 0 && length < minEntryLength) {
        violations.push({
          code: 'short-run',
          message: `Across run at row ${row}, column ${start} has length ${length} (minimum ${minEntryLength})`
        });
      }
    }
  }
  for (let column = 0; column < width; column += 1) {
    for (const { start, length } of downRunsOf(mask, column, height)) {
      if (length >= minEntryLength) sawEntry = true;
      if (length > 0 && length < minEntryLength) {
        violations.push({
          code: 'short-run',
          message: `Down run at row ${start}, column ${column} has length ${length} (minimum ${minEntryLength})`
        });
      }
    }
  }
  if (!sawEntry) {
    violations.push({ code: 'no-entries', message: 'Topology mask produces no entries of the minimum length' });
  }

  // Every white cell must be checked: inside an across run of length >= 2 and
  // a down run of length >= 2.
  const inAcrossRun = new Set<number>();
  const inDownRun = new Set<number>();
  for (let row = 0; row < height; row += 1) {
    for (const { start, length } of acrossRunsOf(mask, row, width)) {
      if (length < 2) continue;
      for (let column = start; column < start + length; column += 1) inAcrossRun.add(row * width + column);
    }
  }
  for (let column = 0; column < width; column += 1) {
    for (const { start, length } of downRunsOf(mask, column, height)) {
      if (length < 2) continue;
      for (let row = start; row < start + length; row += 1) inDownRun.add(row * width + column);
    }
  }
  for (let row = 0; row < height; row += 1) {
    for (let column = 0; column < width; column += 1) {
      if (block(row, column)) continue;
      const key = row * width + column;
      if (!inAcrossRun.has(key) || !inDownRun.has(key)) {
        violations.push({
          code: 'unchecked-cell',
          message: `White cell at row ${row}, column ${column} is unchecked`
        });
      }
    }
  }

  // Connectivity of the white-cell graph.
  const flat = mask.join('');
  const firstWhite = flat.indexOf('.');
  if (firstWhite >= 0) {
    const seen = new Set<number>([firstWhite]);
    const queue = [firstWhite];
    while (queue.length > 0) {
      const current = queue.pop()!;
      const row = Math.floor(current / width);
      const column = current % width;
      for (const [deltaRow, deltaColumn] of [[1, 0], [-1, 0], [0, 1], [0, -1]] as const) {
        const nextRow = row + deltaRow;
        const nextColumn = column + deltaColumn;
        if (nextRow < 0 || nextColumn < 0 || nextRow >= height || nextColumn >= width) continue;
        if (block(nextRow, nextColumn)) continue;
        const next = nextRow * width + nextColumn;
        if (!seen.has(next)) {
          seen.add(next);
          queue.push(next);
        }
      }
    }
    const whiteCount = flat.split('').filter((character) => character === '.').length;
    if (seen.size !== whiteCount) {
      violations.push({
        code: 'disconnected',
        message: `White cells form disconnected regions (${seen.size}/${whiteCount} reachable)`
      });
    }
  }

  return violations;
}

export function validateTopologyMask(
  mask: readonly string[],
  minEntryLength = DEFAULT_MIN_ENTRY_LENGTH
): readonly TopologyViolation[] {
  return violationsFor(mask, minEntryLength);
}

export function deriveTopology(mask: readonly string[], options: DeriveTopologyOptions = {}): DeriveTopologyResult {
  const minEntryLength = options.minEntryLength ?? DEFAULT_MIN_ENTRY_LENGTH;
  const violations = violationsFor(mask, minEntryLength);
  if (violations.length > 0) return { ok: false, violations };

  const height = mask.length;
  const width = mask[0]!.length;
  const templateId = options.templateId ?? 'ad-hoc';

  const cells: TopologyCell[] = [];
  const blockedCellIds: string[] = [];
  for (let row = 0; row < height; row += 1) {
    for (let column = 0; column < width; column += 1) {
      const id = `${row}-${column}`;
      const isBlock = mask[row]![column] === '#';
      cells.push({ id, row, column, block: isBlock });
      if (isBlock) blockedCellIds.push(id);
    }
  }

  // Standard crossword numbering: scan row-major; a white cell that starts an
  // across run and/or a down run receives the next number.
  const numberByCellId = new Map<string, number>();
  let nextNumber = 1;
  for (let row = 0; row < height; row += 1) {
    for (let column = 0; column < width; column += 1) {
      if (mask[row]![column] === '#') continue;
      const startsAcross = (column === 0 || mask[row]![column - 1] === '#')
        && column + 1 < width
        && mask[row]![column + 1] !== '#';
      const startsDown = (row === 0 || mask[row - 1]![column] === '#')
        && row + 1 < height
        && mask[row + 1]![column] !== '#';
      if (startsAcross || startsDown) numberByCellId.set(`${row}-${column}`, nextNumber++);
    }
  }

  const entries: TopologyEntry[] = [];
  const slots: TopologySlot[] = [];
  const entryIdByCell = new Map<string, { across?: string; down?: string }>();

  const registerEntry = (direction: 'across' | 'down', row: number, column: number, length: number): void => {
    const cellIds = Array.from({ length }, (_, position) =>
      direction === 'across' ? `${row}-${column + position}` : `${row + position}-${column}`
    );
    const entry: TopologyEntry = {
      id: direction === 'across' ? `A${row}-${column}` : `D${row}-${column}`,
      direction,
      row,
      column,
      length,
      cellIds
    };
    entries.push(entry);
    slots.push({ id: entry.id, length });
    for (const cellId of cellIds) {
      const current = entryIdByCell.get(cellId) ?? {};
      entryIdByCell.set(cellId, { ...current, [direction]: entry.id });
    }
  };

  for (let row = 0; row < height; row += 1) {
    for (const { start, length } of acrossRunsOf(mask, row, width)) {
      if (length >= minEntryLength) registerEntry('across', row, start, length);
    }
  }
  for (let column = 0; column < width; column += 1) {
    for (const { start, length } of downRunsOf(mask, column, height)) {
      if (length >= minEntryLength) registerEntry('down', start, column, length);
    }
  }

  // One intersection per crossing cell (the CSP enforces it bidirectionally).
  const intersections: TopologyIntersection[] = [];
  const cellsById = new Map(cells.map((cell) => [cell.id, cell] as const));
  for (const entry of entries) {
    if (entry.direction !== 'across') continue;
    for (const [position, cellId] of entry.cellIds.entries()) {
      const downEntryId = entryIdByCell.get(cellId)?.down;
      if (!downEntryId) continue;
      const downEntry = entries.find((candidate) => candidate.id === downEntryId);
      if (!downEntry) continue;
      const otherPosition = downEntry.cellIds.indexOf(cellId);
      const cell = cellsById.get(cellId);
      if (otherPosition < 0 || !cell || cell.block) continue;
      intersections.push({ slotId: entry.id, position, otherSlotId: downEntryId, otherPosition });
    }
  }

  const whiteCellCount = cells.length - blockedCellIds.length;

  return {
    ok: true,
    topology: {
      templateId,
      width,
      height,
      minEntryLength,
      cells,
      entries,
      slots,
      intersections,
      numberByCellId,
      blockedCellIds,
      whiteCellCount
    }
  };
}
