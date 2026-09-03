export type FillSlot = Readonly<{
  id: string;
  length: number;
  pattern?: string;
  importance?: number;
}>;

export type FillIntersection = Readonly<{
  slotId: string;
  position: number;
  otherSlotId: string;
  otherPosition: number;
}>;

export type FillCandidate = Readonly<{
  word: string;
  score: number;
  lexemeId: string;
  senseId?: string;
  sourceIds: readonly string[];
  tags?: readonly string[];
}>;

export type FillRequest = Readonly<{
  slots: readonly FillSlot[];
  intersections: readonly FillIntersection[];
  candidates: readonly FillCandidate[];
  /**
   * Theme locks: slots whose answer is fixed before search (themed entries
   * supplied by the model candidate bag). Locked words participate in
   * crossings like any candidate and join the eligible set even when the
   * lexicon does not carry them.
   */
  lockedWords?: Readonly<Record<string, string>>;
  seed?: number;
  maxNodes?: number;
  /**
   * Minimum SUM of candidate scores for a complete fill to be recorded as a
   * solution. Unit: raw candidate-score sum — NOT the normalized editorial
   * 0..1 quality gate, which lives in the application layer (`scoreFill`).
   */
  minimumAssignmentScore?: number;
  excludedWords?: readonly string[];
}>;

export type FillProgress = Readonly<{
  type: 'progress';
  nodes: number;
  assigned: number;
  openSlots: number;
  bestScore: number;
}>;

export type FillFailureCode = 'unsatisfiable' | 'cancelled' | 'resource-limit' | 'invalid-request';

export type FillSolution = Readonly<{
  assignments: Readonly<Record<string, FillCandidate>>;
  score: number;
  nodes: number;
}>;

export type FillResult = Readonly<{
  status: 'solved' | 'failed';
  solution?: FillSolution;
  failure?: Readonly<{
    code: FillFailureCode;
    message: string;
    nodes: number;
  }>;
}>;

export type FillOptions = Readonly<{
  signal?: AbortSignal;
  onProgress?: (progress: FillProgress) => void;
}>;

type Bits = Uint32Array;

type IndexedCandidate = FillCandidate & Readonly<{
  normalizedWord: string;
  index: number;
}>;

type IndexedIntersection = Readonly<{
  left: number;
  leftPosition: number;
  right: number;
  rightPosition: number;
}>;

type LengthClass = Readonly<{
  length: number;
  count: number;
  /** Local preference-ordered ids -> global candidate ids. */
  globalByLocal: readonly number[];
  localIndexByGlobal: ReadonlyMap<number, number>;
  words: number;
}>;

type IndexedRequest = Readonly<{
  slots: readonly FillSlot[];
  slotIds: readonly string[];
  intersections: readonly IndexedIntersection[];
  intersectionsBySlot: readonly (readonly IndexedIntersection[])[];
  candidates: readonly IndexedCandidate[];
  candidatesByLength: ReadonlyMap<number, readonly number[]>;
  /** Per-length local index classes: bitsets are width-local to a length. */
  lengthClasses: ReadonlyMap<number, LengthClass>;
  /**
   * Bitset of LOCAL candidate indexes carrying `letter` at `position`, among
   * candidates of a given length. Key: `${length}:${position}:${letter}`.
   */
  positionBits: ReadonlyMap<string, Bits>;
  excludedWords: ReadonlySet<string>;
  candidateIndexByWord: ReadonlyMap<string, number>;
  scoreByIndex: Readonly<Float64Array>;
  tieBreakByIndex: Readonly<Uint32Array>;
  bestScoreByLength: ReadonlyMap<number, number>;
}>;

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';



function seededTieBreak(seed: number, value: string): number {
  let hash = (seed ^ 0x9e3779b9) >>> 0;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return hash;
}

