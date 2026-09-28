import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { createFixturePuzzle } from './puzzle';
import type { PuzzleDocumentV2 } from './puzzleV2';
import {
  analyzeSessionV2,
  analyzeSessionV2Document,
  validateEntryObservation,
  validateSessionAnalysis,
  validateSolveEventV2,
  validateSolveSessionV2,
} from './solveV2';
import type { SolveEventV2, SolveSessionV2 } from './solveV2';

const puzzle = createFixturePuzzle();
const across = puzzle.entries.find((entry) => entry.id === 'entry-across-0')!;
const v2FixtureUrl = new URL(
  '../../../tests/fixtures/personalized-review-v2.json',
  import.meta.url,
);

function readV2Fixture(): PuzzleDocumentV2 {
  return JSON.parse(readFileSync(v2FixtureUrl, 'utf8')) as PuzzleDocumentV2;
}

function startV2Session(document: PuzzleDocumentV2): SolveSessionV2 {
  return {
    schemaVersion: 2,
    sessionId: 'session-v2-fixture',
    puzzleHash: document.integrity.value,
    initialGrid: document.cells
      .filter((cell) => !cell.block)
      .map((cell) => ({
        cellId: cell.id as never,
        token: null,
        origin: 'unknown' as const,
      })),
    events: [
      {
        schemaVersion: 2,
        eventId: 'event-v2-start',
        sessionId: 'session-v2-fixture',
        segmentId: 'segment-v2-fixture',
        seq: 1,
        elapsedMs: 0,
        recordedAt: '2026-09-26T12:00:00.000Z',
        puzzleHash: document.integrity.value,
        type: 'session-started',
        reason: 'fresh',
      },
    ],
  };
}

type GridCell = {
  token: string | null;
  sourceEntryId: string | null;
  origin: 'unknown' | 'player' | 'reveal';
};

class TraceBuilder {
  private seq = 0;
  private elapsedMs = 0;
  private readonly events: SolveEventV2[] = [];
  private readonly grid = new Map<string, GridCell>();

  constructor(
    private readonly initialGrid: SolveSessionV2['initialGrid'] = [],
  ) {
    for (const cell of puzzle.cells) {
      if (!cell.block)
        this.grid.set(cell.id, {
          token: null,
          origin: 'unknown',
          sourceEntryId: null,
        });
    }
    for (const cell of initialGrid)
      this.grid.set(cell.cellId, {
        token: cell.token,
        origin: 'unknown',
        sourceEntryId: null,
      });
    this.emit({ type: 'session-started', reason: 'fresh' });
  }

  private emit(payload: Record<string, unknown>, elapsedMs?: number): void {
    this.seq += 1;
    this.elapsedMs = elapsedMs ?? this.elapsedMs + 100;
    this.events.push({
      schemaVersion: 2,
      eventId: `event-${this.seq}`,
      sessionId: 'session-fixture-1',
      segmentId: 'segment-1',
      seq: this.seq,
      elapsedMs: this.elapsedMs,
      recordedAt: '2026-09-25T12:00:00.000Z',
      puzzleHash: puzzle.integrity.value,
      ...payload,
    } as unknown as SolveEventV2);
  }

  focus(entryId: string): void {
    const entry = puzzle.entries.find((candidate) => candidate.id === entryId)!;
    const visiblePattern = entry.cellIds.map((cellId) => {
      const current = this.grid.get(cellId)!;
      if (current.origin === 'reveal') {
        return {
          cellId,
          token: current.token,
          origin: 'reveal',
          sourceEntryId: null,
        };
      }
      if (current.origin === 'unknown' || current.sourceEntryId === null) {
        return {
          cellId,
          token: current.token,
          origin: 'unknown',
          sourceEntryId: null,
        };
      }
      if (current.sourceEntryId === entryId) {
        return {
          cellId,
          token: current.token,
          origin: 'player',
          sourceEntryId: entryId,
        };
      }
      return {
        cellId,
        token: current.token,
        origin: 'crossing',
        sourceEntryId: current.sourceEntryId,
      };
    });
    this.emit({
      type: 'entry-focused',
      entryId,
      variantId: null,
      reason: 'keyboard',
      visiblePattern,
    });
  }

