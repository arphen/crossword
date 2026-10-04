const TIER_COPY = {
  'clue-reading': {
    label: 'How to read this clue',
    hintId: 'prepared-clue-reading-v1',
  },
  context: {
    label: 'A little more context',
    hintId: 'prepared-context-v1',
  },
  crossing: {
    label: 'Suggest a crossing',
    hintId: 'prepared-crossing-v1',
  },
  letter: {
    label: 'Reveal a letter',
    hintId: 'prepared-letter-v1',
  },
  answer: {
    label: 'Reveal this answer',
    hintId: 'prepared-answer-v1',
  },
};

function entryId(entry) {
  return `${entry.direction}-${entry.clue_number}`;
}

function entryCellIds(entry) {
  return entry.characters.map((_, index) =>
    entry.direction === 'across'
      ? `r${entry.start_y}c${entry.start_x + index}`
      : `r${entry.start_y + index}c${entry.start_x}`,
  );
}

function clueReading(clue) {
  if (/^Entry supported by its crossings \([1-9][0-9]* letters\)$/i.test(clue)) {
    return 'This entry is using an answer-free scaffold because its original surface was not safe to keep. Start with a crossing that has letters in place; the ladder can reveal one letter only after you have tried the structural route.';
  }
  const notes = [];
  if (clue.includes('?')) {
    notes.push(
      'The question mark gives permission to let the clue turn sideways. Try a phrase or a playful reading rather than a strict definition.',
    );
  }
  if (/['“”"]/.test(clue)) {
    notes.push(
      'Quotation marks usually point toward something that could be said aloud. Try hearing the answer as a small utterance.',
    );
  }
  if (/\[[^\]]+\]/.test(clue)) {
    notes.push(
      'Square brackets often describe a sound, gesture, or editorial aside. Read the bracketed part as a cue about how the answer appears.',
    );
  }
  if (/\b(?:abbr\.?|briefly|initially)\b/i.test(clue)) {
    notes.push(
      'The clue signals a shortened form. Look for a compact answer rather than spelling out the whole phrase.',
    );
  }
  if (/(?:\[|\()\s*pl\.?\s*(?:\]|\))/i.test(clue)) {
    notes.push(
      'The plural marker is a contract: the answer should name more than one thing. Let the crossings confirm the number.',
    );
  }
  const language = clue.match(
    /\b(?:in|from)\s+(Dutch|French|German|Italian|Portuguese|Spanish|Japanese)\b/i,
  );
  if (language) {
    notes.push(
      `${language[1]} marks the language of the answer. Keep the clue’s meaning in view, then use the crossings to choose the foreign form.`,
    );
  }
  if (/_{2,}|\b(?:and|or|to|of)\s+___\b/i.test(clue)) {
    notes.push(
      'A blank signals a phrase with a missing piece. Read the words around it as one surface and let the grid supply the shape.',
    );
  }
  if (notes.length) return notes.slice(0, 2).join(' ');
  return 'Try the clue’s clearest surface first; its tense and number should agree with the answer. Then let the crossings decide which sense belongs here. The nudge keeps the answer hidden.';
}

/**
 * Return the small, answer-free assistance ladder for an active legacy clue.
 * These are authored client-side fallbacks until generated manifests carry
 * explicit clue variants; their IDs are still stable and journaled.
 */
export function assistanceLadder(app, entry) {
  if (!entry) return [];
  const clue = String(entry.clue_text || '').trim();
  const hasTokenCell = entry.characters.some(
    (character) =>
      character?.tokenMetadata?.rebus === true ||
      String(character?.letters || '').length > 1,
  );
  const cells = entryCellIds(entry);
  const crossingCells = cells.filter((cellId) =>
    (app.crossword || []).some(
      (candidate) =>
        entryId(candidate) !== entryId(entry) &&
        entryCellIds(candidate).includes(cellId) &&
        Boolean(
          app.grid?.[Number(cellId.match(/^r(\d+)/)?.[1])]?.[
            Number(cellId.match(/c(\d+)$/)?.[1])
          ],
        ),
    ),
  );
  const crossingEntry = (app.crossword || [])
    .filter((candidate) => entryId(candidate) !== entryId(entry))
    .map((candidate) => ({
      candidate,
      filled: entryCellIds(candidate).filter((cellId) => {
        const match = /^r(\d+)c(\d+)$/.exec(cellId);
        return Boolean(match && app.grid?.[Number(match[1])]?.[Number(match[2])]);
      }).length,
      shared: entryCellIds(candidate).filter((cellId) => cells.includes(cellId)),
    }))
    .filter((item) => item.shared.length > 0)
    .sort((left, right) => right.filled - left.filled || right.shared.length - left.shared.length)[0]
    ?.candidate;
  const crossingLabel = crossingEntry
    ? `${crossingEntry.direction === 'across' ? 'Across' : 'Down'} ${crossingEntry.clue_number}`
    : null;
  /** @type {Array<{assistanceTier: string, text: string, affectedCellIds: string[], label: string, hintId: string, reveal?: 'letter' | 'answer'}>} */
  const ladder = [
    {
      ...TIER_COPY['clue-reading'],
      assistanceTier: 'clue-reading',
      text: clueReading(clue),
      affectedCellIds: [],
    },
  ];
  if (crossingCells.length) {
    ladder.push({
      ...TIER_COPY.context,
      assistanceTier: 'context',
      text: 'A crossing is already giving you structure. Use its letters as a pattern and return to the clue; the intended answer should become narrower without being handed over.',
      affectedCellIds: crossingCells,
    });
    ladder.push({
      ...TIER_COPY.crossing,
      assistanceTier: 'crossing',
      text: crossingLabel
        ? `Try ${crossingLabel}; it shares ${crossingCells.length === 1 ? 'a square' : 'squares'} with this entry and may open the route.`
        : 'Try a crossing clue with a few letters already in place. The suggested route stays yours to solve.',
      affectedCellIds: crossingCells,
    });
  }
  ladder.push({
    ...TIER_COPY.letter,
    label: hasTokenCell ? 'Reveal a token' : TIER_COPY.letter.label,
    assistanceTier: 'letter',
    text: hasTokenCell
      ? 'One empty square will be filled with its declared token. Keep reading the clue and let that unit do only part of the work.'
      : 'One empty square will be filled. Keep reading the clue and let that letter do only part of the work.',
    affectedCellIds: cells,
    reveal: 'letter',
  });
  ladder.push({
    ...TIER_COPY.answer,
    assistanceTier: 'answer',
    text: 'The remaining empty squares in this entry will be filled. You can still study how the clue and crossings led there.',
    affectedCellIds: cells,
    reveal: 'answer',
  });
  return ladder;
}