function createIndex(request: FillRequest): IndexedRequest | { failure: FillResult['failure'] } {
  const slotsById = new Map<string, FillSlot>();
  for (const slot of request.slots) {
    if (slotsById.has(slot.id) || !slot.id || !Number.isInteger(slot.length) || slot.length < 1 || (slot.pattern !== undefined && (slot.pattern.length !== slot.length || !/^[A-Z.]*$/.test(slot.pattern)))) {
      return { failure: { code: 'invalid-request', message: `Invalid fill slot: ${slot.id}`, nodes: 0 } };
    }
    slotsById.set(slot.id, slot);
  }
  if (slotsById.size === 0) return { failure: { code: 'invalid-request', message: 'Fill request has no slots', nodes: 0 } };

  for (const [slotId, word] of Object.entries(request.lockedWords ?? {})) {
    const slot = slotsById.get(slotId);
    if (!slot) return { failure: { code: 'invalid-request', message: `Lock references unknown slot: ${slotId}`, nodes: 0 } };
    const normalized = word.trim().toUpperCase();
    if (!/^[A-Z]+$/.test(normalized) || normalized.length !== slot.length) {
      return { failure: { code: 'invalid-request', message: `Lock for slot ${slotId} is not a ${slot.length}-letter word`, nodes: 0 } };
    }
  }

  const slotIds = request.slots.map((slot) => slot.id);
  const slotIndexById = new Map(slotIds.map((id, index) => [id, index] as const));

  const candidates: IndexedCandidate[] = [];
  const candidatesByLength = new Map<number, number[]>();
  const candidateIndexByWord = new Map<string, number>();
  const excluded = request.excludedWords;
  const registerCandidate = (candidate: FillCandidate): void => {
    const normalizedWord = candidate.word.trim().toUpperCase();
    if (!/^[A-Z]+$/.test(normalizedWord) || !Number.isFinite(candidate.score) || !candidate.lexemeId || candidate.sourceIds.length === 0) return;
    if (excluded?.some((word) => word.toUpperCase() === normalizedWord)) return;
    if (candidateIndexByWord.has(normalizedWord)) return; // first record wins; duplicates drop
    const index = candidates.length;
    candidateIndexByWord.set(normalizedWord, index);
    candidates.push({ ...candidate, normalizedWord, index });
    const indexes = candidatesByLength.get(normalizedWord.length) ?? [];
    indexes.push(index);
    candidatesByLength.set(normalizedWord.length, indexes);
  };

  for (const candidate of request.candidates) registerCandidate(candidate);

  // Locked words participate even when the lexicon cannot resolve them; their
  // provenance is the lock itself and the caller records it in the manifest.
  for (const [slotId, word] of Object.entries(request.lockedWords ?? {})) {
    registerCandidate({
      word,
      score: 1,
      lexemeId: `lock:${slotId}:${word.trim().toUpperCase()}`,
      sourceIds: [`theme-lock:${slotId}`]
    });
  }

  if (candidates.length === 0) return { failure: { code: 'unsatisfiable', message: 'No eligible candidates remain', nodes: 0 } };

  // Preference order doubles as search order: sort once by score (desc) with
  // a seeded tie-break, then reassign indexes so ascending index order is the
  // value-ordering heuristic. Per-node value iteration needs no sort.
  const seed = request.seed ?? 0;
  candidates.sort((left, right) =>
    right.score - left.score
    || seededTieBreak(request.seed ?? 0, left.normalizedWord) - seededTieBreak(request.seed ?? 0, right.normalizedWord)
  );
  candidates.forEach((candidate, index) => {
    candidateIndexByWord.set(candidate.normalizedWord, index);
    candidates[index] = { ...candidate, index };
  });
  candidatesByLength.clear();
  for (const candidate of candidates) {
    const indexes = candidatesByLength.get(candidate.normalizedWord.length) ?? [];
    indexes.push(candidate.index);
    candidatesByLength.set(candidate.normalizedWord.length, indexes);
  }

  // Per-length local index classes: every bitset is width-local to its length
  // class (a 4-letter class with 5k words needs 157 u32 words, not the ~7100
  // a global bitset would use). Local order preserves global preference order.
  const lengthClasses = new Map<number, LengthClass>();
  for (const [length, globalIndexes] of candidatesByLength) {
    const globalByLocal = [...globalIndexes].sort((a, b) => a - b);
    const localIndexByGlobal = new Map<number, number>();
    globalByLocal.forEach((globalIndex, localIndex) => localIndexByGlobal.set(globalIndex, localIndex));
    lengthClasses.set(length, {
      length,
      count: globalByLocal.length,
      globalByLocal,
      localIndexByGlobal,
      words: Math.ceil(globalByLocal.length / 32)
    });
  }

  const positionBits = new Map<string, Bits>();
  for (const candidate of candidates) {
    const lengthClass = lengthClasses.get(candidate.normalizedWord.length)!;
    const localIndex = lengthClass.localIndexByGlobal.get(candidate.index)!;
    for (let position = 0; position < candidate.normalizedWord.length; position += 1) {
      const letter = candidate.normalizedWord[position]!;
      const key = `${candidate.normalizedWord.length}:${position}:${letter}`;
      const bits = positionBits.get(key) ?? new Uint32Array(lengthClass.words);
      bits[localIndex >>> 5] = bits[localIndex >>> 5]! | (1 << (localIndex & 31));
      positionBits.set(key, bits);
    }
  }

  const intersections: IndexedIntersection[] = [];
  const intersectionsBySlot: IndexedIntersection[][] = request.slots.map(() => []);
  for (const intersection of request.intersections) {
    const slot = slotsById.get(intersection.slotId);
    const other = slotsById.get(intersection.otherSlotId);
    if (!slot || !other || !Number.isInteger(intersection.position) || !Number.isInteger(intersection.otherPosition) || intersection.position < 0 || intersection.position >= slot.length || intersection.otherPosition < 0 || intersection.otherPosition >= other.length) {
      return { failure: { code: 'invalid-request', message: 'Intersection references an invalid slot position', nodes: 0 } };
    }
    if (intersection.slotId === intersection.otherSlotId) {
      return { failure: { code: 'invalid-request', message: `Intersection on slot ${intersection.slotId} references itself`, nodes: 0 } };
    }
    const indexed: IndexedIntersection = {
      left: slotIndexById.get(intersection.slotId)!,
      leftPosition: intersection.position,
      right: slotIndexById.get(intersection.otherSlotId)!,
      rightPosition: intersection.otherPosition
    };
    intersections.push(indexed);
    intersectionsBySlot[indexed.left]!.push(indexed);
    intersectionsBySlot[indexed.right]!.push(indexed);
  }

  const scoreByIndex = new Float64Array(candidates.length);
  const tieBreakByIndex = new Uint32Array(candidates.length);
  const bestScoreByLength = new Map<number, number>();
  for (const candidate of candidates) {
    scoreByIndex[candidate.index] = candidate.score;
    tieBreakByIndex[candidate.index] = seededTieBreak(seed, candidate.normalizedWord);
    const best = bestScoreByLength.get(candidate.normalizedWord.length);
    if (best === undefined || candidate.score > best) bestScoreByLength.set(candidate.normalizedWord.length, candidate.score);
  }

  return {
    slots: request.slots,
    slotIds,
    intersections,
    intersectionsBySlot,
    candidates,
    candidatesByLength,
    lengthClasses,
    positionBits,
    excludedWords: new Set(excluded?.map((word) => word.toUpperCase()) ?? []),
    candidateIndexByWord,
    scoreByIndex,
    tieBreakByIndex,
    bestScoreByLength
  };
}