  write(
    cellId: string,
    afterToken: string,
    activeEntryId: string,
    source = 'keyboard',
  ): void {
    const beforeToken = this.grid.get(cellId)!.token;
    this.emit({
      type: 'cell-written',
      cellId,
      beforeToken,
      afterToken,
      activeEntryId,
      actionId: `action-${this.seq + 1}`,
      source,
    });
    this.grid.set(cellId, {
      token: afterToken,
      origin: source === 'unknown' ? 'unknown' : 'player',
      sourceEntryId: source === 'unknown' ? null : activeEntryId,
    });
  }

  batch(entryId: string, values: readonly string[]): void {
    const entry = puzzle.entries.find((candidate) => candidate.id === entryId)!;
    const edits = entry.cellIds.map((cellId, index) => ({
      cellId,
      beforeToken: this.grid.get(cellId)!.token,
      afterToken: values[index]!,
    }));
    this.emit({
      type: 'batch-entered',
      activeEntryId: entryId,
      actionId: `batch-${this.seq + 1}`,
      source: 'paste',
      edits,
    });
    for (const edit of edits) {
      this.grid.set(edit.cellId, {
        token: edit.afterToken,
        origin: 'player',
        sourceEntryId: entryId,
      });
    }
  }

  check(entryId: string, cellIds: readonly string[]): void {
    const entry = puzzle.entries.find((candidate) => candidate.id === entryId)!;
    const answer = Array.from(entry.answer);
    const results = cellIds.map((cellId) => {
      const position = entry.cellIds.indexOf(cellId as never);
      const token = this.grid.get(cellId)!.token;
      return {
        cellId,
        token,
        classification:
          token === null
            ? 'blank'
            : token.toUpperCase() === answer[position]?.toUpperCase()
              ? 'correct'
              : 'incorrect',
      };
    });
    this.emit({ type: 'check-result-shown', scope: 'entry', entryId, results });
  }

  reveal(entryId: string, cellId: string): void {
    const entry = puzzle.entries.find((candidate) => candidate.id === entryId)!;
    const position = entry.cellIds.indexOf(cellId as never);
    const token = Array.from(entry.answer)[position]!;
    const beforeToken = this.grid.get(cellId)!.token;
    this.emit({
      type: 'answer-revealed',
      scope: 'cell',
      entryId,
      cells: [{ cellId, beforeToken, token }],
    });
    this.grid.set(cellId, { token, origin: 'reveal', sourceEntryId: null });
  }

  add(payload: Record<string, unknown>, elapsedMs?: number): void {
    this.emit(payload, elapsedMs);
  }

  makeSession(): SolveSessionV2 {
    return {
      schemaVersion: 2,
      sessionId: 'session-fixture-1',
      puzzleHash: puzzle.integrity.value,
      initialGrid: this.initialGrid,
      events: this.events,
    };
  }
}

function fillTargetManually(
  trace: TraceBuilder,
  entry = across,
  skip = new Set<number>(),
): void {
  trace.focus(entry.id);
  for (const [index, cellId] of entry.cellIds.entries()) {
    if (!skip.has(index))
      trace.write(cellId, Array.from(entry.answer)[index]!, entry.id);
  }
}

function targetObservation(trace: TraceBuilder) {
  const analysis = analyzeSessionV2(trace.makeSession(), puzzle);
  return analysis.observations.find((item) => item.entryId === across.id)!;
}

