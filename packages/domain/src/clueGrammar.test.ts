import { describe, expect, it } from 'vitest';
import {
  CLUE_GRAMMAR_VERSION,
  validateClueGrammar,
  type ClueGrammarAnnotation,
  type ClueSignalSpan,
  type GrammarFeatures,
} from './clueGrammar';

const nounPlural: GrammarFeatures = { partOfSpeech: 'noun', number: 'plural' };

function definition(
  overrides: Partial<ClueGrammarAnnotation> = {},
): ClueGrammarAnnotation {
  const clueText = 'Purring pets';
  return {
    grammarVersion: CLUE_GRAMMAR_VERSION,
    clueId: 'clue-1a',
    entryId: 'entry-1a',
    clueText,
    answer: 'CATS',
    variantRole: 'standard',
    primaryFamily: 'definition',
    morphology: {
      clue: nounPlural,
      answer: nounPlural,
      substitutionWitness: {
        frame: 'We heard {0} outside.',
        cluePhrase: clueText,
        answerPhrase: 'CATS',
        editorialNote: 'Both forms occupy the same plural noun slot.',
        reviewerId: 'editor-17',
      },
    },
    signalSpans: [],
    ...overrides,
  };
}

function span(
  text: string,
  kind: ClueSignalSpan['kind'],
  extra: Record<string, unknown> = {},
): ClueSignalSpan {
  return {
    id: 'signal-1',
    kind,
    start: 0,
    end: text.length,
    text,
    ...extra,
  } as ClueSignalSpan;
}

function codes(
  value: unknown,
  context: Parameters<typeof validateClueGrammar>[1] = {},
) {
  return validateClueGrammar(value, context).issues.map(({ code }) => code);
}