/**
 * Union, over the distinct letters present at `sourcePosition` in the source
 * domain, of the bitsets of target candidates with that letter at
 * `targetPosition`. Letter-domain propagation costs O(26 x bitset words) per
 * intersection instead of O(candidates in domain x key lookup).
 */
function compatibleBits(
  index: IndexedRequest,
  sourceLength: number,
  targetLength: number,
  targetPosition: number,
  sourcePosition: number,
  source: Bits
): Bits {
  const targetClass = index.lengthClasses.get(targetLength)!;
  const result = new Uint32Array(targetClass.words);
  for (let letterIndex = 0; letterIndex < 26; letterIndex += 1) {
    const letter = LETTERS[letterIndex]!;
    const sourceBits = index.positionBits.get(`${sourceLength}:${sourcePosition}:${letter}`);
    if (!sourceBits) continue;
    let present = false;
    for (let wordIndex = 0; wordIndex < source.length; wordIndex += 1) {
      if ((source[wordIndex]! & sourceBits[wordIndex]!) !== 0) {
        present = true;
        break;
      }
    }
    if (!present) continue;
    const allowed = index.positionBits.get(`${targetLength}:${targetPosition}:${letter}`);
    if (!allowed) continue;
    for (let wordIndex = 0; wordIndex < result.length; wordIndex += 1) result[wordIndex] = result[wordIndex]! | allowed[wordIndex]!;
  }
  return result;
}