describe('solve event v2 contracts and conservative analysis', () => {
  it('replays explicitly against a schema- and digest-validated V2 puzzle document', async () => {
    const document = readV2Fixture();
    const session = startV2Session(document);

    const analysis = await analyzeSessionV2Document(session, document);

    expect(analysis.puzzleHash).toBe(document.integrity.value);
    expect(analysis.observations).toHaveLength(document.entries.length);
    expect(new Set(analysis.observations.map((item) => item.outcome))).toEqual(
      new Set(['untouched']),
    );
  });

  it('rejects a V2 document whose content no longer matches its digest', async () => {
    const document = readV2Fixture();
    const session = startV2Session(document);
    const edited = { ...document, title: `${document.title} edited` };

    await expect(analyzeSessionV2Document(session, edited)).rejects.toThrow(
      'integrity-mismatch',
    );
  });

  it('requires the solve session to bind to the validated V2 puzzle digest', async () => {
    const document = readV2Fixture();
    const session = startV2Session(document);
    const mismatched = {
      ...session,
      puzzleHash: '0'.repeat(64),
      events: session.events.map((event) => ({
        ...event,
        puzzleHash: '0'.repeat(64),
      })),
    };

    await expect(analyzeSessionV2Document(mismatched, document)).rejects.toThrow(
      'puzzle hash does not match',
    );
  });

  it('does not infer the puzzle schema from a V2 solve-session envelope', () => {
    const document = readV2Fixture();
    const session = startV2Session(document);

    expect(() =>
      analyzeSessionV2(
        session,
        document as unknown as Parameters<typeof analyzeSessionV2>[1],
      ),
    ).toThrow('Invalid puzzle document');
  });

  it('strictly validates event shapes, event ordering, and provenance snapshots', () => {
    const trace = new TraceBuilder();
    trace.focus(across.id);
    trace.write(across.cellIds[0]!, 'C', across.id);
    const session = trace.makeSession();

    expect(validateSolveEventV2(session.events[0])).toBe(true);
    expect(validateSolveSessionV2(session)).toBe(true);
    expect(validateEntryObservation(targetObservation(trace))).toBe(true);
    expect(validateSessionAnalysis(analyzeSessionV2(session, puzzle))).toBe(
      true,
    );

    const eventWithExtraPayload = {
      ...session.events[0],
      secret: 'not part of the schema',
    };
    expect(validateSolveEventV2(eventWithExtraPayload)).toBe(false);
    expect(
      validateSolveSessionV2({
        ...session,
        events: [session.events[1], session.events[0]],
      }),
    ).toBe(false);
    expect(
      validateSolveSessionV2({
        ...session,
        initialGrid: [{ cellId: 'cell-0-0', token: 'C', origin: 'player' }],
      }),
    ).toBe(false);
  });

  it('requires contiguous sequence numbers beginning at one', () => {
    const trace = new TraceBuilder();
    trace.focus(across.id);
    const session = trace.makeSession();
    const gapped = {
      ...session,
      events: session.events.map((event, index) =>
        index === 1 ? { ...event, seq: event.seq + 1 } : event,
      ),
    };

    expect(validateSolveSessionV2(gapped)).toBe(false);
  });

  it('requires exactly one session-started event at the beginning', () => {
    const trace = new TraceBuilder();
    const session = trace.makeSession();
    const duplicateStart = {
      ...session.events[0]!,
      eventId: 'duplicate-session-start',
      seq: 2,
    };

    expect(
      validateSolveSessionV2({
        ...session,
        events: [...session.events, duplicateStart],
      }),
    ).toBe(false);
  });

  it('allows finish only as the terminal event and rejects later writes', () => {
    const trace = new TraceBuilder();
    trace.add({ type: 'session-finished', reason: 'stopped' });
    const finished = trace.makeSession();
    expect(validateSolveSessionV2(finished)).toBe(true);

    trace.write(across.cellIds[0]!, 'C', across.id);
    const postFinishWrite = trace.makeSession();
    expect(validateSolveSessionV2(postFinishWrite)).toBe(false);
    expect(() => analyzeSessionV2(postFinishWrite, puzzle)).toThrow(
      'Invalid solve session v2',
    );
  });

  it('recognizes a correct blank-pattern solve as an independent retrieval candidate', () => {
    const trace = new TraceBuilder();
    fillTargetManually(trace);

    const observation = targetObservation(trace);
    expect(observation).toMatchObject({
      finalState: 'correct',
      outcome: 'independent-retrieval',
      inputMode: 'manual',
      prefilledFraction: 0,
      independentSuccessWeight: 1,
      supportedSuccessWeight: 0,
      failureWeight: 0,
    });
  });

  it('does not let crossings added after a correct answer erase its independent retrieval evidence', () => {
    const trace = new TraceBuilder();
    fillTargetManually(trace);
    for (let column = 0; column < across.cellIds.length; column += 1) {
      trace.write(
        across.cellIds[column]!,
        Array.from(across.answer)[column]!,
        `entry-down-${column}`,
      );
    }

    const observation = targetObservation(trace);
    expect(observation.outcome).toBe('independent-retrieval');
    expect(observation.supportCellIds).toEqual([]);
    expect(observation.independentSuccessWeight).toBe(1);
  });

  it('uses the exact crossing positions to classify supported retrieval', () => {
    const trace = new TraceBuilder();
    trace.write(across.cellIds[0]!, 'C', 'entry-down-0');
    trace.write(across.cellIds[1]!, 'A', 'entry-down-1');
    fillTargetManually(trace, across, new Set([0, 1]));

    const observation = targetObservation(trace);
    expect(observation.outcome).toBe('supported-retrieval');
    expect(observation.prefilledFraction).toBe(0.5);
    expect(observation.supportCellIds).toEqual(['cell-0-0', 'cell-0-1']);
    expect(observation.supportedSuccessWeight).toBe(0.35);
    expect(observation.independentSuccessWeight).toBe(0);
  });

  it('treats a word completed entirely by crossing entries as exposure', () => {
    const trace = new TraceBuilder();
    for (let column = 0; column < across.cellIds.length; column += 1) {
      trace.write(
        across.cellIds[column]!,
        Array.from(across.answer)[column]!,
        `entry-down-${column}`,
      );
    }

    const observation = targetObservation(trace);
    expect(observation.finalState).toBe('correct');
    expect(observation.outcome).toBe('exposure');
    expect(observation.supportCellIds).toEqual(across.cellIds);
    expect(observation.independentSuccessWeight).toBe(0);
    expect(observation.supportedSuccessWeight).toBe(0);
  });

  it('records checked correction once even when identical wrong feedback repeats', () => {
    const trace = new TraceBuilder();
    trace.focus(across.id);
    trace.write(across.cellIds[0]!, 'X', across.id);
    trace.check(
      across.id,
      [across.cellIds[0]!, across.cellIds[0]!].slice(0, 1),
    );
    trace.check(across.id, [across.cellIds[0]!]);
    trace.write(across.cellIds[0]!, 'C', across.id);
    for (const [index, cellId] of across.cellIds.slice(1).entries()) {
      trace.write(cellId!, Array.from(across.answer)[index + 1]!, across.id);
    }

    const observation = targetObservation(trace);
    expect(observation.outcome).toBe('check-assisted-correction');
    expect(observation.checkCorrectedCellIds).toEqual(['cell-0-0']);
    expect(observation.correctnessShownCellIds).toEqual(['cell-0-0']);
    expect(observation.incorrectAttemptCount).toBe(1);
    expect(observation.failureWeight).toBe(0.5);
    expect(observation.independentSuccessWeight).toBe(0);
  });

  it('keeps a revealed letter separate from retrieval evidence', () => {
    const trace = new TraceBuilder();
    trace.focus(across.id);
    trace.reveal(across.id, across.cellIds[0]!);
    for (const [index, cellId] of across.cellIds.slice(1).entries()) {
      trace.write(cellId!, Array.from(across.answer)[index + 1]!, across.id);
    }

    const observation = targetObservation(trace);
    expect(observation.outcome).toBe('reveal-assisted-correction');
    expect(observation.revealedCellIds).toEqual(['cell-0-0']);
    expect(observation.revealCorrectedCellIds).toEqual([]);
    expect(observation.independentSuccessWeight).toBe(0);
    expect(observation.supportedSuccessWeight).toBe(0);
  });

  it('labels pasted answers as one batch with no independent success weight', () => {
    const trace = new TraceBuilder();
    trace.batch(across.id, Array.from(across.answer));

    expect(targetObservation(trace)).toMatchObject({
      finalState: 'correct',
      outcome: 'batch-entry',
      inputMode: 'batch',
      independentSuccessWeight: 0,
      supportedSuccessWeight: 0,
    });
  });

  it('preserves unknown imported letters and never upgrades them into unaided recall', () => {
    const trace = new TraceBuilder([
      { cellId: across.cellIds[0]!, token: 'C', origin: 'unknown' },
    ]);
    fillTargetManually(trace, across, new Set([0]));

    const observation = targetObservation(trace);
    expect(observation.outcome).toBe('supported-retrieval');
    expect(observation.unknownProvenanceCellIds).toEqual(['cell-0-0']);
    expect(observation.prefilledFraction).toBe(0.25);
    expect(observation.independentSuccessWeight).toBe(0);
    expect(observation.supportedSuccessWeight).toBe(0.35);
  });

  it('keeps a complete imported answer indeterminate when every letter has unknown provenance', () => {
    const initialGrid = across.cellIds.map((cellId, index) => ({
      cellId,
      token: Array.from(across.answer)[index]!,
      origin: 'unknown' as const,
    }));
    const trace = new TraceBuilder(initialGrid);

    const observation = targetObservation(trace);
    expect(observation.finalState).toBe('correct');
    expect(observation.outcome).toBe('indeterminate');
    expect(observation.unknownProvenanceCellIds).toEqual(across.cellIds);
    expect(observation.independentSuccessWeight).toBe(0);
    expect(observation.supportedSuccessWeight).toBe(0);
  });

  it('leaves unengaged entries unknown and does not infer dislike from absence', () => {
    const trace = new TraceBuilder();
    const observation = targetObservation(trace);

    expect(observation).toMatchObject({
      finalState: 'incomplete',
      outcome: 'untouched',
      inputMode: 'none',
      independentSuccessWeight: 0,
      supportedSuccessWeight: 0,
      failureWeight: 0,
    });
  });

  it('ignores hidden-tab pauses and elapsed time when scoring an otherwise identical solve', () => {
    const trace = new TraceBuilder();
    trace.add({ type: 'visibility-changed', visibility: 'hidden' }, 10_000);
    trace.add({ type: 'paused', reason: 'background' }, 500_000);
    trace.add({ type: 'visibility-changed', visibility: 'visible' }, 900_000);
    trace.add({ type: 'resumed', reason: 'background' }, 900_100);
    fillTargetManually(trace);

    const observation = targetObservation(trace);
    expect(observation.outcome).toBe('independent-retrieval');
    expect(observation.independentSuccessWeight).toBe(1);
  });

  it('rejects inconsistent replay values instead of inventing a correction', () => {
    const trace = new TraceBuilder();
    trace.focus(across.id);
    trace.write(across.cellIds[0]!, 'C', across.id);
    const session = trace.makeSession();
    const events = [...session.events];
    const last = events.at(-1)!;
    events[events.length - 1] = { ...last, beforeToken: 'X' } as SolveEventV2;

    expect(() => analyzeSessionV2({ ...session, events }, puzzle)).toThrow(
      /beforeToken/,
    );
  });

  it('rejects a focus snapshot that relabels an imported letter as player recall', () => {
    const trace = new TraceBuilder([
      { cellId: across.cellIds[0]!, token: 'C', origin: 'unknown' },
    ]);
    trace.focus(across.id);
    const session = trace.makeSession();
    const events = [...session.events];
    const focus = events.at(-1)!;
    if (focus.type !== 'entry-focused')
      throw new Error('Expected a focus event');
    const visiblePattern = focus.visiblePattern.map((cell, index) =>
      index === 0
        ? { ...cell, origin: 'player' as const, sourceEntryId: across.id }
        : cell,
    );
    events[events.length - 1] = { ...focus, visiblePattern };

    expect(() => analyzeSessionV2({ ...session, events }, puzzle)).toThrow(
      /provenance/,
    );
  });
});