describe('clue grammar v1', () => {
  it('keeps clue family separate from the displayed variant role and reports semantic limits', () => {
    const result = validateClueGrammar(
      definition({ variantRole: 'context-hint' }),
    );

    expect(result.valid).toBe(true);
    expect(result.semanticStatus).toBe('not-established');
  });

  it('rejects an answer and its obvious lexical form in the clue text', () => {
    const result = validateClueGrammar(
      definition({
        clueText: 'Shades of red',
        answer: 'REDS',
        morphology: {
          clue: nounPlural,
          answer: nounPlural,
          substitutionWitness: {
            frame: 'We compared {0}.',
            cluePhrase: 'Shades of red',
            answerPhrase: 'REDS',
            editorialNote: 'The fixture intentionally repeats the answer root.',
            reviewerId: 'editor-1',
          },
        },
      }),
      { enforceAnswerSafety: true },
    );

    expect(result.valid).toBe(false);
    expect(result.issues.map(({ code }) => code)).toContain('answer-form-in-clue');
  });

  it('rejects dead-end generic name and term templates', () => {
    expect(codes(definition({ clueText: 'common name' }), { enforceAnswerSafety: true })).toContain('generic-clue');
    expect(codes(definition({ clueText: "singer's name" }), { enforceAnswerSafety: true })).toContain('generic-clue');
  });

  it('rejects visible plural and past-tense markers that contradict the answer shape', () => {
    expect(
      codes(
        definition({ clueText: 'Felines (pl.)', answer: 'CAT' }),
        { enforceAnswerSafety: true },
      ),
    ).toContain('plural-marker-mismatch');
    expect(
      codes(
        definition({ clueText: 'Move (past tense)', answer: 'RUN' }),
        { enforceAnswerSafety: true },
      ),
    ).toContain('past-tense-marker-mismatch');
    expect(
      codes(
        definition({ clueText: 'Move (past tense)', answer: 'RAN' }),
        { enforceAnswerSafety: true },
      ),
    ).not.toContain('past-tense-marker-mismatch');
  });

  it('accepts an irregular plural when both annotated readings are plural', () => {
    const clueText = 'More than one goose';
    const result = validateClueGrammar(
      definition({
        clueText,
        answer: 'GEESE',
        morphology: {
          clue: { partOfSpeech: 'noun', number: 'plural' },
          answer: { partOfSpeech: 'noun', number: 'plural' },
          substitutionWitness: {
            frame: 'We saw {0} near the pond.',
            cluePhrase: clueText,
            answerPhrase: 'GEESE',
            editorialNote:
              'This plural is irregular; suffix spelling is irrelevant.',
            reviewerId: 'editor-2',
          },
        },
      }),
    );

    expect(result.valid).toBe(true);
  });

  it('rejects singular wording for a plural answer instead of guessing from a final S', () => {
    const invalid = definition({
      clueText: 'Pet that purrs',
      morphology: {
        clue: { partOfSpeech: 'noun', number: 'singular' },
        answer: { partOfSpeech: 'noun', number: 'plural' },
        substitutionWitness: {
          frame: 'We heard {0} outside.',
          cluePhrase: 'Pet that purrs',
          answerPhrase: 'CATS',
          editorialNote: 'Intentionally incorrect number fixture.',
          reviewerId: 'editor-17',
        },
      },
    });

    expect(codes(invalid)).toContain('morphology-mismatch');
  });

  it('allows a lexically invariant answer when the intended reading is explicitly plural', () => {
    const result = validateClueGrammar(
      definition({
        clueText: 'Forest animals',
        answer: 'DEER',
        morphology: {
          clue: { partOfSpeech: 'noun', number: 'plural' },
          answer: { partOfSpeech: 'noun', number: 'invariant' },
          substitutionWitness: {
            frame: 'We watched {0} cross.',
            cluePhrase: 'Forest animals',
            answerPhrase: 'DEER',
            editorialNote: 'Deer is invariant in this plural reading.',
            reviewerId: 'editor-3',
          },
        },
      }),
    );

    expect(result.valid).toBe(true);
  });

  it('accepts a matching irregular verb tense with a substitution frame', () => {
    const verbPast = {
      partOfSpeech: 'verb',
      number: 'singular',
      tense: 'past',
      aspect: 'simple',
      person: 3,
    } as const;
    const clueText = 'Devoured';
    const result = validateClueGrammar(
      definition({
        clueText,
        answer: 'ATE',
        morphology: {
          clue: verbPast,
          answer: verbPast,
          substitutionWitness: {
            frame: 'Yesterday, she {0} lunch.',
            cluePhrase: clueText,
            answerPhrase: 'ATE',
            editorialNote:
              'Both past-tense forms fit the same subject and object.',
            reviewerId: 'editor-4',
          },
        },
      }),
    );

    expect(result.valid).toBe(true);
  });

  it('rejects a tense mismatch and an unsupported noun-to-verb switch', () => {
    const tenseMismatch = definition({
      morphology: {
        clue: {
          partOfSpeech: 'verb',
          number: 'singular',
          tense: 'present',
          aspect: 'simple',
          person: 3,
        },
        answer: {
          partOfSpeech: 'verb',
          number: 'singular',
          tense: 'past',
          aspect: 'simple',
          person: 3,
        },
        substitutionWitness: {
          frame: 'She {0} every day.',
          cluePhrase: 'Purring pets',
          answerPhrase: 'CATS',
          editorialNote: 'Mismatch fixture.',
          reviewerId: 'editor-1',
        },
      },
    });
    const posSwitch = definition({
      morphology: {
        clue: { partOfSpeech: 'noun', number: 'singular' },
        answer: { partOfSpeech: 'verb', number: 'not-applicable' },
        substitutionWitness: {
          frame: 'They {0} at dusk.',
          cluePhrase: 'Purring pets',
          answerPhrase: 'CATS',
          editorialNote: 'No construction is given.',
          reviewerId: 'editor-1',
        },
      },
    });

    expect(codes(tenseMismatch)).toContain('morphology-mismatch');
    expect(codes(posSwitch)).toContain('unsupported-part-of-speech-switch');

    const supportedPhraseResponse = definition({
      clueText: 'Thank you, in German',
      answer: 'DANKE',
      morphology: {
        clue: { partOfSpeech: 'phrase', number: 'not-applicable' },
        answer: { partOfSpeech: 'interjection', number: 'not-applicable' },
        substitutionWitness: {
          frame: 'Say {0} to show gratitude.',
          cluePhrase: 'Thank you, in German',
          answerPhrase: 'DANKE',
          editorialNote:
            'A language-labeled phrase asks for a spoken response.',
          reviewerId: 'editor-9',
        },
        constructionWitness: {
          kind: 'phrase-response',
          cluePartOfSpeech: 'phrase',
          answerPartOfSpeech: 'interjection',
          exampleFrame: 'Say {0} when someone helps.',
          explanation:
            'The answer is a one-word utterance that fills the phrase response slot.',
          reviewerId: 'editor-9',
        },
      },
    });
    expect(validateClueGrammar(supportedPhraseResponse).valid).toBe(true);
  });

  it('requires tense, aspect, and person annotations whenever a verb reading is recorded', () => {
    const missingVerbFeatures = definition({
      morphology: {
        clue: { partOfSpeech: 'verb', number: 'singular' },
        answer: { partOfSpeech: 'verb', number: 'singular' },
        substitutionWitness: {
          frame: 'She {0} every day.',
          cluePhrase: 'Purring pets',
          answerPhrase: 'CATS',
          editorialNote: 'Verb features intentionally omitted.',
          reviewerId: 'editor-1',
        },
      },
    });

    expect(codes(missingVerbFeatures)).toContain('missing-verb-morphology');
  });

  it('requires an explicit resolution for an ambiguous noun/verb reading', () => {
    const ambiguous = definition({
      morphology: {
        clue: { partOfSpeech: 'ambiguous', number: 'singular' },
        answer: { partOfSpeech: 'noun', number: 'singular' },
        substitutionWitness: {
          frame: 'The {0} is ready.',
          cluePhrase: 'Purring pets',
          answerPhrase: 'CATS',
          editorialNote: 'A deliberately ambiguous surface.',
          reviewerId: 'editor-8',
        },
      },
    });
    expect(codes(ambiguous)).toContain('missing-ambiguity-witness');

    const resolved = definition({
      morphology: {
        ...ambiguous.morphology!,
        ambiguityWitnesses: [
          {
            dimension: 'partOfSpeech',
            resolvedAs: 'noun',
            explanation: 'The intended reading is a noun phrase.',
            reviewerId: 'editor-8',
          },
        ],
      },
    });
    expect(validateClueGrammar(resolved).valid).toBe(true);
  });

  it('requires literal whole-clue speech quotes and keeps title quotes distinct', () => {
    const utterance = '“Not a chance!”';
    const spoken = definition({
      clueText: utterance,
      answer: 'NO WAY',
      primaryFamily: 'spoken-equivalent',
      morphology: undefined,
      interpretation: {
        intendedSense: 'a spoken refusal',
        intendedReading: 'a refusal',
        explanation:
          'Use another expression a person could say in the same situation.',
      },
      signalSpans: [span(utterance, 'quote', { role: 'spoken-equivalent' })],
    });
    expect(validateClueGrammar(spoken).valid).toBe(true);

    const titleText = 'Word before “rain” in “acid rain”';
    const quoteStart = titleText.indexOf('“');
    const quoteEnd = titleText.indexOf('”') + 1;
    const title = definition({
      clueText: titleText,
      answer: 'ACID',
      primaryFamily: 'factual-relation',
      morphology: undefined,
      signalSpans: [
        span(titleText.slice(quoteStart, quoteEnd), 'quote', {
          id: 'title-quote',
          role: 'title',
          start: quoteStart,
          end: quoteEnd,
        }),
      ],
    });
    expect(validateClueGrammar(title).valid).toBe(true);

    const inlineSpeech = { ...spoken, clueText: 'She said “not a chance”' };
    expect(codes(inlineSpeech)).toContain('missing-whole-quote');
  });

  it('requires literal whole square brackets for a nonverbal action', () => {
    const clueText = '[Sigh of relief]';
    const nonverbal = definition({
      clueText,
      answer: 'PHEW',
      primaryFamily: 'nonverbal-expression',
      morphology: undefined,
      interpretation: {
        intendedSense: 'a relieved exhalation written as letters',
        intendedReading: 'relief sound',
        explanation:
          'The bracketed clue is an action or sound rather than speech.',
      },
      signalSpans: [
        span(clueText, 'brackets', { role: 'nonverbal-expression' }),
      ],
    });
    expect(validateClueGrammar(nonverbal).valid).toBe(true);
    expect(
      codes({ ...nonverbal, clueText: 'Editorial note: [Sigh of relief]' }),
    ).toContain('missing-whole-brackets');
  });

  it('requires a two-reading explanation for question-mark wordplay', () => {
    const pun = definition({
      clueText: 'Branch specialist?',
      answer: 'ARBORIST',
      primaryFamily: 'pun',
      morphology: undefined,
      interpretation: {
        intendedSense: 'a tree-care professional',
        surfaceReading: 'a specialist in a branch of study',
        intendedReading: 'a professional who works with tree branches',
        explanation:
          'The word branch shifts from a field of study to part of a tree.',
      },
    });
    expect(validateClueGrammar(pun).valid).toBe(true);
    expect(
      codes({
        ...pun,
        interpretation: {
          intendedSense: 'tree-care professional',
          explanation: 'This answer is a fact.',
        },
      }),
    ).toContain('unexplained-question-mark');
    expect(codes(pun, { punQuestionMarkPolicy: 'forbidden' })).toContain(
      'pun-question-mark-policy',
    );

    const unsignaled = { ...pun, clueText: 'Branch specialist' };
    expect(validateClueGrammar(unsignaled).valid).toBe(true);
    expect(codes(unsignaled, { punQuestionMarkPolicy: 'required' })).toContain(
      'pun-question-mark-policy',
    );
  });

  it('does not let a factual clue use a question mark as a repair for weak wording', () => {
    const clue = definition({
      clueText: 'Famous botanist?',
      answer: 'LINNAEUS',
      primaryFamily: 'factual-relation',
      morphology: undefined,
    });
    expect(codes(clue)).toContain('unexplained-question-mark');
  });

  it('requires an actual abbreviation indicator, not an unrelated acronym nearby', () => {
    const clueText = 'Estimated arrival, briefly';
    const indicatorStart = clueText.indexOf('briefly');
    const abbreviated = definition({
      clueText,
      answer: 'ETA',
      primaryFamily: 'factual-relation',
      morphology: undefined,
      answerIsAbbreviation: true,
      abbreviationEvidence: { kind: 'indicator-span', spanId: 'briefly' },
      signalSpans: [
        span('briefly', 'abbreviation-indicator', {
          id: 'briefly',
          start: indicatorStart,
          end: indicatorStart + 7,
        }),
      ],
    });
    expect(validateClueGrammar(abbreviated).valid).toBe(true);

    const unrelatedAcronym = definition({
      clueText: "OPEC delegate's arrival",
      answer: 'ETA',
      primaryFamily: 'factual-relation',
      morphology: undefined,
      answerIsAbbreviation: true,
    });
    expect(codes(unrelatedAcronym)).toContain('missing-abbreviation-indicator');
  });

  it('requires a language signal for a language-specific answer', () => {
    const clueText = 'Thank you, in German';
    const start = clueText.indexOf('in German');
    const clue = definition({
      clueText,
      answer: 'DANKE',
      primaryFamily: 'factual-relation',
      morphology: {
        clue: {
          partOfSpeech: 'phrase',
          number: 'not-applicable',
          language: 'en',
        },
        answer: {
          partOfSpeech: 'interjection',
          number: 'not-applicable',
          language: 'de',
        },
        constructionWitness: {
          kind: 'phrase-response',
          cluePartOfSpeech: 'phrase',
          answerPartOfSpeech: 'interjection',
          exampleFrame: 'Say {0} to express thanks.',
          explanation: 'A phrase can be answered by an interjection.',
          reviewerId: 'editor-9',
        },
      },
      signalSpans: [
        span('in German', 'language-indicator', {
          id: 'language',
          start,
          end: start + 9,
          language: 'de',
        }),
      ],
    });
    expect(validateClueGrammar(clue).valid).toBe(true);
    expect(codes({ ...clue, signalSpans: [] })).toContain(
      'missing-language-indicator',
    );
  });

  it('checks a cross-reference against the live entry IDs and numbering', () => {
    const clueText = 'See 12-Down';
    const start = clueText.indexOf('12-Down');
    const linked = definition({
      clueText,
      primaryFamily: 'linked',
      morphology: undefined,
      signalSpans: [
        span('12-Down', 'cross-reference', {
          id: 'ref-12d',
          start,
          end: start + 7,
          targetEntryId: 'entry-12d',
          displayedNumber: 12,
          direction: 'down',
        }),
      ],
    });
    const entries = [
      { entryId: 'entry-12d', number: 12, direction: 'down' as const },
    ];
    expect(validateClueGrammar(linked, { entries }).valid).toBe(true);
    expect(codes(linked, { entries: [] })).toContain(
      'missing-reference-target',
    );
    expect(
      codes(linked, { entries: [{ ...entries[0]!, number: 13 }] }),
    ).toContain('stale-cross-reference');
    const textMismatch = {
      ...linked,
      clueText: 'See 13-Down',
      signalSpans: [
        span('13-Down', 'cross-reference', {
          id: 'ref-12d',
          start,
          end: start + 7,
          targetEntryId: 'entry-12d',
          displayedNumber: 12,
          direction: 'down',
        }),
      ],
    };
    expect(codes(textMismatch, { entries })).toContain('stale-cross-reference');
    expect(codes(linked)).toContain('missing-reference-context');
  });

  it('requires a matching declared theme mechanic and its cue obligation', () => {
    const clueText = 'Twist the final letter';
    const cueStart = clueText.indexOf('Twist');
    const themeClue = definition({
      clueText,
      primaryFamily: 'theme-dependent',
      morphology: undefined,
      interpretation: {
        intendedSense: 'the theme answer changes its final letter',
        intendedReading: 'apply the puzzle transformation',
        explanation:
          'The declared transformation changes the final letter of this entry.',
      },
      mechanicRef: {
        mechanicId: 'last-letter-shift',
        explanation: 'Apply the puzzle’s announced letter shift.',
      },
      signalSpans: [
        span('Twist', 'mechanic-indicator', {
          id: 'mechanic-cue',
          start: cueStart,
          end: cueStart + 5,
        }),
      ],
    });
    const mechanics = [
      {
        id: 'last-letter-shift',
        family: 'letter-shift',
        affectedEntryIds: ['entry-1a'],
        requiredSignal: 'mechanic-indicator' as const,
        explanationRequired: true,
      },
    ];
    expect(validateClueGrammar(themeClue, { mechanics }).valid).toBe(true);
    expect(
      codes(
        {
          ...themeClue,
          primaryFamily: 'factual-relation',
          mechanicRef: undefined,
        },
        { mechanics },
      ),
    ).toContain('missing-mechanic-reference');
    expect(
      codes({ ...themeClue, mechanicRef: undefined }, { mechanics }),
    ).toContain('missing-mechanic-reference');
    expect(
      codes(themeClue, {
        mechanics: [{ ...mechanics[0]!, id: 'different-mechanic' }],
      }),
    ).toContain('unknown-mechanic');
    expect(
      codes(themeClue, {
        mechanics: [{ ...mechanics[0]!, affectedEntryIds: ['other-entry'] }],
      }),
    ).toContain('mechanic-not-applicable');
    expect(
      codes(themeClue, {
        mechanics: [{ ...mechanics[0]!, requiredSignal: 'theme-indicator' }],
      }),
    ).toContain('missing-mechanic-signal');
  });

  it('requires explicit signals for fill-in-the-blank and metalinguistic clue families', () => {
    const fill = definition({
      clueText: 'Safe and ___',
      answer: 'SOUND',
      primaryFamily: 'fill-blank',
      signalSpans: [],
    });
    const meta = definition({
      clueText: 'A word for “small”',
      primaryFamily: 'metalinguistic',
    });

    expect(codes(fill)).toContain('missing-fill-blank-signal');
    expect(codes(meta)).toContain('missing-metalinguistic-signal');
  });
});