type SearchState = {
  domains: Bits[];
  sizes: Int32Array;
  assignments: Int32Array;
  /**
   * Undo trail of word-level domain edits: triples of
   * (slotIndex, wordIndex, previousWordValue) — one entry per modified
   * 32-bit word instead of per cleared candidate.
   */
  trail: number[];
  nodes: number;
  score: number;
  cancelled: boolean;
  overBudget: boolean;
  satisfied: boolean;
  best: FillSolution | undefined;
  bestScore: number;
};

function popcount(value: number): number {
  let count = value;
  count = count - ((count >> 1) & 0x55555555);
  count = (count & 0x33333333) + ((count >>> 2) & 0x33333333);
  count = (count + (count >>> 4)) & 0x0f0f0f0f;
  return (count * 0x01010101) >>> 24;
}

/**
 * Remove `removedBits` from `wordIndex` of the slot's domain, recording the
 * previous word value on the trail for undo.
 */
function removeWordBits(state: SearchState, slotIndex: number, wordIndex: number, removedBits: number): void {
  const bits = state.domains[slotIndex]!;
  const previous = bits[wordIndex]!;
  const next = previous & ~removedBits;
  if (next === previous) return;
  bits[wordIndex] = next;
  state.sizes[slotIndex] = state.sizes[slotIndex]! - popcount(previous ^ next);
  state.trail.push(slotIndex, wordIndex, previous);
}

function removeSingleBit(state: SearchState, slotIndex: number, candidateIndex: number): void {
  removeWordBits(state, slotIndex, candidateIndex >>> 5, 1 << (candidateIndex & 31));
}

function undoTrail(state: SearchState, base: number): void {
  while (state.trail.length > base) {
    const previous = state.trail.pop()!;
    const wordIndex = state.trail.pop()!;
    const slotIndex = state.trail.pop()!;
    const bits = state.domains[slotIndex]!;
    const current = bits[wordIndex]!;
    bits[wordIndex] = previous;
    state.sizes[slotIndex] = state.sizes[slotIndex]! + popcount(current ^ previous);
  }
}

/**
 * Maintain arc consistency from a worklist of slots whose domains changed.
 * For each queued slot, recompute the letters available at each of its
 * crossings from its (current) domain and restrict the neighbors accordingly,
 * queueing any neighbor whose domain shrinks. This is classic MAC: domains
 * stay accurate, so MRV selects real dead ends instead of thrashing on
 * stale sizes. Skips already-assigned slots — their constraint was applied
 * when they were assigned.
 */
function propagateFrom(index: IndexedRequest, state: SearchState, seeds: readonly number[]): boolean {
  const queued = new Uint8Array(index.slots.length);
  const queue: number[] = [];
  for (const slotIndex of seeds) {
    // Assigned seeds are intentional: a just-assigned slot carries a
    // singleton domain whose letters must propagate to its crossings.
    if (!queued[slotIndex]) {
      queued[slotIndex] = 1;
      queue.push(slotIndex);
    }
  }
  while (queue.length > 0) {
    const slotIndex = queue.shift()!;
    queued[slotIndex] = 0;
    if (state.sizes[slotIndex] === 0) return false;
    const slot = index.slots[slotIndex]!;
    for (const intersection of index.intersectionsBySlot[slotIndex]!) {
      const isLeft = intersection.left === slotIndex;
      const otherSlotIndex = isLeft ? intersection.right : intersection.left;
      if (state.assignments[otherSlotIndex] !== -1) continue;
      const assignedPosition = isLeft ? intersection.leftPosition : intersection.rightPosition;
      const otherPosition = isLeft ? intersection.rightPosition : intersection.leftPosition;
      const otherLength = index.slots[otherSlotIndex]!.length;
      const allowed = compatibleBits(index, slot.length, otherLength, otherPosition, assignedPosition, state.domains[slotIndex]!);
      const domain = state.domains[otherSlotIndex]!;
      let changed = false;
      for (let wordIndex = 0; wordIndex < domain.length; wordIndex += 1) {
        const removed = domain[wordIndex]! & ~allowed[wordIndex]!;
        if (removed !== 0) {
          removeWordBits(state, otherSlotIndex, wordIndex, removed);
          changed = true;
        }
      }
      if (state.sizes[otherSlotIndex] === 0) return false;
      if (changed && !queued[otherSlotIndex]) {
        queued[otherSlotIndex] = 1;
        queue.push(otherSlotIndex);
      }
    }
  }
  return true;
}

function pressureOf(index: IndexedRequest, slotIndex: number): number {
  return slotIndex < 0 ? -1 : index.intersectionsBySlot[slotIndex]!.length;
}

function selectSlot(index: IndexedRequest, state: SearchState): number {
  let bestIndex = -1;
  let bestSize = Number.POSITIVE_INFINITY;
  for (let slotIndex = 0; slotIndex < index.slots.length; slotIndex += 1) {
    if (state.assignments[slotIndex] !== -1) continue;
    const size = state.sizes[slotIndex]!;
    if (size < bestSize) {
      bestIndex = slotIndex;
      bestSize = size;
      if (size === 1) break;
      continue;
    }
    if (size === bestSize && pressureOf(index, slotIndex) > pressureOf(index, bestIndex)) {
      bestIndex = slotIndex;
    }
  }
  return bestIndex;
}


function remainingScoreUpperBound(index: IndexedRequest, state: SearchState): number {
  let bound = 0;
  for (let slotIndex = 0; slotIndex < index.slots.length; slotIndex += 1) {
    if (state.assignments[slotIndex] !== -1) continue;
    const best = index.bestScoreByLength.get(index.slots[slotIndex]!.length);
    if (best === undefined) return Number.NEGATIVE_INFINITY;
    bound += best;
  }
  return bound;
}

function assignedCount(state: SearchState): number {
  let count = 0;
  for (let slotIndex = 0; slotIndex < state.assignments.length; slotIndex += 1) {
    if (state.assignments[slotIndex] !== -1) count += 1;
  }
  return count;
}

/**
 * Depth-first fill search as a generator: the sync driver drains it without
 * awaiting; the async driver awaits between nodes so worker cancellation
 * stays responsive. Mutations are undone via the trail before frames return,
 * so state is consistent at every yield boundary.
 */
function* searchGenerator(
  index: IndexedRequest,
  request: FillRequest,
  state: SearchState,
  signal: AbortSignal | undefined,
  maxNodes: number
): Generator<void, void, void> {
  state.nodes += 1;
  if (signal?.aborted) {
    state.cancelled = true;
    return;
  }
  if (state.nodes > maxNodes) {
    state.overBudget = true;
    return;
  }
  if (state.best !== undefined && state.score + remainingScoreUpperBound(index, state) <= state.bestScore) return;

  const slotIndex = selectSlot(index, state);
  yield;
  if (state.cancelled || state.overBudget) return;
  if (slotIndex < 0) {
    if (state.score >= (request.minimumAssignmentScore ?? Number.NEGATIVE_INFINITY)) {
      const result: Record<string, FillCandidate> = {};
      for (let slot = 0; slot < index.slots.length; slot += 1) {
        result[index.slotIds[slot]!] = index.candidates[state.assignments[slot]!]!;
      }
      if (state.best === undefined || state.score > state.bestScore) {
        state.best = { assignments: result, score: state.score, nodes: state.nodes };
        state.bestScore = state.score;
      }
      // An explicit assignment-score bound turns the search into "first
      // acceptable fill wins"; without one, branch and bound keeps maximizing.
      if (request.minimumAssignmentScore !== undefined && state.score >= request.minimumAssignmentScore) {
        state.satisfied = true;
      }
    }
    return;
  }

  // The assigned slot's domain is narrowed to the singleton chosen candidate
  // (word-level trail edits): later propagation through this slot then sees
  // the fixed letters and prunes crossings correctly.
  const domain = state.domains[slotIndex]!;
  const slotLength = index.slots[slotIndex]!.length;
  const slotClass = index.lengthClasses.get(slotLength)!;
  for (let wordIndex = 0; wordIndex < domain.length; wordIndex += 1) {
    let word = domain[wordIndex]!;
    while (word !== 0) {
      const lowest = word & -word;
      word ^= lowest;
      if (state.cancelled || state.overBudget || state.satisfied) return;
      const localIndex = (wordIndex << 5) + (31 - Math.clz32(lowest));
      const candidateIndex = slotClass.globalByLocal[localIndex]!;
      const candidate = index.candidates[candidateIndex]!;
      const trailBase = state.trail.length;
      state.assignments[slotIndex] = candidateIndex;
      // Narrow this slot's domain to the singleton (word-level trail edits).
      for (let w = 0; w < domain.length; w += 1) {
        const keep = w === wordIndex ? lowest : 0;
        const extra = domain[w]! & ~keep;
        if (extra !== 0) removeWordBits(state, slotIndex, w, extra);
      }

      // All-different: a used word may not repeat in another slot. Only
      // same-length slots can contain the same surface, and they share the
      // length class's local index space.
      let viable = true;
      for (let other = 0; other < index.slots.length && viable; other += 1) {
        if (other === slotIndex) continue;
        if (index.slots[other]!.length !== slotLength) continue;
        removeSingleBit(state, other, localIndex);
        viable = state.sizes[other]! > 0;
      }
      if (viable) viable = propagateFrom(index, state, [slotIndex]);
      if (viable) {
        state.score += index.scoreByIndex[candidateIndex]!;
        yield* searchGenerator(index, request, state, signal, maxNodes);
        state.score -= index.scoreByIndex[candidateIndex]!;
      }
      state.assignments[slotIndex] = -1;
      undoTrail(state, trailBase);
    }
  }
}

function buildInitialState(
  index: IndexedRequest,
  request: FillRequest
): SearchState | { failure: FillResult['failure'] } {
  const domains: Bits[] = [];
  for (const slot of request.slots) {
    const lengthClass = index.lengthClasses.get(slot.length)!;
    const domain = new Uint32Array(lengthClass.words);
    const lockWord = request.lockedWords?.[slot.id];
    if (lockWord !== undefined) {
      const lockedGlobal = index.candidateIndexByWord.get(lockWord.trim().toUpperCase());
      if (lockedGlobal === undefined) return { failure: { code: 'unsatisfiable', message: `Lock for slot ${slot.id} has no candidate`, nodes: 0 } };
      const lockedLocal = lengthClass.localIndexByGlobal.get(lockedGlobal)!;
      domain[lockedLocal >>> 5] = domain[lockedLocal >>> 5]! | (1 << (lockedLocal & 31));
      domains.push(domain);
      continue;
    }
    lengthClass.globalByLocal.forEach((candidateIndex, localIndex) => {
      const candidate = index.candidates[candidateIndex]!;
      if (slot.pattern && [...slot.pattern].some((letter, position) => letter !== '.' && candidate.normalizedWord[position] !== letter)) return;
      domain[localIndex >>> 5] = domain[localIndex >>> 5]! | (1 << (localIndex & 31));
    });
    domains.push(domain);
  }
  const state: SearchState = {
    domains,
    sizes: new Int32Array(domains.map((domain) => {
      let count = 0;
      for (let wordIndex = 0; wordIndex < domain.length; wordIndex += 1) {
        let word = domain[wordIndex]!;
        while (word !== 0) {
          word &= word - 1;
          count += 1;
        }
      }
      return count;
    })),
    assignments: new Int32Array(request.slots.length).fill(-1),
    trail: [],
    nodes: 0,
    score: 0,
    cancelled: false,
    overBudget: false,
    satisfied: false,
    best: undefined,
    bestScore: Number.NEGATIVE_INFINITY
  };
  const allSlots = request.slots.map((_, slotIndex) => slotIndex);
  if (!propagateFrom(index, state, allSlots)) {
    return { failure: { code: 'unsatisfiable', message: 'Initial crossing constraints have no solution', nodes: state.nodes } };
  }
  return state;
}

function failureFor(state: SearchState, nodes: number): FillResult['failure'] {
  if (state.cancelled) return { code: 'cancelled', message: 'Fill search cancelled', nodes };
  if (state.overBudget) return { code: 'resource-limit', message: 'Fill search reached its node budget', nodes };
  return { code: 'unsatisfiable', message: 'No valid fill satisfies the constraints', nodes };
}

export function solveFill(request: FillRequest, options: FillOptions = {}): FillResult {
  const indexed = createIndex(request);
  if ('failure' in indexed) return { status: 'failed', failure: indexed.failure };
  const initial = buildInitialState(indexed, request);
  if ('failure' in initial) return { status: 'failed', failure: initial.failure };
  const state = initial;

  const generator = searchGenerator(indexed, request, state, options.signal, request.maxNodes ?? 50_000);
  let finished = generator.next();
  while (!finished.done) {
    if (options.signal?.aborted) state.cancelled = true;
    options.onProgress?.({
      type: 'progress',
      nodes: state.nodes,
      assigned: assignedCount(state),
      openSlots: indexed.slots.length - assignedCount(state),
      bestScore: state.bestScore
    });
    finished = generator.next();
  }

  if (state.best) return { status: 'solved', solution: state.best };
  return { status: 'failed', failure: failureFor(state, state.nodes) };
}

function yieldToHost(): Promise<void> {
  const host = globalThis as typeof globalThis & { setTimeout?: (callback: () => void, delayMs: number) => unknown };
  return typeof host.setTimeout === 'function'
    ? new Promise((resolve) => host.setTimeout!(resolve, 0))
    : Promise.resolve();
}

export async function solveFillAsync(request: FillRequest, options: FillOptions = {}): Promise<FillResult> {
  const indexed = createIndex(request);
  if ('failure' in indexed) return { status: 'failed', failure: indexed.failure };
  const initial = buildInitialState(indexed, request);
  if ('failure' in initial) return { status: 'failed', failure: initial.failure };
  const state = initial;

  const generator = searchGenerator(indexed, request, state, options.signal, request.maxNodes ?? 50_000);
  let step = 0;
  let finished = generator.next();
  while (!finished.done) {
    step += 1;
    if (step % 32 === 0) await yieldToHost();
    if (options.signal?.aborted) state.cancelled = true;
    options.onProgress?.({
      type: 'progress',
      nodes: state.nodes,
      assigned: assignedCount(state),
      openSlots: indexed.slots.length - assignedCount(state),
      bestScore: state.bestScore
    });
    finished = generator.next();
  }

  if (state.best) return { status: 'solved', solution: state.best };
  return { status: 'failed', failure: failureFor(state, state.nodes) };
}
