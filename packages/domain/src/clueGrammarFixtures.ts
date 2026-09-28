import type {
  ClueFamily,
  ClueGrammarAnnotation,
  ClueGrammarContext,
  ClueGrammarIssueCode,
  ClueSignalSpan,
} from './clueGrammar';
import { CLUE_GRAMMAR_VERSION } from './clueGrammar';

/**
 * Original, answer-visible fixtures for the house grammar.
 *
 * These are structural fixtures, not a semantic truth set.  A `valid` case
 * means that the annotation is internally consistent with the rendered clue
 * and its declared puzzle context.  It does not mean that the clue is fair,
 * that the sense is true, or that a player would find the answer.
 */
export type ClueGrammarFixture = Readonly<{
  id: string;
  family: ClueFamily;
  valid: boolean;
  annotation: ClueGrammarAnnotation;
  context?: ClueGrammarContext;
  intendedReading: string;
  defectOrReason: string;
  repair: string;
  expectedIssues: readonly ClueGrammarIssueCode[];
}>;

const nounPlural = { partOfSpeech: 'noun' as const, number: 'plural' as const };
const nounSingular = {
  partOfSpeech: 'noun' as const,
  number: 'singular' as const,
};
const nounMass = {
  partOfSpeech: 'noun' as const,
  number: 'mass' as const,
};
const adjectiveSingular = {
  partOfSpeech: 'adjective' as const,
  number: 'not-applicable' as const,
};
const verbPast = {
  partOfSpeech: 'verb' as const,
  number: 'singular' as const,
  tense: 'past' as const,
  aspect: 'simple' as const,
  person: 3 as const,
};
const verbPresent = {
  partOfSpeech: 'verb' as const,
  number: 'singular' as const,
  tense: 'present' as const,
  aspect: 'simple' as const,
  person: 3 as const,
};

function signal(
  id: string,
  text: string,
  kind: ClueSignalSpan['kind'],
  start = 0,
  extra: Record<string, unknown> = {},
): ClueSignalSpan {
  return {
    id,
    kind,
    start,
    end: start + text.length,
    text,
    ...extra,
  } as ClueSignalSpan;
}

function annotation(
  id: string,
  clueText: string,
  answer: string,
  primaryFamily: ClueFamily,
  overrides: Partial<ClueGrammarAnnotation> = {},
): ClueGrammarAnnotation {
  return {
    grammarVersion: CLUE_GRAMMAR_VERSION,
    clueId: `${id}-clue`,
    entryId: `${id}-entry`,
    clueText,
    answer,
    variantRole: 'standard',
    primaryFamily,
    signalSpans: [],
    ...overrides,
  };
}

function fixture(
  id: string,
  family: ClueFamily,
  valid: boolean,
  value: ClueGrammarAnnotation,
  intendedReading: string,
  defectOrReason: string,
  repair: string,
  expectedIssues: readonly ClueGrammarIssueCode[] = [],
  context?: ClueGrammarContext,
): ClueGrammarFixture {
  return {
    id,
    family,
    valid,
    annotation: value,
    ...(context ? { context } : {}),
    intendedReading,
    defectOrReason,
    repair,
    expectedIssues,
  };
}

function directDefinition(
  id: string,
  clueText: string,
  answer: string,
  clueMorphology: NonNullable<ClueGrammarAnnotation['morphology']>['clue'],
  answerMorphology: NonNullable<ClueGrammarAnnotation['morphology']>['answer'],
  frame: string,
  extra: Partial<ClueGrammarAnnotation['morphology']> = {},
): ClueGrammarAnnotation {
  return annotation(id, clueText, answer, 'definition', {
    morphology: {
      clue: clueMorphology,
      answer: answerMorphology,
      substitutionWitness: {
        frame,
        cluePhrase: clueText,
        answerPhrase: answer,
        editorialNote: 'The two readings occupy the same frame.',
        reviewerId: 'fixture-editor',
      },
      ...extra,
    },
  });
}

function fillBlank(
  id: string,
  clueText: string,
  answer: string,
  marker: string,
  markerStart = clueText.indexOf(marker),
): ClueGrammarAnnotation {
  return annotation(id, clueText, answer, 'fill-blank', {
    signalSpans: [signal(`${id}-blank`, marker, 'fill-blank', markerStart)],
  });
}

function spoken(
  id: string,
  clueText: string,
  answer: string,
  role: 'spoken-equivalent' | 'title' = 'spoken-equivalent',
): ClueGrammarAnnotation {
  return annotation(id, clueText, answer, 'spoken-equivalent', {
    interpretation: {
      intendedSense: 'a conversational equivalent',
      intendedReading: 'another thing someone could say in the same moment',
      explanation: 'The answer can replace the quoted utterance in context.',
    },
    signalSpans: [signal(`${id}-quote`, clueText, 'quote', 0, { role })],
  });
}

function nonverbal(
  id: string,
  clueText: string,
  answer: string,
): ClueGrammarAnnotation {
  return annotation(id, clueText, answer, 'nonverbal-expression', {
    interpretation: {
      intendedSense: 'a written reaction or sound',
      intendedReading: 'letters that express the bracketed action',
      explanation: 'The brackets describe an action rather than speech.',
    },
    signalSpans: [
      signal(`${id}-brackets`, clueText, 'brackets', 0, {
        role: 'nonverbal-expression',
      }),
    ],
  });
}

function wordplay(
  id: string,
  family: 'semantic-misdirection' | 'pun',
  clueText: string,
  answer: string,
  overrides: Partial<NonNullable<ClueGrammarAnnotation['interpretation']>> = {},
): ClueGrammarAnnotation {
  return annotation(id, clueText, answer, family, {
    interpretation: {
      intendedSense: 'the intended answer sense',
      surfaceReading: 'the ordinary first reading',
      intendedReading: 'the reading that resolves after the turn',
      explanation: 'The surface and intended readings point to related senses.',
      ...overrides,
    },
  });
}

function crossReference(
  id: string,
  clueText: string,
  answer: string,
  displayedNumber: number,
  direction: 'across' | 'down',
  targetEntryId: string,
  surfaceNumber = displayedNumber,
): ClueGrammarAnnotation {
  const targetText = `${surfaceNumber}-${direction[0]!.toUpperCase()}${direction.slice(1)}`;
  const start = clueText.indexOf(targetText);
  return annotation(id, clueText, answer, 'linked', {
    signalSpans: [
      signal(`${id}-reference`, targetText, 'cross-reference', start, {
        targetEntryId,
        displayedNumber,
        direction,
      }),
    ],
  });
}

const linkedEntries = [
  { entryId: 'entry-12-down', number: 12, direction: 'down' as const },
  { entryId: 'entry-7-across', number: 7, direction: 'across' as const },
  { entryId: 'entry-3-across', number: 3, direction: 'across' as const },
  { entryId: 'entry-18-down', number: 18, direction: 'down' as const },
];

const mechanic = {
  id: 'last-letter-turn',
  family: 'letter-shift',
  affectedEntryIds: [
    'theme-valid-first-entry',
    'theme-valid-second-entry',
    'theme-valid-third-entry',
    'theme-valid-fourth-entry',
    'theme-valid-fifth-entry',
    'theme-valid-sixth-entry',
    'theme-invalid-no-ref-entry',
    'theme-invalid-unknown-entry',
    'theme-invalid-signal-entry',
    'theme-invalid-explanation-entry',
    'theme-final-valid-adverb-entry',
    'theme-final-valid-register-entry',
    'theme-final-valid-prefix-entry',
    'theme-final-valid-suffix-entry',
    'theme-final-invalid-context-entry',
    'theme-final-invalid-signal-entry',
    'theme-final-invalid-explanation-entry',
    'theme-final-invalid-unknown-entry',
  ],
  requiredSignal: 'mechanic-indicator' as const,
  explanationRequired: true,
};

const themeContext = { mechanics: [mechanic] };

const definitions: ClueGrammarFixture[] = [
  fixture(
    'definition-valid-cats',
    'definition',
    true,
    directDefinition('definition-valid-cats', 'Purring pets', 'CATS', nounPlural, nounPlural, 'We heard {0} outside.'),
    'plural domestic animals that purr',
    'The clue and answer are plural nouns with a direct substitution frame.',
    'No repair; preserve the plural frame.',
  ),
  fixture(
    'definition-valid-geese',
    'definition',
    true,
    directDefinition('definition-valid-geese', 'More than one goose', 'GEESE', nounPlural, nounPlural, 'We saw {0} near the pond.'),
    'the irregular plural of goose',
    'The fixture checks plural agreement without relying on a final S.',
    'No repair; retain the explicit plural annotation.',
  ),
  fixture(
    'definition-valid-ate',
    'definition',
    true,
    directDefinition('definition-valid-ate', 'Devoured', 'ATE', verbPast, verbPast, 'Yesterday, she {0} lunch.'),
    'a past-tense verb meaning devoured',
    'Both sides record matching tense, aspect, person, and number.',
    'No repair; preserve the past-tense frame.',
  ),
  fixture(
    'definition-valid-silently',
    'definition',
    true,
    directDefinition(
      'definition-valid-silently',
      'Quietly',
      'SILENTLY',
      { partOfSpeech: 'adverb', number: 'not-applicable' },
      { partOfSpeech: 'adverb', number: 'not-applicable' },
      'They moved {0} through the hall.',
    ),
    'in a quiet manner',
    'Matching adverb roles do not need an invented special signal.',
    'No repair; preserve the adverb agreement.',
  ),
  fixture(
    'definition-invalid-number',
    'definition',
    false,
    directDefinition('definition-invalid-number', 'Pet that purrs', 'CATS', nounSingular, nounPlural, 'We heard {0} outside.'),
    'the intended answer is plural CATS',
    'The annotation silently changes singular clue wording into a plural answer.',
    'Change the clue to “Purring pets” or annotate a singular answer.',
    ['morphology-mismatch'],
  ),
  fixture(
    'definition-invalid-tense',
    'definition',
    false,
    directDefinition(
      'definition-invalid-tense',
      'Devours',
      'ATE',
      { partOfSpeech: 'verb', number: 'singular', tense: 'present', aspect: 'simple', person: 3 },
      verbPast,
      'Yesterday, she {0} lunch.',
    ),
    'the answer was intended as a past-tense verb',
    'The clue is present tense while the answer is past tense.',
    'Use EATS for the present clue or change the clue to “Devoured.”',
    ['morphology-mismatch'],
  ),
  fixture(
    'definition-invalid-witness',
    'definition',
    false,
    annotation('definition-invalid-witness', 'Purring pets', 'CATS', 'definition', {
      morphology: { clue: nounPlural, answer: nounPlural },
    }),
    'plural pets',
    'A direct definition has no editor-authored substitution witness.',
    'Add a frame, both substitutions, a note, and a reviewer ID.',
    ['missing-substitution-witness'],
  ),
  fixture(
    'definition-invalid-switch',
    'definition',
    false,
    directDefinition(
      'definition-invalid-switch',
      'Purring pets',
      'CATS',
      nounSingular,
      { partOfSpeech: 'verb', number: 'not-applicable' },
      'They {0} at dusk.',
    ),
    'the answer was incorrectly treated as a verb',
    'The annotation switches noun to verb without a construction witness and also changes number.',
    'Use a noun answer or add a reviewed conversion witness for a genuinely supported switch.',
    ['unsupported-part-of-speech-switch', 'morphology-mismatch'],
  ),
];

const factualRelations: ClueGrammarFixture[] = [
  fixture('factual-valid-amp', 'factual-relation', true, annotation('factual-valid-amp', 'Current unit', 'AMP', 'factual-relation'), 'a unit of electrical current', 'A concise factual relation has no special surface signal.', 'No repair; fact support belongs to the semantic review boundary.'),
  fixture('factual-valid-tree', 'factual-relation', true, annotation('factual-valid-tree', 'Oak, for one', 'TREE', 'factual-relation'), 'a category of which oak is an example', 'The example-to-category relation is represented as ordinary clue text.', 'No repair; preserve the relation direction for semantic review.'),
  fixture('factual-valid-title', 'factual-relation', true, annotation('factual-valid-title', 'Word before “rain” in “acid rain”', 'ACID', 'factual-relation', {
    signalSpans: [signal('factual-valid-title-quote-1', '“rain”', 'quote', 12, { role: 'mentioned-word' }), signal('factual-valid-title-quote-2', '“acid rain”', 'quote', 22, { role: 'title' })],
  }), 'the word before rain in the cited phrase', 'Quote roles distinguish mentioned language from a spoken-equivalent clue.', 'No repair; retain typed quote spans.'),
  fixture('factual-valid-language', 'factual-relation', true, annotation('factual-valid-language', 'Thank you, in German', 'DANKE', 'factual-relation', {
    morphology: { clue: { partOfSpeech: 'phrase', number: 'not-applicable', language: 'en' }, answer: { partOfSpeech: 'phrase', number: 'not-applicable', language: 'de' } },
    signalSpans: [signal('factual-valid-language-label', 'in German', 'language-indicator', 11, { language: 'de' })],
  }), 'the German phrase DANKE', 'The answer language is explicitly signaled in the clue.', 'No repair; semantic language and orthography review remains separate.'),
  fixture('factual-invalid-question', 'factual-relation', false, annotation('factual-invalid-question', 'Famous botanist?', 'LINNAEUS', 'factual-relation'), 'a factual identity clue', 'A question mark is being used to disguise an unreviewed factual assertion.', 'Remove the question mark or provide a reviewed pun annotation with two readings.', ['unexplained-question-mark']),
  fixture('factual-invalid-language', 'factual-relation', false, annotation('factual-invalid-language', 'Thank you, foreign', 'DANKE', 'factual-relation', { morphology: { clue: { partOfSpeech: 'phrase', number: 'not-applicable', language: 'en' }, answer: { partOfSpeech: 'phrase', number: 'not-applicable', language: 'de' } } }), 'the German answer DANKE', 'A language-specific answer has no language-indicator span.', 'Add a literal “in German” span or choose an answer in the clue language.', ['missing-language-indicator']),
  fixture('factual-invalid-abbreviation', 'factual-relation', false, annotation('factual-invalid-abbreviation', "OPEC delegate's arrival", 'ETA', 'factual-relation', { answerIsAbbreviation: true }), 'the abbreviation ETA', 'An unrelated acronym in the surface does not license an abbreviated answer.', 'Add an actual abbreviation indicator such as “briefly,” or use a full answer.', ['missing-abbreviation-indicator']),
  fixture('factual-invalid-span', 'factual-relation', false, annotation('factual-invalid-span', 'Current unit', 'AMP', 'factual-relation', { signalSpans: [signal('factual-invalid-span-signal', 'unit', 'language-indicator', 2, { language: 'de' })] }), 'a current unit', 'The signal span text and offsets do not describe the intended surface convention.', 'Remove the false language span or annotate the exact literal signal.', ['invalid-span']),
];

/**
 * A second authored layer keeps the release pack moving toward its planned
 * 20/20 per-family size without pretending that structural fixtures establish
 * a clue's truth or fairness.  These cases deliberately exercise different
 * morphology and literal-signal shapes from the smoke matrix above.
 */
const releasePackExpansionDefinitions: ClueGrammarFixture[] = [
  fixture(
    'definition-valid-open',
    'definition',
    true,
    directDefinition(
      'definition-valid-open',
      'Available',
      'OPEN',
      adjectiveSingular,
      adjectiveSingular,
      'The gate is {0}.',
    ),
    'an adjective meaning available',
    'Both sides occupy the same adjective slot in the editor frame.',
    'No repair; semantic support remains a separate review concern.',
  ),
  fixture(
    'definition-valid-runs',
    'definition',
    true,
    directDefinition(
      'definition-valid-runs',
      'Moves swiftly',
      'RUNS',
      verbPresent,
      verbPresent,
      'She {0} every morning.',
    ),
    'a present-tense verb for moving swiftly',
    'Present tense, aspect, person, and number agree on both sides.',
    'No repair; preserve the present-tense frame.',
  ),
  fixture(
    'definition-invalid-verb-fields',
    'definition',
    false,
    directDefinition(
      'definition-invalid-verb-fields',
      'Moves swiftly',
      'RUNS',
      { partOfSpeech: 'verb', number: 'singular' },
      { partOfSpeech: 'verb', number: 'singular' },
      'She {0} every morning.',
    ),
    'a present-tense verb for moving swiftly',
    'A verb annotation omits tense, aspect, and person on both sides.',
    'Record all required verb morphology before semantic review.',
    ['missing-verb-morphology'],
  ),
  fixture(
    'definition-invalid-pos-switch',
    'definition',
    false,
    directDefinition(
      'definition-invalid-pos-switch',
      'Available',
      'OPEN',
      { partOfSpeech: 'noun', number: 'not-applicable' },
      adjectiveSingular,
      'The gate is {0}.',
    ),
    'an adjective meaning available',
    'The answer changes part of speech without a construction witness.',
    'Add a reviewed conversion witness or keep both readings in one part of speech.',
    ['unsupported-part-of-speech-switch'],
  ),
];

const releasePackExpansionFactualRelations: ClueGrammarFixture[] = [
  fixture(
    'factual-valid-abbreviation',
    'factual-relation',
    true,
    annotation(
      'factual-valid-abbreviation',
      'Briefly, estimate',
      'ETA',
      'factual-relation',
      {
        answerIsAbbreviation: true,
        signalSpans: [
          signal('factual-valid-abbreviation-indicator', 'Briefly', 'abbreviation-indicator'),
        ],
        abbreviationEvidence: {
          kind: 'indicator-span',
          spanId: 'factual-valid-abbreviation-indicator',
        },
      },
    ),
    'an abbreviated form of an estimated arrival time',
    'The abbreviated answer has a literal indicator span and typed evidence.',
    'No repair; semantic expansion of the abbreviation remains separate.',
  ),
  fixture(
    'factual-valid-exception',
    'factual-relation',
    true,
    annotation(
      'factual-valid-exception',
      'Initials for a medical scan',
      'MRI',
      'factual-relation',
      {
        answerIsAbbreviation: true,
        abbreviationEvidence: {
          kind: 'licensed-exception',
          exceptionId: 'common-medical-initialism',
          rationale: 'The pack registers this conventional initialism.',
        },
      },
    ),
    'a registered initialism for a medical scan',
    'The abbreviated answer uses a registered exception with an editorial rationale.',
    'No repair; verify the exception registry during semantic review.',
    [],
    { licensedAbbreviationExceptions: ['common-medical-initialism'] },
  ),
  fixture(
    'factual-invalid-abbreviation-span',
    'factual-relation',
    false,
    annotation(
      'factual-invalid-abbreviation-span',
      'Briefly, estimate',
      'ETA',
      'factual-relation',
      {
        answerIsAbbreviation: true,
        signalSpans: [
          signal('factual-invalid-abbreviation-quote', 'Briefly', 'quote', 0, {
            role: 'mentioned-word',
          }),
        ],
        abbreviationEvidence: {
          kind: 'indicator-span',
          spanId: 'factual-invalid-abbreviation-quote',
        },
      },
    ),
    'an abbreviated answer',
    'The evidence points at a quote span instead of an abbreviation indicator.',
    'Annotate the literal indicator as abbreviation-indicator or use a full answer.',
    ['missing-abbreviation-indicator'],
  ),
  fixture(
    'factual-invalid-language-mismatch',
    'factual-relation',
    false,
    annotation(
      'factual-invalid-language-mismatch',
      'Thank you, in French',
      'MERCI',
      'factual-relation',
      {
        morphology: {
          clue: { partOfSpeech: 'phrase', number: 'not-applicable', language: 'en' },
          answer: { partOfSpeech: 'phrase', number: 'not-applicable', language: 'fr' },
        },
        signalSpans: [
          signal('factual-invalid-language-mismatch-label', 'in French', 'language-indicator', 12, {
            language: 'de',
          }),
        ],
      },
    ),
    'a French phrase',
    'The literal language indicator names a different language than the answer annotation.',
    'Make the indicator and answer language agree before semantic review.',
    ['missing-language-indicator'],
  ),
];

const fillBlanks: ClueGrammarFixture[] = [
  fixture('fill-valid-sound', 'fill-blank', true, fillBlank('fill-valid-sound', 'Safe and ___', 'SOUND', '___'), 'the completion of “Safe and sound”', 'The blank marker is literal and correctly spanned.', 'No repair; semantic phrase support remains a separate gate.'),
  fixture('fill-valid-swim', 'fill-blank', true, fillBlank('fill-valid-swim', 'Sink or ___', 'SWIM', '___'), 'the completion of “Sink or swim”', 'The blank is in a familiar phrase frame.', 'No repair; retain the fill marker.'),
  fixture('fill-valid-be', 'fill-blank', true, fillBlank('fill-valid-be', 'To be or not to ___', 'BE', '___'), 'the missing verb in the phrase', 'A repeated answer can still be structurally valid; duplicate policy belongs to puzzle validation.', 'No repair; check duplicate answers at the puzzle level.'),
  fixture('fill-valid-there', 'fill-blank', true, fillBlank('fill-valid-there', 'Neither here nor ___', 'THERE', '___'), 'the completion of the paired adverb phrase', 'The blank span is exact and answer-free.', 'No repair; semantic phrase evidence remains required.',),
  fixture('fill-invalid-missing', 'fill-blank', false, annotation('fill-invalid-missing', 'Safe and sound', 'SOUND', 'fill-blank'), 'the phrase completion', 'The family claims a blank but the rendered clue contains none.', 'Render a literal blank marker such as ___ or change the family.', ['missing-fill-blank-signal']),
  fixture('fill-invalid-marker', 'fill-blank', false, fillBlank('fill-invalid-marker', 'Safe and __', 'SOUND', '__'), 'the phrase completion', 'The house fixture requires at least three underscores or an ellipsis.', 'Use ___ or an ellipsis and preserve its exact span.', ['span-role-mismatch']),
  fixture('fill-invalid-span', 'fill-blank', false, annotation('fill-invalid-span', 'Safe and ___', 'SOUND', 'fill-blank', { signalSpans: [signal('fill-invalid-span-blank', 'and', 'fill-blank', 5)] }), 'the phrase completion', 'The signal span labels ordinary text as the blank.', 'Point the span at the literal ___ marker.', ['span-role-mismatch']),
  fixture('fill-invalid-offset', 'fill-blank', false, annotation('fill-invalid-offset', 'Safe and ___', 'SOUND', 'fill-blank', { signalSpans: [signal('fill-invalid-offset-blank', '___', 'fill-blank', 0)] }), 'the phrase completion', 'The fill marker span has the wrong offsets and does not match the clue text.', 'Use the actual marker start offset.', ['invalid-span']),
];

const spokenEquivalents: ClueGrammarFixture[] = [
  fixture('spoken-valid-chance', 'spoken-equivalent', true, spoken('spoken-valid-chance', '“Not a chance!”', 'NO WAY'), 'another spoken refusal', 'The whole quoted utterance is typed as a spoken-equivalent.', 'No repair; preserve the quote role.'),
  fixture('spoken-valid-greeting', 'spoken-equivalent', true, spoken('spoken-valid-greeting', '“See you soon.”', 'LATER'), 'another casual farewell', 'The whole clue is a quoted utterance with an interpretation.', 'No repair; preserve the conversational reading.'),
  fixture('spoken-valid-thanks', 'spoken-equivalent', true, spoken('spoken-valid-thanks', '“Much obliged!”', 'THANKS'), 'another spoken thanks', 'Curly quote boundaries remain literal clue text.', 'No repair; retain the full-span quote.'),
  fixture('spoken-valid-warning', 'spoken-equivalent', true, spoken('spoken-valid-warning', '“Watch out!”', 'LOOKOUT'), 'another spoken warning', 'The quote is not treated as a title or mentioned word.', 'No repair; preserve the spoken role.'),
  fixture('spoken-invalid-inline', 'spoken-equivalent', false, spoken('spoken-invalid-inline', 'She said “not a chance”', 'NO WAY'), 'a spoken refusal', 'An inline quotation is not a whole-clue spoken-equivalent surface.', 'Use a whole quoted utterance or change the family to a factual/mentioned-word clue.', ['missing-whole-quote']),
  fixture('spoken-invalid-partial', 'spoken-equivalent', false, annotation('spoken-invalid-partial', '“Not a chance!” — emphatic', 'NO WAY', 'spoken-equivalent', { interpretation: { intendedSense: 'a refusal', explanation: 'A refusal.' }, signalSpans: [signal('spoken-invalid-partial-quote', '“Not a chance!”', 'quote', 0, { role: 'spoken-equivalent' })] }), 'a spoken refusal', 'The quote span does not cover the whole clue.', 'Make the utterance the entire clue or annotate the longer surface accurately.', ['missing-whole-quote']),
  fixture('spoken-invalid-no-interpretation', 'spoken-equivalent', false, annotation('spoken-invalid-no-interpretation', '“Not a chance!”', 'NO WAY', 'spoken-equivalent', { signalSpans: [signal('spoken-invalid-no-interpretation-quote', '“Not a chance!”', 'quote', 0, { role: 'spoken-equivalent' })] }), 'a spoken refusal', 'A quote marker alone does not explain the intended utterance.', 'Add the intended sense and concise substitution explanation.', ['missing-interpretation']),
  fixture('spoken-invalid-role', 'spoken-equivalent', false, annotation('spoken-invalid-role', '“Not a chance!”', 'NO WAY', 'spoken-equivalent', { interpretation: { intendedSense: 'a refusal', explanation: 'A refusal.' }, signalSpans: [signal('spoken-invalid-role-quote', '“Not a chance!”', 'quote', 0, { role: 'title' })] }), 'a spoken refusal', 'A title quote is not a spoken-equivalent signal.', 'Set the span role to spoken-equivalent or use a title/factual family.', ['missing-whole-quote']),
];

const releasePackExpansionFillBlanks: ClueGrammarFixture[] = [
  fixture(
    'fill-valid-ellipsis',
    'fill-blank',
    true,
    fillBlank('fill-valid-ellipsis', 'Once upon a …', 'TIME', '…'),
    'the missing word in a familiar opening',
    'A single Unicode ellipsis is a literal blank marker with an exact span.',
    'No repair; phrase truth remains outside structural validation.',
  ),
  fixture(
    'fill-valid-dots',
    'fill-blank',
    true,
    fillBlank('fill-valid-dots', 'Ready, set, ...', 'GO', '...'),
    'the completion of a starting sequence',
    'Three literal periods are accepted as the answer slot.',
    'No repair; preserve the exact marker.',
  ),
  fixture(
    'fill-invalid-short-ellipsis',
    'fill-blank',
    false,
    fillBlank('fill-invalid-short-ellipsis', 'Once upon ..', 'TIME', '..'),
    'the missing word in a familiar opening',
    'Two periods do not meet the house marker convention.',
    'Use three periods, a Unicode ellipsis, or a longer ellipsis marker.',
    ['span-role-mismatch'],
  ),
  fixture(
    'fill-invalid-unmarked',
    'fill-blank',
    false,
    annotation('fill-invalid-unmarked', 'Ready, set, go', 'GO', 'fill-blank'),
    'the completion of a starting sequence',
    'The family claims a blank but the rendered clue has no literal marker.',
    'Render a blank marker and span it exactly, or use another family.',
    ['missing-fill-blank-signal'],
  ),
];

const releasePackExpansionSpokenEquivalents: ClueGrammarFixture[] = [
  fixture(
    'spoken-valid-single-quotes',
    'spoken-equivalent',
    true,
    spoken('spoken-valid-single-quotes', '‘Good morning.’', 'HELLO'),
    'another morning greeting',
    'A complete curly single-quoted utterance carries the spoken role.',
    'No repair; preserve the full utterance span.',
  ),
  fixture(
    'spoken-valid-straight-quotes',
    'spoken-equivalent',
    true,
    spoken('spoken-valid-straight-quotes', '"See ya!"', 'BYE'),
    'another casual farewell',
    'A complete straight-quoted utterance is structurally equivalent.',
    'No repair; semantic equivalence remains unestablished.',
  ),
  fixture(
    'spoken-invalid-title-role',
    'spoken-equivalent',
    false,
    annotation('spoken-invalid-title-role', '“Good morning.”', 'HELLO', 'spoken-equivalent', {
      interpretation: {
        intendedSense: 'another greeting',
        explanation: 'A greeting in the same moment.',
      },
      signalSpans: [
        signal('spoken-invalid-title-role-quote', '“Good morning.”', 'quote', 0, { role: 'title' }),
      ],
    }),
    'another morning greeting',
    'The full quote is typed as a title rather than a spoken-equivalent utterance.',
    'Use the spoken-equivalent role or move the clue to a title/factual family.',
    ['missing-whole-quote'],
  ),
  fixture(
    'spoken-invalid-trailing-text',
    'spoken-equivalent',
    false,
    spoken('spoken-invalid-trailing-text', '"See ya!" today', 'BYE'),
    'another casual farewell',
    'Additional prose leaves the quoted utterance short of the whole clue.',
    'Make the utterance the entire clue or change its family.',
    ['missing-whole-quote'],
  ),
];

const nonverbalExpressions: ClueGrammarFixture[] = [
  fixture('nonverbal-valid-phew', 'nonverbal-expression', true, nonverbal('nonverbal-valid-phew', '[Sigh of relief]', 'PHEW'), 'a written relieved exhalation', 'The whole bracketed clue describes a nonverbal action.', 'No repair; preserve brackets as literal signal text.'),
  fixture('nonverbal-valid-brr', 'nonverbal-expression', true, nonverbal('nonverbal-valid-brr', '[Shiver]', 'BRR'), 'letters expressing a shiver', 'The clue asks for a written sound rather than speech.', 'No repair; preserve the nonverbal family.'),
  fixture('nonverbal-valid-oof', 'nonverbal-expression', true, nonverbal('nonverbal-valid-oof', '[Impact reaction]', 'OOF'), 'a written impact reaction', 'The bracketed action has an explicit interpretation.', 'No repair; keep the whole-clue brackets.'),
  fixture('nonverbal-valid-hush', 'nonverbal-expression', true, nonverbal('nonverbal-valid-hush', '[Quiet gesture]', 'SHH'), 'letters for a quieting gesture', 'The typed brackets distinguish gesture from quotation.', 'No repair; retain the nonverbal signal.'),
  fixture('nonverbal-invalid-inline', 'nonverbal-expression', false, nonverbal('nonverbal-invalid-inline', 'Reaction: [Sigh]', 'PHEW'), 'a relieved exhalation', 'Decorative prose surrounds the bracketed expression.', 'Make the bracketed expression the complete clue or change the family.', ['missing-whole-brackets']),
  fixture('nonverbal-invalid-no-interpretation', 'nonverbal-expression', false, annotation('nonverbal-invalid-no-interpretation', '[Sigh of relief]', 'PHEW', 'nonverbal-expression', { signalSpans: [signal('nonverbal-invalid-no-interpretation-brackets', '[Sigh of relief]', 'brackets', 0, { role: 'nonverbal-expression' })] }), 'a relieved exhalation', 'Brackets alone do not state what the answer is doing.', 'Add a concise intended sense and explanation.', ['missing-interpretation']),
  fixture('nonverbal-invalid-role', 'nonverbal-expression', false, annotation('nonverbal-invalid-role', 'Sigh of relief', 'PHEW', 'nonverbal-expression', { interpretation: { intendedSense: 'relief sound', explanation: 'A written reaction.' }, signalSpans: [signal('nonverbal-invalid-role-brackets', 'Sigh of relief', 'brackets', 0, { role: 'nonverbal-expression' })] }), 'a relief sound', 'The nonverbal family has no literal whole-clue brackets.', 'Render the brackets in the clue text and span them exactly.', ['missing-whole-brackets']),
  fixture('nonverbal-invalid-span', 'nonverbal-expression', false, annotation('nonverbal-invalid-span', '[Sigh of relief]', 'PHEW', 'nonverbal-expression', { interpretation: { intendedSense: 'relief sound', explanation: 'A written reaction.' }, signalSpans: [signal('nonverbal-invalid-span-brackets', '[Sigh of relief]', 'brackets', 1, { role: 'nonverbal-expression' })] }), 'a relief sound', 'The bracket span starts one character late.', 'Use offset zero for the whole clue.', ['invalid-span', 'missing-whole-brackets']),
];

const releasePackExpansionNonverbalExpressions: ClueGrammarFixture[] = [
  fixture(
    'nonverbal-valid-gulp',
    'nonverbal-expression',
    true,
    nonverbal('nonverbal-valid-gulp', '[Nervous swallow]', 'GULP'),
    'letters expressing a nervous swallow',
    'The complete bracketed clue is explicitly treated as a nonverbal action.',
    'No repair; retain the bracket role.',
  ),
  fixture(
    'nonverbal-valid-yawn',
    'nonverbal-expression',
    true,
    nonverbal('nonverbal-valid-yawn', '[Tired exhalation]', 'YAWN'),
    'a written tired reaction',
    'The whole clue and its span agree on the bracket convention.',
    'No repair; answer semantics remain outside this structural check.',
  ),
  fixture(
    'nonverbal-invalid-parentheses',
    'nonverbal-expression',
    false,
    annotation('nonverbal-invalid-parentheses', '(Nervous swallow)', 'GULP', 'nonverbal-expression', {
      interpretation: {
        intendedSense: 'a nervous swallow',
        explanation: 'A written reaction.',
      },
      signalSpans: [
        signal('nonverbal-invalid-parentheses-span', '(Nervous swallow)', 'brackets', 0, { role: 'nonverbal-expression' }),
      ],
    }),
    'a written nervous swallow',
    'Parentheses do not provide the required literal square-bracket convention.',
    'Render square brackets around the complete clue.',
    ['missing-whole-brackets'],
  ),
  fixture(
    'nonverbal-invalid-empty-interpretation',
    'nonverbal-expression',
    false,
    annotation('nonverbal-invalid-empty-interpretation', '[Nervous swallow]', 'GULP', 'nonverbal-expression', {
      interpretation: { intendedSense: '', explanation: 'A reaction.' },
      signalSpans: [
        signal('nonverbal-invalid-empty-interpretation-span', '[Nervous swallow]', 'brackets', 0, { role: 'nonverbal-expression' }),
      ],
    }),
    'a written nervous swallow',
    'The bracket signal is present but the intended sense is empty.',
    'Provide a concise intended sense before semantic review.',
    ['missing-interpretation'],
  ),
];

const semanticMisdirections: ClueGrammarFixture[] = [
  fixture('misdirection-valid-current', 'semantic-misdirection', true, wordplay('misdirection-valid-current', 'semantic-misdirection', 'Current unit', 'AMP', { intendedSense: 'electrical current unit', surfaceReading: 'a unit that is current or up-to-date', intendedReading: 'a unit of electricity', explanation: 'Current shifts from temporal relevance to electricity.' }), 'the electrical sense of current', 'Both surface and intended readings are recorded.', 'No repair; semantic equivalence still requires a reviewer.'),
  fixture('misdirection-valid-bark', 'semantic-misdirection', true, wordplay('misdirection-valid-bark', 'semantic-misdirection', 'Tree covering', 'BARK', { intendedSense: 'tree outer layer', surfaceReading: 'a covering on a tree', intendedReading: 'the outer layer of a tree', explanation: 'The clue moves from a generic covering to a botanical sense.' }), 'the botanical sense of bark', 'The family has two explicit readings without relying on a question mark.', 'No repair; retain both readings.'),
  fixture('misdirection-valid-organ', 'semantic-misdirection', true, wordplay('misdirection-valid-organ', 'semantic-misdirection', 'Church player', 'ORGAN', { intendedSense: 'a pipe instrument', surfaceReading: 'a person who plays in a church', intendedReading: 'the instrument played in a church', explanation: 'The phrase can initially describe a person before resolving to the instrument.' }), 'a church instrument', 'The fixture records an intentionally oblique but explained relation.', 'No repair; semantic challenger should test fairness.'),
  fixture('misdirection-valid-fine', 'semantic-misdirection', true, wordplay('misdirection-valid-fine', 'semantic-misdirection', 'Small penalty', 'FINE', { intendedSense: 'a monetary penalty', surfaceReading: 'something small or refined', intendedReading: 'a monetary penalty', explanation: 'Fine shifts between an adjective and a noun sense.' }), 'a monetary penalty', 'A semantic turn is explicit and answer-free.', 'No repair; preserve the two-reading explanation.'),
  fixture('misdirection-invalid-no-surface', 'semantic-misdirection', false, annotation('misdirection-invalid-no-surface', 'Current unit', 'AMP', 'semantic-misdirection', { interpretation: { intendedSense: 'electrical unit', explanation: 'A current unit.' } }), 'the electrical sense of current', 'A semantic-misdirection annotation lacks its surface reading.', 'Add the ordinary surface reading or classify the clue as a direct factual relation.', ['missing-interpretation']),
  fixture('misdirection-invalid-no-intended', 'semantic-misdirection', false, annotation('misdirection-invalid-no-intended', 'Current unit', 'AMP', 'semantic-misdirection', { interpretation: { intendedSense: 'electrical unit', surfaceReading: 'a current unit', explanation: 'A current unit.' } }), 'the electrical sense of current', 'The intended reading is not distinguished from the surface.', 'Record the intended reading explicitly.', ['missing-interpretation']),
  fixture('misdirection-invalid-empty', 'semantic-misdirection', false, annotation('misdirection-invalid-empty', 'Current unit', 'AMP', 'semantic-misdirection', { interpretation: { intendedSense: '', surfaceReading: 'a current unit', intendedReading: 'electricity', explanation: 'A current unit.' } }), 'the electrical sense of current', 'The intended sense is empty and cannot anchor semantic review.', 'Provide a nonempty pinned sense.', ['missing-interpretation']),
  fixture('misdirection-invalid-plain', 'semantic-misdirection', false, annotation('misdirection-invalid-plain', 'Current unit', 'AMP', 'semantic-misdirection'), 'the electrical sense of current', 'The family has no interpretation at all.', 'Add both readings and an explanation, or choose factual-relation.', ['missing-interpretation']),
];

const puns: ClueGrammarFixture[] = [
  fixture('pun-valid-branch', 'pun', true, wordplay('pun-valid-branch', 'pun', 'Branch specialist?', 'ARBORIST', { intendedSense: 'tree-care professional', surfaceReading: 'a specialist in a field of study', intendedReading: 'a professional who works with tree branches', explanation: 'Branch shifts from an academic field to part of a tree.' }), 'a tree-care professional', 'The question mark is supported by two explicit readings.', 'No repair; preserve the wordplay account.'),
  fixture('pun-valid-polite', 'pun', true, wordplay('pun-valid-polite', 'pun', 'A courteous wave?', 'HELLO', { intendedSense: 'a greeting', surfaceReading: 'a wave as a polite gesture', intendedReading: 'a greeting spoken with a wave', explanation: 'Wave shifts from a hand gesture to the greeting it carries.' }), 'a greeting', 'A playful question-mark clue has an answer-free explanation.', 'No repair; keep the final question mark.'),
  fixture('pun-valid-quiet', 'pun', true, wordplay('pun-valid-quiet', 'pun', 'Sound choice', 'ECHO', { intendedSense: 'a reflected sound', surfaceReading: 'a choice that sounds agreeable', intendedReading: 'a reflected sound', explanation: 'Sound is read as both an adjective and a physical phenomenon.' }), 'a reflected sound', 'A pun family can omit a question mark when the puzzle policy permits it.', 'No repair; semantic review still decides whether the turn is satisfying.'),
  fixture('pun-valid-light', 'pun', true, wordplay('pun-valid-light', 'pun', 'Bright idea?', 'SPARK', { intendedSense: 'a flash or inspiration', surfaceReading: 'an intelligent thought', intendedReading: 'a tiny flash of light', explanation: 'Idea and spark meet in a compact double reading.' }), 'a spark', 'A final question mark is backed by a recorded turn.', 'No repair; preserve both readings.'),
  fixture('pun-invalid-question', 'pun', false, annotation('pun-invalid-question', 'Branch specialist?', 'ARBORIST', 'pun', { interpretation: { intendedSense: 'tree-care professional', explanation: 'A tree-care professional.' } }), 'a tree-care professional', 'A question mark is present but no surface/intended contrast is recorded.', 'Add both readings and explain the pun, or remove the question mark.', ['unexplained-question-mark']),
  fixture('pun-invalid-policy', 'pun', false, wordplay('pun-invalid-policy', 'pun', 'Branch specialist', 'ARBORIST'), 'a tree-care professional', 'The recipe requires a question mark for pun clues but the surface has none.', 'Add the required question mark or use an optional-policy context.', ['pun-question-mark-policy'], { punQuestionMarkPolicy: 'required' }),
  fixture('pun-invalid-forbidden', 'pun', false, wordplay('pun-invalid-forbidden', 'pun', 'Branch specialist?', 'ARBORIST'), 'a tree-care professional', 'The selected recipe forbids question-mark signaling.', 'Remove the question mark or choose a recipe that permits it.', ['pun-question-mark-policy'], { punQuestionMarkPolicy: 'forbidden' }),
  fixture('pun-invalid-no-reading', 'pun', false, annotation('pun-invalid-no-reading', 'Branch specialist', 'ARBORIST', 'pun'), 'a tree-care professional', 'Pun family has no intended reading or explanation.', 'Add a two-reading interpretation before semantic review.', ['missing-interpretation']),
];

const releasePackExpansionSemanticMisdirections: ClueGrammarFixture[] = [
  fixture(
    'misdirection-valid-light',
    'semantic-misdirection',
    true,
    wordplay('misdirection-valid-light', 'semantic-misdirection', 'Not heavy', 'LIGHT', {
      intendedSense: 'having little weight',
      surfaceReading: 'not bright or dark',
      intendedReading: 'having little weight',
      explanation: 'Light turns from illumination to weight.',
    }),
    'the weight sense of light',
    'Both the surface and intended readings are pinned for review.',
    'No repair; semantic equivalence remains unestablished.',
  ),
  fixture(
    'misdirection-valid-wave',
    'semantic-misdirection',
    true,
    wordplay('misdirection-valid-wave', 'semantic-misdirection', 'Hand motion', 'WAVE', {
      intendedSense: 'a hand gesture',
      surfaceReading: 'a movement of water',
      intendedReading: 'a hand gesture',
      explanation: 'Wave moves from water to a greeting gesture.',
    }),
    'a hand gesture',
    'An ordinary surface and a distinct intended reading are recorded.',
    'No repair; preserve both readings for a future challenger.',
  ),
  fixture(
    'misdirection-invalid-no-surface-extra',
    'semantic-misdirection',
    false,
    annotation('misdirection-invalid-no-surface-extra', 'Not heavy', 'LIGHT', 'semantic-misdirection', {
      interpretation: {
        intendedSense: 'having little weight',
        intendedReading: 'having little weight',
        explanation: 'A weight sense.',
      },
    }),
    'the weight sense of light',
    'The annotation omits the ordinary surface reading needed to describe the turn.',
    'Add the surface reading or classify the clue as a direct definition.',
    ['missing-interpretation'],
  ),
  fixture(
    'misdirection-invalid-empty-explanation-extra',
    'semantic-misdirection',
    false,
    wordplay('misdirection-invalid-empty-explanation-extra', 'semantic-misdirection', 'Hand motion', 'WAVE', {
      intendedSense: 'a hand gesture',
      surfaceReading: 'a movement of water',
      intendedReading: 'a hand gesture',
      explanation: '',
    }),
    'a hand gesture',
    'The two readings exist, but the annotation does not explain their relationship.',
    'Add a concise explanation before semantic review.',
    ['missing-interpretation'],
  ),
];

const releasePackExpansionPuns: ClueGrammarFixture[] = [
  fixture(
    'pun-valid-cold',
    'pun',
    true,
    wordplay('pun-valid-cold', 'pun', 'Unfriendly reception?', 'CHILL', {
      intendedSense: 'an unfriendly reception',
      surfaceReading: 'a cold temperature',
      intendedReading: 'an unfriendly reception',
      explanation: 'Cold shifts from temperature to social reception.',
    }),
    'an unfriendly reception',
    'The question mark is backed by distinct surface and intended readings.',
    'No repair; preserve the wordplay annotation.',
  ),
  fixture(
    'pun-valid-ground',
    'pun',
    true,
    wordplay('pun-valid-ground', 'pun', 'Solid basis?', 'GROUND', {
      intendedSense: 'a basis or reason',
      surfaceReading: 'the earth underfoot',
      intendedReading: 'a basis or reason',
      explanation: 'Ground shifts from earth to a supporting reason.',
    }),
    'a basis or reason',
    'The final question mark has an explicit two-reading account.',
    'No repair; semantic fairness remains a separate decision.',
  ),
  fixture(
    'pun-invalid-question-extra',
    'pun',
    false,
    annotation('pun-invalid-question-extra', 'Unfriendly reception?', 'CHILL', 'pun', {
      interpretation: {
        intendedSense: 'an unfriendly reception',
        explanation: 'A social reception.',
      },
    }),
    'an unfriendly reception',
    'A question-mark pun omits its surface and intended readings.',
    'Record both readings and explain the turn, or remove the question mark.',
    ['unexplained-question-mark'],
  ),
  fixture(
    'pun-invalid-forbidden-extra',
    'pun',
    false,
    wordplay('pun-invalid-forbidden-extra', 'pun', 'Solid basis?', 'GROUND', {
      intendedSense: 'a basis or reason',
      surfaceReading: 'the earth underfoot',
      intendedReading: 'a basis or reason',
      explanation: 'Ground shifts from earth to a supporting reason.',
    }),
    'a basis or reason',
    'The selected recipe forbids question-mark signaling for this pun.',
    'Remove the question mark or use a recipe that permits it.',
    ['pun-question-mark-policy'],
    { punQuestionMarkPolicy: 'forbidden' },
  ),
];

const metalinguistic: ClueGrammarFixture[] = [
  fixture('meta-valid-small', 'metalinguistic', true, annotation('meta-valid-small', 'A word for “small”', 'LITTLE', 'metalinguistic', { signalSpans: [signal('meta-valid-small-marker', 'word for', 'metalinguistic-marker', 2)] }), 'a word meaning small', 'The clue explicitly talks about a word rather than directly defining the answer.', 'No repair; semantic sense review remains separate.'),
  fixture('meta-valid-friend', 'metalinguistic', true, annotation('meta-valid-friend', 'Term meaning “friend”', 'ALLY', 'metalinguistic', { signalSpans: [signal('meta-valid-friend-marker', 'Term meaning', 'metalinguistic-marker', 0)] }), 'a term meaning friend', 'The metalinguistic marker is literal and typed.', 'No repair; preserve the marker span.'),
  fixture('meta-valid-short', 'metalinguistic', true, annotation('meta-valid-short', 'Prefix for “before”', 'PRE', 'metalinguistic', { signalSpans: [signal('meta-valid-short-marker', 'Prefix for', 'metalinguistic-marker', 0)] }), 'a prefix meaning before', 'The clue asks about a word part rather than a factual object.', 'No repair; answer morphology can be reviewed separately.'),
  fixture('meta-valid-letters', 'metalinguistic', true, annotation('meta-valid-letters', 'Letters for a hesitation', 'UM', 'metalinguistic', { signalSpans: [signal('meta-valid-letters-marker', 'Letters for', 'metalinguistic-marker', 0)] }), 'written letters representing hesitation', 'The marker explains that the answer is a linguistic representation.', 'No repair; keep the family distinct from nonverbal brackets.'),
  fixture('meta-invalid-missing', 'metalinguistic', false, annotation('meta-invalid-missing', 'Small', 'LITTLE', 'metalinguistic'), 'a word meaning small', 'A direct definition is mislabeled as metalinguistic without a marker.', 'Add “A word for” or classify it as definition.', ['missing-metalinguistic-signal']),
  fixture('meta-invalid-wrong-marker', 'metalinguistic', false, annotation('meta-invalid-wrong-marker', 'A word for “small”', 'LITTLE', 'metalinguistic', { signalSpans: [signal('meta-invalid-wrong-marker-signal', 'word', 'metalinguistic-marker', 4)] }), 'a word meaning small', 'The marker is truncated and its span does not match the intended convention phrase.', 'Point the marker at the complete literal “word for” phrase.', ['invalid-span']),
  fixture('meta-invalid-span', 'metalinguistic', false, annotation('meta-invalid-span', 'A word for “small”', 'LITTLE', 'metalinguistic', { signalSpans: [signal('meta-invalid-span-signal', 'word for', 'metalinguistic-marker', 3)] }), 'a word meaning small', 'The signal span starts inside the phrase and fails to match its literal text.', 'Use the exact start offset for “word for.”', ['invalid-span']),
  fixture('meta-invalid-family', 'metalinguistic', false, annotation('meta-invalid-family', 'A word for “small”', 'LITTLE', 'definition', { morphology: undefined, signalSpans: [signal('meta-invalid-family-signal', 'word for', 'metalinguistic-marker', 2)] }), 'a word meaning small', 'The metalinguistic signal is attached to a direct-definition family with missing morphology.', 'Use the metalinguistic family or provide a complete definition annotation.', ['missing-morphology']),
];

const releasePackExpansionMetalinguistic: ClueGrammarFixture[] = [
  fixture(
    'meta-valid-opposite',
    'metalinguistic',
    true,
    annotation('meta-valid-opposite', 'A word opposite “early”', 'LATE', 'metalinguistic', {
      signalSpans: [signal('meta-valid-opposite-marker', 'A word opposite', 'metalinguistic-marker', 0)],
    }),
    'a word opposite early',
    'The marker explicitly identifies a relation between words.',
    'No repair; meaning and answer accessibility remain separate checks.',
  ),
  fixture(
    'meta-valid-ending',
    'metalinguistic',
    true,
    annotation('meta-valid-ending', 'Ending meaning “small”', 'LET', 'metalinguistic', {
      signalSpans: [signal('meta-valid-ending-marker', 'Ending meaning', 'metalinguistic-marker', 0)],
    }),
    'a word ending meaning small',
    'The typed marker distinguishes a word part from a direct definition.',
    'No repair; preserve the marker span.',
  ),
  fixture(
    'meta-invalid-no-marker-extra',
    'metalinguistic',
    false,
    annotation('meta-invalid-no-marker-extra', 'Opposite of early', 'LATE', 'metalinguistic'),
    'a word opposite early',
    'The clue is metalinguistic in intent but has no literal marker span.',
    'Add a phrase such as “A word opposite” and span it exactly.',
    ['missing-metalinguistic-signal'],
  ),
  fixture(
    'meta-invalid-offset-extra',
    'metalinguistic',
    false,
    annotation('meta-invalid-offset-extra', 'Ending meaning “small”', 'LET', 'metalinguistic', {
      signalSpans: [signal('meta-invalid-offset-extra-marker', 'Ending meaning', 'metalinguistic-marker', 1)],
    }),
    'a word ending meaning small',
    'The marker span starts one character inside the literal convention phrase.',
    'Use the exact start offset for the marker.',
    ['invalid-span'],
  ),
];

const linked: ClueGrammarFixture[] = [
  fixture('linked-valid-down', 'linked', true, crossReference('linked-valid-down', 'See 12-Down', 'PAIR', 12, 'down', 'entry-12-down'), 'a linked answer resolved with 12-Down', 'The printed reference and target index agree.', 'No repair; preserve the target entry identity.', [], { entries: linkedEntries }),
  fixture('linked-valid-across', 'linked', true, crossReference('linked-valid-across', 'With 7-Across, together', 'TEAM', 7, 'across', 'entry-7-across'), 'a linked answer resolved with 7-Across', 'The across direction and number are current.', 'No repair; preserve the link.', [], { entries: linkedEntries }),
  fixture('linked-valid-third', 'linked', true, crossReference('linked-valid-third', 'See 3-Across', 'PAIR', 3, 'across', 'entry-3-across'), 'a linked answer resolved with 3-Across', 'A second across link remains structurally independent.', 'No repair; retain the entry ID.', [], { entries: linkedEntries }),
  fixture('linked-valid-eighteen', 'linked', true, crossReference('linked-valid-eighteen', 'With 18-Down, jointly', 'DUET', 18, 'down', 'entry-18-down'), 'a linked answer resolved with 18-Down', 'The down target is present in the same puzzle index.', 'No repair; retain the live target reference.', [], { entries: linkedEntries }),
  fixture('linked-invalid-no-context', 'linked', false, crossReference('linked-invalid-no-context', 'See 12-Down', 'PAIR', 12, 'down', 'entry-12-down'), 'a linked answer', 'A cross-reference cannot be trusted without the current entry index.', 'Supply the puzzle entry index before validating the link.', ['missing-reference-context']),
  fixture('linked-invalid-target', 'linked', false, crossReference('linked-invalid-target', 'See 12-Down', 'PAIR', 12, 'down', 'missing-entry'), 'a linked answer', 'The target entry ID is not present in the current puzzle.', 'Resolve the target to an existing entry or rewrite the clue.', ['missing-reference-target'], { entries: linkedEntries }),
  fixture('linked-invalid-number', 'linked', false, crossReference('linked-invalid-number', 'See 13-Down', 'PAIR', 12, 'down', 'entry-12-down', 13), 'a linked answer', 'The printed number and declared target number disagree.', 'Update the displayed reference and span metadata together.', ['stale-cross-reference'], { entries: linkedEntries }),
  fixture('linked-invalid-direction', 'linked', false, crossReference('linked-invalid-direction', 'See 12-Across', 'PAIR', 12, 'across', 'entry-12-down'), 'a linked answer', 'The displayed direction no longer matches the target entry.', 'Use the target’s actual direction or point at the correct entry.', ['stale-cross-reference'], { entries: linkedEntries }),
];

const releasePackExpansionLinked: ClueGrammarFixture[] = [
  fixture(
    'linked-valid-repeat',
    'linked',
    true,
    crossReference('linked-valid-repeat', 'See 18-Down', 'DUET', 18, 'down', 'entry-18-down'),
    'a linked answer resolved with 18-Down',
    'A repeated target remains valid when its displayed reference and index agree.',
    'No repair; retain the target identity.',
    [],
    { entries: linkedEntries },
  ),
  fixture(
    'linked-valid-across-second',
    'linked',
    true,
    crossReference('linked-valid-across-second', 'With 3-Across, together', 'PAIR', 3, 'across', 'entry-3-across'),
    'a linked answer resolved with 3-Across',
    'A second across reference uses the same current puzzle index.',
    'No repair; preserve the live target reference.',
    [],
    { entries: linkedEntries },
  ),
  fixture(
    'linked-invalid-no-context-extra',
    'linked',
    false,
    crossReference('linked-invalid-no-context-extra', 'See 7-Across', 'TEAM', 7, 'across', 'entry-7-across'),
    'a linked answer',
    'A visible cross-reference cannot be checked without the current entry index.',
    'Supply the puzzle entry index before validating the link.',
    ['missing-reference-context'],
  ),
  fixture(
    'linked-invalid-target-extra',
    'linked',
    false,
    crossReference('linked-invalid-target-extra', 'See 18-Down', 'DUET', 18, 'down', 'missing-entry'),
    'a linked answer',
    'The displayed target is absent from the current puzzle index.',
    'Resolve the target to an existing entry or rewrite the clue.',
    ['missing-reference-target'],
    { entries: linkedEntries },
  ),
];

function themed(
  id: string,
  clueText: string,
  answer: string,
  signalText: string,
  mechanicRef = true,
): ClueGrammarAnnotation {
  const start = clueText.indexOf(signalText);
  return annotation(id, clueText, answer, 'theme-dependent', {
    interpretation: {
      intendedSense: 'the answer under the declared puzzle transformation',
      intendedReading: 'apply the announced theme move',
      explanation: 'The clue names the operation instead of hiding it.',
    },
    ...(mechanicRef
      ? {
          mechanicRef: {
            mechanicId: mechanic.id,
            explanation: 'Apply the puzzle’s declared final-letter turn.',
          },
        }
      : {}),
    signalSpans: [signal(`${id}-mechanic-signal`, signalText, 'mechanic-indicator', start)],
  });
}

const themeDependent: ClueGrammarFixture[] = [
  fixture('theme-valid-first', 'theme-dependent', true, themed('theme-valid-first', 'Twist the final letter', 'SHIFT', 'Twist'), 'an answer governed by the final-letter turn', 'The mechanic registry, clue signal, and explanation agree.', 'No repair; keep the explicit mechanic reference.', [], themeContext),
  fixture('theme-valid-second', 'theme-dependent', true, themed('theme-valid-second', 'Turn the ending', 'BEND', 'Turn'), 'an answer governed by the final-letter turn', 'A different surface still carries the declared mechanic signal.', 'No repair; preserve the mechanic ID.', [], themeContext),
  fixture('theme-valid-third', 'theme-dependent', true, themed('theme-valid-third', 'Shift the last letter', 'MOVE', 'Shift'), 'an answer governed by the final-letter turn', 'The signal scope is exact and the entry is affected.', 'No repair; retain the typed signal.', [], themeContext),
  fixture('theme-valid-fourth', 'theme-dependent', true, themed('theme-valid-fourth', 'Twist the ending here', 'TURN', 'Twist'), 'an answer governed by the final-letter turn', 'The mechanic explanation remains attached to the clue reference.', 'No repair; preserve the mechanic context.', [], themeContext),
  fixture('theme-invalid-no-ref', 'theme-dependent', false, themed('theme-invalid-no-ref', 'Twist the final letter', 'SHIFT', 'Twist', false), 'an answer governed by the final-letter turn', 'A theme clue has no mechanic reference.', 'Attach the declared mechanic ID and explanation.', ['missing-mechanic-reference'], themeContext),
  fixture('theme-invalid-unknown', 'theme-dependent', false, { ...themed('theme-invalid-unknown', 'Twist the final letter', 'SHIFT', 'Twist'), mechanicRef: { mechanicId: 'missing-mechanic', explanation: 'Unknown.' } }, 'an answer governed by the final-letter turn', 'The clue points at an undeclared mechanic.', 'Use the puzzle’s declared mechanic ID.', ['unknown-mechanic'], themeContext),
  fixture('theme-invalid-signal', 'theme-dependent', false, { ...themed('theme-invalid-signal', 'Twist the final letter', 'SHIFT', 'Twist'), signalSpans: [] }, 'an answer governed by the final-letter turn', 'The declared mechanic requires a literal cue span that is missing.', 'Add a mechanic-indicator span covering the cue.', ['missing-mechanic-signal'], themeContext),
  fixture('theme-invalid-explanation', 'theme-dependent', false, { ...themed('theme-invalid-explanation', 'Twist the final letter', 'SHIFT', 'Twist'), mechanicRef: { mechanicId: mechanic.id, explanation: '' } }, 'an answer governed by the final-letter turn', 'The mechanic reference has no explanation.', 'Explain how the mechanic applies to this entry.', ['missing-mechanic-explanation'], themeContext),
];

const releasePackExpansionThemeDependent: ClueGrammarFixture[] = [
  fixture(
    'theme-valid-fifth',
    'theme-dependent',
    true,
    themed('theme-valid-fifth', 'Turn the final letter here', 'BEND', 'Turn'),
    'an answer governed by the final-letter turn',
    'The literal operation cue, mechanic registry, and affected entry agree.',
    'No repair; retain the mechanic explanation.',
    [],
    themeContext,
  ),
  fixture(
    'theme-valid-sixth',
    'theme-dependent',
    true,
    themed('theme-valid-sixth', 'Shift the ending now', 'MOVE', 'Shift'),
    'an answer governed by the final-letter turn',
    'A different operation surface remains bound to the declared mechanic.',
    'No repair; preserve the typed signal.',
    [],
    themeContext,
  ),
  fixture(
    'theme-invalid-no-context-extra',
    'theme-dependent',
    false,
    themed('theme-invalid-no-context-extra', 'Twist the final letter', 'SHIFT', 'Twist'),
    'an answer governed by the final-letter turn',
    'A theme-dependent clue cannot be checked without the mechanic registry.',
    'Supply the puzzle mechanic context before validating the clue.',
    ['missing-mechanic-context'],
  ),
  fixture(
    'theme-invalid-not-applicable-extra',
    'theme-dependent',
    false,
    {
      ...themed('theme-invalid-not-applicable-extra', 'Twist the final letter', 'SHIFT', 'Twist'),
      entryId: 'unaffected-entry',
    },
    'an answer governed by the final-letter turn',
    'The mechanic reference points at an entry outside its affected-entry list.',
    'Bind the clue to an affected entry or select the applicable mechanic.',
    ['mechanic-not-applicable'],
    themeContext,
  ),
];

/**
 * Final authored rows for the structural release matrix.  The rows are kept
 * explicit instead of generated from a loop so that each case can be read,
 * edited, and reviewed as a distinct house-grammar example.  They continue
 * to describe structure only: no row establishes a sense, fact, or player
 * fairness.
 */
const releasePackCompletionDefinitions: ClueGrammarFixture[] = [
  fixture(
    'definition-final-valid-mass',
    'definition',
    true,
    directDefinition(
      'definition-final-valid-mass',
      'Campfire fuel',
      'WOOD',
      nounMass,
      nounMass,
      'The shed stores {0}.',
    ),
    'a mass noun for campfire fuel',
    'The clue and answer use the same mass-noun frame.',
    'No repair; semantic support remains a separate review concern.',
  ),
  fixture(
    'definition-final-valid-invariant',
    'definition',
    true,
    directDefinition(
      'definition-final-valid-invariant',
      'Woolly farm animal',
      'SHEEP',
      { partOfSpeech: 'noun', number: 'invariant' },
      { partOfSpeech: 'noun', number: 'invariant' },
      'The farmer counted {0}.',
    ),
    'an invariant-form farm animal noun',
    'The invariant number is pinned on both sides of the substitution frame.',
    'No repair; preserve the explicit number annotation.',
  ),
  fixture(
    'definition-final-valid-register',
    'definition',
    true,
    directDefinition(
      'definition-final-valid-register',
      'Friend, informally',
      'BUDDY',
      { partOfSpeech: 'noun', number: 'singular', register: 'informal' },
      { partOfSpeech: 'noun', number: 'singular', register: 'informal' },
      'My {0} called yesterday.',
    ),
    'an informal noun for a friend',
    'The clue and answer carry the same marked register.',
    'No repair; register meaning remains outside structural validation.',
  ),
  fixture(
    'definition-final-valid-adjective',
    'definition',
    true,
    directDefinition(
      'definition-final-valid-adjective',
      'Without delay',
      'PROMPT',
      adjectiveSingular,
      adjectiveSingular,
      'The reply was {0}.',
    ),
    'an adjective meaning without delay',
    'The two adjective readings occupy the same copular frame.',
    'No repair; retain the direct substitution witness.',
  ),
  fixture(
    'definition-final-invalid-register',
    'definition',
    false,
    directDefinition(
      'definition-final-invalid-register',
      'Friend',
      'BUDDY',
      { partOfSpeech: 'noun', number: 'singular', register: 'neutral' },
      { partOfSpeech: 'noun', number: 'singular', register: 'slang' },
      'My {0} called yesterday.',
    ),
    'an answer whose slang register was not signaled',
    'The answer register differs from the clue with no register indicator.',
    'Add a literal register signal or align the two register annotations.',
    ['morphology-mismatch', 'missing-register-signal'],
  ),
  fixture(
    'definition-final-invalid-ambiguity',
    'definition',
    false,
    directDefinition(
      'definition-final-invalid-ambiguity',
      'A fish or fishes',
      'FISH',
      { partOfSpeech: 'noun', number: 'ambiguous' },
      { partOfSpeech: 'noun', number: 'ambiguous' },
      'We saw {0}.',
    ),
    'a number-ambiguous noun without a pinned reading',
    'Both morphology sides remain ambiguous without an editor witness.',
    'Pin one number reading and record the ambiguity rationale.',
    ['missing-ambiguity-witness'],
  ),
  fixture(
    'definition-final-invalid-witness-answer',
    'definition',
    false,
    {
      ...directDefinition(
        'definition-final-invalid-witness-answer',
        'A small stream',
        'BROOK',
        nounSingular,
        nounSingular,
        'They crossed the {0}.',
      ),
      morphology: {
        ...directDefinition(
          'definition-final-invalid-witness-answer-inner',
          'A small stream',
          'BROOK',
          nounSingular,
          nounSingular,
          'They crossed the {0}.',
        ).morphology!,
        substitutionWitness: {
          ...directDefinition(
            'definition-final-invalid-witness-answer-witness',
            'A small stream',
            'BROOK',
            nounSingular,
            nounSingular,
            'They crossed the {0}.',
          ).morphology!.substitutionWitness!,
          answerPhrase: 'CREEK',
        },
      },
    },
    'a direct definition with an answer-mismatched witness',
    'The witness proposes a different answer than the annotation.',
    'Make answerPhrase equal the annotated answer before review.',
    ['missing-substitution-witness'],
  ),
  fixture(
    'definition-final-invalid-span',
    'definition',
    false,
    {
      ...directDefinition(
        'definition-final-invalid-span',
        'A small stream',
        'BROOK',
        nounSingular,
        nounSingular,
        'They crossed the {0}.',
      ),
      signalSpans: [signal('definition-final-invalid-span-signal', 'small', 'register-indicator', 99)],
    },
    'a direct definition with a malformed auxiliary span',
    'The signal span points outside the literal clue text.',
    'Remove the unrelated span or bind it to an exact literal convention.',
    ['invalid-span'],
  ),
];

const releasePackCompletionFactualRelations: ClueGrammarFixture[] = [
  fixture(
    'factual-final-valid-abbreviation-exception',
    'factual-relation',
    true,
    annotation('factual-final-valid-abbreviation-exception', 'Medical scan initials', 'MRI', 'factual-relation', {
      answerIsAbbreviation: true,
      abbreviationEvidence: { kind: 'licensed-exception', exceptionId: 'final-medical-initialism', rationale: 'Registered by the fixture pack.' },
    }),
    'a registered medical initialism',
    'The answer is tied to a declared exception with an editorial rationale.',
    'No repair; fact expansion remains unestablished.',
    [],
    { licensedAbbreviationExceptions: ['final-medical-initialism'] },
  ),
  fixture(
    'factual-final-valid-language',
    'factual-relation',
    true,
    annotation('factual-final-valid-language', 'Good night, in Italian', 'NOTTE', 'factual-relation', {
      morphology: {
        clue: { partOfSpeech: 'phrase', number: 'not-applicable', language: 'en' },
        answer: { partOfSpeech: 'phrase', number: 'not-applicable', language: 'it' },
      },
      signalSpans: [signal('factual-final-valid-language-signal', 'in Italian', 'language-indicator', 12, { language: 'it' })],
    }),
    'the Italian phrase NOTTE',
    'The answer language is named by an exact literal indicator.',
    'No repair; translation accuracy remains a semantic review concern.',
  ),
  fixture(
    'factual-final-valid-title',
    'factual-relation',
    true,
    annotation('factual-final-valid-title', 'Word before “stone” in “stone age”', 'AGE', 'factual-relation', {
      signalSpans: [signal('factual-final-valid-title-quote', '“stone age”', 'quote', 23, { role: 'title' })],
    }),
    'a word identified inside the quoted phrase',
    'The mentioned title surface is represented by a typed quote span.',
    'No repair; phrase truth remains separately unestablished.',
  ),
  fixture(
    'factual-final-valid-plain',
    'factual-relation',
    true,
    annotation('factual-final-valid-plain', 'A red gemstone', 'RUBY', 'factual-relation'),
    'a factual category relation',
    'An ordinary factual surface carries no special punctuation signal.',
    'No repair; retain the relation for later grounding.',
  ),
  fixture(
    'factual-final-invalid-question',
    'factual-relation',
    false,
    annotation('factual-final-invalid-question', 'Astronomer who mapped Mars?', 'LOWELL', 'factual-relation'),
    'a factual identity assertion',
    'The question mark disguises an unreviewed factual claim.',
    'Remove the question mark or classify and explain a genuine pun.',
    ['unexplained-question-mark'],
  ),
  fixture(
    'factual-final-invalid-abbreviation',
    'factual-relation',
    false,
    annotation('factual-final-invalid-abbreviation', 'Space agency vehicle', 'ISS', 'factual-relation', { answerIsAbbreviation: true }),
    'an abbreviated answer without a license',
    'The answer is marked abbreviated but the clue has no indicator or exception.',
    'Add an exact abbreviation indicator or register an exception.',
    ['missing-abbreviation-indicator'],
  ),
  fixture(
    'factual-final-invalid-language',
    'factual-relation',
    false,
    annotation('factual-final-invalid-language', 'Good night, foreign', 'NOTTE', 'factual-relation', {
      morphology: {
        clue: { partOfSpeech: 'phrase', number: 'not-applicable', language: 'en' },
        answer: { partOfSpeech: 'phrase', number: 'not-applicable', language: 'it' },
      },
    }),
    'a foreign-language answer with no named language',
    'The answer language is set without an explicit language indicator.',
    'Name the target language literally or use the clue language.',
    ['missing-language-indicator'],
  ),
  fixture(
    'factual-final-invalid-reference',
    'factual-relation',
    false,
    annotation('factual-final-invalid-reference', 'See 7-Across for the pair', 'DUET', 'factual-relation', {
      signalSpans: [signal('factual-final-invalid-reference-span', '7-Across', 'cross-reference', 4, { targetEntryId: 'entry-7-across', displayedNumber: 7, direction: 'across' })],
    }),
    'a factual clue with an unbound cross-reference',
    'The visible reference cannot be checked without the current puzzle index.',
    'Supply the entry index or remove the cross-reference signal.',
    ['missing-reference-context'],
  ),
];

const releasePackCompletionFillBlanks: ClueGrammarFixture[] = [
  fixture('fill-final-valid-underscores', 'fill-blank', true, fillBlank('fill-final-valid-underscores', 'Trial and ___', 'ERROR', '___'), 'the completion of a familiar phrase', 'The three-underscore marker is literal and exact.', 'No repair; phrase truth remains separate.'),
  fixture('fill-final-valid-long-ellipsis', 'fill-blank', true, fillBlank('fill-final-valid-long-ellipsis', 'And they lived happily ……', 'EVER', '……'), 'the omitted ending of a phrase', 'A longer Unicode ellipsis is retained as the answer marker.', 'No repair; preserve the marker span.'),
  fixture('fill-final-valid-dots', 'fill-blank', true, fillBlank('fill-final-valid-dots', 'First, do no ...', 'HARM', '...'), 'the missing word in a maxim', 'Three periods are treated as the explicit answer slot.', 'No repair; semantic phrase support remains separate.'),
  fixture('fill-final-valid-long-blank', 'fill-blank', true, fillBlank('fill-final-valid-long-blank', 'A ____ in the armor', 'CHINK', '____'), 'the phrase completion', 'A longer underscore marker is still a literal blank.', 'No repair; retain its exact span.'),
  fixture('fill-final-invalid-dash', 'fill-blank', false, fillBlank('fill-final-invalid-dash', 'Trial and --', 'ERROR', '--'), 'the phrase completion', 'Dashes are not one of the house blank-marker forms.', 'Use underscores or an ellipsis and span them exactly.', ['span-role-mismatch']),
  fixture('fill-final-invalid-missing', 'fill-blank', false, annotation('fill-final-invalid-missing', 'First, do no harm', 'HARM', 'fill-blank'), 'the phrase completion', 'The family claims a blank but no literal marker is present.', 'Add and span an explicit blank marker.', ['missing-fill-blank-signal']),
  fixture('fill-final-invalid-offset', 'fill-blank', false, annotation('fill-final-invalid-offset', 'Trial and ___', 'ERROR', 'fill-blank', { signalSpans: [signal('fill-final-invalid-offset-span', '___', 'fill-blank', 0)] }), 'the phrase completion', 'The marker span starts at the wrong offset.', 'Use the marker’s exact offset in the clue.', ['invalid-span']),
  fixture('fill-final-invalid-role', 'fill-blank', false, annotation('fill-final-invalid-role', 'Trial and ___', 'ERROR', 'fill-blank', { signalSpans: [signal('fill-final-invalid-role-span', '___', 'quote', 10, { role: 'mentioned-word' })] }), 'the phrase completion', 'The literal marker is annotated as a quote rather than a fill signal.', 'Use a fill-blank signal for the marker.', ['missing-fill-blank-signal']),
];

const releasePackCompletionSpokenEquivalents: ClueGrammarFixture[] = [
  fixture('spoken-final-valid-agreement', 'spoken-equivalent', true, spoken('spoken-final-valid-agreement', '“Absolutely!”', 'YES'), 'another spoken agreement', 'The whole quoted utterance is typed as a spoken equivalent.', 'No repair; preserve the quote role.'),
  fixture('spoken-final-valid-surprise', 'spoken-equivalent', true, spoken('spoken-final-valid-surprise', '“You did what?”', 'WOW'), 'another spoken reaction', 'The complete question is still a quoted utterance with an interpretation.', 'No repair; punctuation does not replace the interpretation.'),
  fixture('spoken-final-valid-apology', 'spoken-equivalent', true, spoken('spoken-final-valid-apology', '“My mistake.”', 'SORRY'), 'another spoken apology', 'The whole sentence remains inside the spoken-equivalent quote span.', 'No repair; retain the conversational reading.'),
  fixture('spoken-final-valid-dismissal', 'spoken-equivalent', true, spoken('spoken-final-valid-dismissal', '“Whatever.”', 'FINE'), 'another spoken dismissal', 'The full literal utterance carries the required role.', 'No repair; keep the utterance as written.'),
  fixture('spoken-final-invalid-title-role', 'spoken-equivalent', false, annotation('spoken-final-invalid-title-role', '“Absolutely!”', 'YES', 'spoken-equivalent', { interpretation: { intendedSense: 'agreement', explanation: 'A spoken agreement.' }, signalSpans: [signal('spoken-final-invalid-title-role-span', '“Absolutely!”', 'quote', 0, { role: 'title' })] }), 'a spoken agreement', 'A title quote cannot stand in for a spoken-equivalent signal.', 'Use the spoken-equivalent role.', ['missing-whole-quote']),
  fixture('spoken-final-invalid-interpretation', 'spoken-equivalent', false, annotation('spoken-final-invalid-interpretation', '“Absolutely!”', 'YES', 'spoken-equivalent', { signalSpans: [signal('spoken-final-invalid-interpretation-span', '“Absolutely!”', 'quote', 0, { role: 'spoken-equivalent' })] }), 'a spoken agreement', 'The quote is present but the intended utterance is not explained.', 'Add an intended sense and explanation.', ['missing-interpretation']),
  fixture('spoken-final-invalid-offset', 'spoken-equivalent', false, annotation('spoken-final-invalid-offset', '“My mistake.”', 'SORRY', 'spoken-equivalent', { interpretation: { intendedSense: 'apology', explanation: 'A spoken apology.' }, signalSpans: [signal('spoken-final-invalid-offset-span', '“My mistake.”', 'quote', 1, { role: 'spoken-equivalent' })] }), 'a spoken apology', 'The quote span is shifted one character into the clue.', 'Span the whole clue from offset zero.', ['invalid-span', 'missing-whole-quote']),
  fixture('spoken-final-invalid-inline', 'spoken-equivalent', false, spoken('spoken-final-invalid-inline', 'He replied “yes”', 'YES'), 'a spoken agreement', 'An inline quote is not a whole-clue spoken equivalent.', 'Make the entire clue the quoted utterance.', ['missing-whole-quote']),
];

const releasePackCompletionNonverbalExpressions: ClueGrammarFixture[] = [
  fixture('nonverbal-final-valid-laugh', 'nonverbal-expression', true, nonverbal('nonverbal-final-valid-laugh', '[Burst of laughter]', 'HA'), 'letters expressing laughter', 'The complete bracketed surface is a nonverbal action.', 'No repair; retain the bracket role.'),
  fixture('nonverbal-final-valid-shiver', 'nonverbal-expression', true, nonverbal('nonverbal-final-valid-shiver', '[Cold reaction]', 'BRR'), 'letters expressing a cold reaction', 'The square brackets cover the literal clue exactly.', 'No repair; semantic interpretation remains separate.'),
  fixture('nonverbal-final-valid-sneeze', 'nonverbal-expression', true, nonverbal('nonverbal-final-valid-sneeze', '[Achoo]', 'ACHOO'), 'a written sneeze', 'The bracketed action has a typed nonverbal interpretation.', 'No repair; preserve the whole span.'),
  fixture('nonverbal-final-valid-grunt', 'nonverbal-expression', true, nonverbal('nonverbal-final-valid-grunt', '[Effort sound]', 'UGH'), 'a written effort sound', 'The complete bracket span distinguishes reaction from direct definition.', 'No repair; keep the family boundary.'),
  fixture('nonverbal-final-invalid-parentheses', 'nonverbal-expression', false, annotation('nonverbal-final-invalid-parentheses', '(Burst of laughter)', 'HA', 'nonverbal-expression', { interpretation: { intendedSense: 'laughter', explanation: 'A written reaction.' }, signalSpans: [signal('nonverbal-final-invalid-parentheses-span', '(Burst of laughter)', 'brackets', 0, { role: 'nonverbal-expression' })] }), 'a written laugh', 'Parentheses do not satisfy the square-bracket convention.', 'Render square brackets around the complete clue.', ['missing-whole-brackets']),
  fixture('nonverbal-final-invalid-interpretation', 'nonverbal-expression', false, annotation('nonverbal-final-invalid-interpretation', '[Cold reaction]', 'BRR', 'nonverbal-expression', { interpretation: { intendedSense: '', explanation: 'A reaction.' }, signalSpans: [signal('nonverbal-final-invalid-interpretation-span', '[Cold reaction]', 'brackets', 0, { role: 'nonverbal-expression' })] }), 'a written cold reaction', 'The bracket signal has no pinned intended sense.', 'Add a nonempty intended sense.', ['missing-interpretation']),
  fixture('nonverbal-final-invalid-offset', 'nonverbal-expression', false, annotation('nonverbal-final-invalid-offset', '[Achoo]', 'ACHOO', 'nonverbal-expression', { interpretation: { intendedSense: 'a sneeze', explanation: 'A written reaction.' }, signalSpans: [signal('nonverbal-final-invalid-offset-span', '[Achoo]', 'brackets', 1, { role: 'nonverbal-expression' })] }), 'a written sneeze', 'The bracket span begins one character late.', 'Span the whole clue from offset zero.', ['invalid-span', 'missing-whole-brackets']),
  fixture('nonverbal-final-invalid-role', 'nonverbal-expression', false, annotation('nonverbal-final-invalid-role', '[Effort sound]', 'UGH', 'nonverbal-expression', { interpretation: { intendedSense: 'effort sound', explanation: 'A written reaction.' }, signalSpans: [signal('nonverbal-final-invalid-role-span', '[Effort sound]', 'brackets', 0, { role: 'nonverbal-expression' }), signal('nonverbal-final-invalid-role-extra', 'Effort', 'quote', 1, { role: 'spoken-equivalent' })] }), 'a written effort sound', 'A spoken-equivalent signal is attached to a nonverbal clue family.', 'Remove the conflicting quote signal.', ['span-role-mismatch']),
];

const releasePackCompletionSemanticMisdirections: ClueGrammarFixture[] = [
  fixture('misdirection-final-valid-date', 'semantic-misdirection', true, wordplay('misdirection-final-valid-date', 'semantic-misdirection', 'Fruit of labor', 'DATE', { intendedSense: 'a calendar day', surfaceReading: 'a fruit produced by labor', intendedReading: 'a calendar day', explanation: 'Date turns from fruit to a day on the calendar.' }), 'the calendar sense of date', 'Both readings and their turn are explicitly recorded.', 'No repair; semantic equivalence remains unestablished.'),
  fixture('misdirection-final-valid-draft', 'semantic-misdirection', true, wordplay('misdirection-final-valid-draft', 'semantic-misdirection', 'Air current', 'DRAFT', { intendedSense: 'a preliminary version', surfaceReading: 'a flow of air', intendedReading: 'a preliminary version', explanation: 'Draft moves from air flow to an early written version.' }), 'a preliminary version', 'The ordinary surface and intended reading are distinct and explained.', 'No repair; retain both readings for a challenger.'),
  fixture('misdirection-final-valid-stool', 'semantic-misdirection', true, wordplay('misdirection-final-valid-stool', 'semantic-misdirection', 'Bar support', 'STOOL', { intendedSense: 'a seat', surfaceReading: 'a bar support or droppings', intendedReading: 'a seat', explanation: 'Stool resolves from a broad bar-related surface to a seat.' }), 'a seat', 'A two-reading annotation makes the intended turn inspectable.', 'No repair; fairness remains separate.'),
  fixture('misdirection-final-valid-scale', 'semantic-misdirection', true, wordplay('misdirection-final-valid-scale', 'semantic-misdirection', 'Fish measure', 'SCALE', { intendedSense: 'a measuring device', surfaceReading: 'a fish covering', intendedReading: 'a measuring device', explanation: 'Scale turns from fish covering to measurement.' }), 'a measuring device', 'The surface and intended readings are both nonempty.', 'No repair; preserve the explicit interpretation.'),
  fixture('misdirection-final-invalid-surface', 'semantic-misdirection', false, annotation('misdirection-final-invalid-surface', 'Fruit of labor', 'DATE', 'semantic-misdirection', { interpretation: { intendedSense: 'a calendar day', intendedReading: 'a calendar day', explanation: 'A date.' } }), 'the calendar sense of date', 'The surface reading needed to describe the turn is absent.', 'Add the ordinary surface reading.', ['missing-interpretation']),
  fixture('misdirection-final-invalid-intended', 'semantic-misdirection', false, annotation('misdirection-final-invalid-intended', 'Air current', 'DRAFT', 'semantic-misdirection', { interpretation: { intendedSense: 'a preliminary version', surfaceReading: 'a flow of air', explanation: 'A draft.' } }), 'a preliminary version', 'The intended reading is not distinguished from the surface.', 'Record the intended reading explicitly.', ['missing-interpretation']),
  fixture('misdirection-final-invalid-explanation', 'semantic-misdirection', false, wordplay('misdirection-final-invalid-explanation', 'semantic-misdirection', 'Fish measure', 'SCALE', { intendedSense: 'a measuring device', surfaceReading: 'a fish covering', intendedReading: 'a measuring device', explanation: '' }), 'a measuring device', 'The annotation has readings but no account of their relationship.', 'Add a concise explanation.', ['missing-interpretation']),
  fixture('misdirection-final-invalid-none', 'semantic-misdirection', false, annotation('misdirection-final-invalid-none', 'Bar support', 'STOOL', 'semantic-misdirection'), 'a seat', 'The family has no interpretation at all.', 'Add both readings and an explanation.', ['missing-interpretation']),
];

const releasePackCompletionPuns: ClueGrammarFixture[] = [
  fixture('pun-final-valid-bark', 'pun', true, wordplay('pun-final-valid-bark', 'pun', 'Dog speech?', 'BARK', { intendedSense: 'a tree covering', surfaceReading: 'a dog sound', intendedReading: 'a tree covering', explanation: 'Bark turns from an animal sound to tree covering.' }), 'a tree covering', 'The question mark is backed by two recorded readings.', 'No repair; preserve the turn.'),
  fixture('pun-final-valid-board', 'pun', true, wordplay('pun-final-valid-board', 'pun', 'School group?', 'BOARD', { intendedSense: 'a governing group', surfaceReading: 'a classroom surface', intendedReading: 'a governing group', explanation: 'Board turns from a physical surface to a governing group.' }), 'a governing group', 'The playful surface is structurally explained.', 'No repair; semantic satisfaction remains unestablished.'),
  fixture('pun-final-valid-trunk', 'pun', true, wordplay('pun-final-valid-trunk', 'pun', 'Elephant luggage?', 'TRUNK', { intendedSense: 'travel luggage', surfaceReading: 'an elephant nose', intendedReading: 'travel luggage', explanation: 'Trunk turns from an animal feature to luggage.' }), 'travel luggage', 'The question-mark surface has a distinct intended reading.', 'No repair; retain both readings.'),
  fixture('pun-final-valid-spring', 'pun', true, wordplay('pun-final-valid-spring', 'pun', 'Coil season?', 'SPRING', { intendedSense: 'a season', surfaceReading: 'a coiled mechanism', intendedReading: 'a season', explanation: 'Spring turns from a mechanism to a season.' }), 'a season', 'The pun account supplies both literal readings.', 'No repair; fairness remains a later review.'),
  fixture('pun-final-invalid-question', 'pun', false, annotation('pun-final-invalid-question', 'Dog speech?', 'BARK', 'pun', { interpretation: { intendedSense: 'a tree covering', explanation: 'A tree covering.' } }), 'a tree covering', 'A question mark is present without a surface/intended contrast.', 'Add both readings and explain the turn.', ['unexplained-question-mark']),
  fixture('pun-final-invalid-required-policy', 'pun', false, wordplay('pun-final-invalid-required-policy', 'pun', 'School group', 'BOARD', { intendedSense: 'a governing group', surfaceReading: 'a classroom surface', intendedReading: 'a governing group', explanation: 'Board shifts from surface to group.' }), 'a governing group', 'The selected recipe requires question-mark signaling but the clue has none.', 'Add the required question mark or change the recipe.', ['pun-question-mark-policy'], { punQuestionMarkPolicy: 'required' }),
  fixture('pun-final-invalid-forbidden-policy', 'pun', false, wordplay('pun-final-invalid-forbidden-policy', 'pun', 'Elephant luggage?', 'TRUNK', { intendedSense: 'travel luggage', surfaceReading: 'an elephant nose', intendedReading: 'travel luggage', explanation: 'Trunk shifts from animal feature to luggage.' }), 'travel luggage', 'The selected recipe forbids question-mark signaling.', 'Remove the question mark or choose an optional recipe.', ['pun-question-mark-policy'], { punQuestionMarkPolicy: 'forbidden' }),
  fixture('pun-final-invalid-none', 'pun', false, annotation('pun-final-invalid-none', 'Coil season?', 'SPRING', 'pun'), 'a season', 'The pun has neither a reading account nor an explanation.', 'Add both readings and a concise explanation.', ['missing-interpretation', 'unexplained-question-mark']),
];

const releasePackCompletionMetalinguistic: ClueGrammarFixture[] = [
  fixture('meta-final-valid-term', 'metalinguistic', true, annotation('meta-final-valid-term', 'A term for “quick”', 'FAST', 'metalinguistic', { signalSpans: [signal('meta-final-valid-term-marker', 'A term for', 'metalinguistic-marker', 0)] }), 'a term meaning quick', 'The marker says the answer is a word under discussion.', 'No repair; semantic equivalence remains separate.'),
  fixture('meta-final-valid-prefix', 'metalinguistic', true, annotation('meta-final-valid-prefix', 'Prefix meaning “against”', 'ANTI', 'metalinguistic', { signalSpans: [signal('meta-final-valid-prefix-marker', 'Prefix meaning', 'metalinguistic-marker', 0)] }), 'a prefix meaning against', 'The clue explicitly asks for a word part.', 'No repair; preserve the marker span.'),
  fixture('meta-final-valid-letters', 'metalinguistic', true, annotation('meta-final-valid-letters', 'Letters spelling “yes”', 'YEP', 'metalinguistic', { signalSpans: [signal('meta-final-valid-letters-marker', 'Letters spelling', 'metalinguistic-marker', 0)] }), 'letters representing an affirmative', 'The linguistic representation marker is literal and typed.', 'No repair; retain the family distinction.'),
  fixture('meta-final-valid-after', 'metalinguistic', true, annotation('meta-final-valid-after', 'Word after “rain” in “rainbow”', 'BOW', 'metalinguistic', { signalSpans: [signal('meta-final-valid-after-marker', 'Word after', 'metalinguistic-marker', 0), signal('meta-final-valid-after-quote', '“rain”', 'quote', 11, { role: 'mentioned-word' }), signal('meta-final-valid-after-title', '“rainbow”', 'quote', 21, { role: 'title' })] }), 'a word identified within a compound', 'The metalinguistic marker and mentioned-word spans are literal.', 'No repair; preserve the typed spans.'),
  fixture('meta-final-invalid-missing', 'metalinguistic', false, annotation('meta-final-invalid-missing', 'Quick', 'FAST', 'metalinguistic'), 'a word meaning quick', 'A direct definition is mislabeled without a metalinguistic marker.', 'Add a literal marker or use definition.', ['missing-metalinguistic-signal']),
  fixture('meta-final-invalid-offset', 'metalinguistic', false, annotation('meta-final-invalid-offset', 'A term for “quick”', 'FAST', 'metalinguistic', { signalSpans: [signal('meta-final-invalid-offset-marker', 'A term for', 'metalinguistic-marker', 1)] }), 'a word meaning quick', 'The marker begins one character inside the literal phrase.', 'Use the exact phrase offset.', ['invalid-span']),
  fixture('meta-final-invalid-kind', 'metalinguistic', false, annotation('meta-final-invalid-kind', 'Prefix meaning “against”', 'ANTI', 'metalinguistic', { signalSpans: [signal('meta-final-invalid-kind-marker', 'Prefix meaning', 'register-indicator', 0)] }), 'a prefix meaning against', 'The literal marker has the wrong signal kind.', 'Use metalinguistic-marker for the word-about-word convention.', ['missing-metalinguistic-signal']),
  fixture('meta-final-invalid-span', 'metalinguistic', false, annotation('meta-final-invalid-span', 'Letters spelling “yes”', 'YEP', 'metalinguistic', { signalSpans: [signal('meta-final-invalid-span-marker', 'Letters', 'metalinguistic-marker', 1)] }), 'letters representing an affirmative', 'The span is truncated and starts at the wrong offset.', 'Span the complete literal marker at offset zero.', ['invalid-span']),
];

const releasePackCompletionLinked: ClueGrammarFixture[] = [
  fixture('linked-final-valid-seven', 'linked', true, crossReference('linked-final-valid-seven', 'Together with 7-Across', 'TEAM', 7, 'across', 'entry-7-across'), 'an answer linked to 7-Across', 'The displayed reference and target entry agree.', 'No repair; preserve the link.' , [], { entries: linkedEntries }),
  fixture('linked-final-valid-three', 'linked', true, crossReference('linked-final-valid-three', 'Pair with 3-Across', 'DUO', 3, 'across', 'entry-3-across'), 'an answer linked to 3-Across', 'The target index is current and explicit.', 'No repair; retain the target ID.', [], { entries: linkedEntries }),
  fixture('linked-final-valid-eighteen', 'linked', true, crossReference('linked-final-valid-eighteen', 'Together with 18-Down', 'DUET', 18, 'down', 'entry-18-down'), 'an answer linked to 18-Down', 'The down reference resolves against the supplied index.', 'No repair; preserve the direction.', [], { entries: linkedEntries }),
  fixture('linked-final-valid-twelve', 'linked', true, crossReference('linked-final-valid-twelve', 'See 12-Down for its mate', 'PAIR', 12, 'down', 'entry-12-down'), 'an answer linked to 12-Down', 'The reference number, direction, and target all agree.', 'No repair; retain the live reference.', [], { entries: linkedEntries }),
  fixture('linked-final-invalid-context', 'linked', false, crossReference('linked-final-invalid-context', 'See 7-Across', 'TEAM', 7, 'across', 'entry-7-across'), 'a linked answer', 'The reference cannot be validated without an entry index.', 'Supply the current puzzle index.', ['missing-reference-context']),
  fixture('linked-final-invalid-target', 'linked', false, crossReference('linked-final-invalid-target', 'See 3-Across', 'DUO', 3, 'across', 'missing-final-entry'), 'a linked answer', 'The displayed target is absent from the current puzzle.', 'Resolve the target or rewrite the clue.', ['missing-reference-target'], { entries: linkedEntries }),
  fixture('linked-final-invalid-number', 'linked', false, crossReference('linked-final-invalid-number', 'See 8-Across', 'TEAM', 7, 'across', 'entry-7-across', 8), 'a linked answer', 'The printed number disagrees with the annotation and target.', 'Update the visible number and metadata together.', ['stale-cross-reference'], { entries: linkedEntries }),
  fixture('linked-final-invalid-direction', 'linked', false, crossReference('linked-final-invalid-direction', 'See 12-Across', 'PAIR', 12, 'across', 'entry-12-down'), 'a linked answer', 'The printed direction conflicts with the target entry.', 'Use the target direction or point to the correct entry.', ['stale-cross-reference'], { entries: linkedEntries }),
];

const releasePackCompletionThemeDependent: ClueGrammarFixture[] = [
  fixture('theme-final-valid-adverb', 'theme-dependent', true, themed('theme-final-valid-adverb', 'Turn the final letter gently', 'SOFT', 'Turn'), 'an answer governed by the declared letter turn', 'The mechanic cue, reference, and affected-entry context agree.', 'No repair; retain the mechanic explanation.', [], themeContext),
  fixture('theme-final-valid-register', 'theme-dependent', true, themed('theme-final-valid-register', 'Shift the ending sharply', 'EDGE', 'Shift'), 'an answer governed by the declared letter shift', 'The mechanic registry applies to this entry and the cue is literal.', 'No repair; preserve the mechanic reference.', [], themeContext),
  fixture('theme-final-valid-prefix', 'theme-dependent', true, themed('theme-final-valid-prefix', 'Twist the last letter again', 'BEND', 'Twist'), 'an answer governed by the declared letter turn', 'A repeated surface still points at the declared mechanic.', 'No repair; retain the signal span.', [], themeContext),
  fixture('theme-final-valid-suffix', 'theme-dependent', true, themed('theme-final-valid-suffix', 'Turn the ending once more', 'MOVE', 'Turn'), 'an answer governed by the declared letter turn', 'The mechanic explanation and affected entry remain bound.', 'No repair; preserve the context.', [], themeContext),
  fixture('theme-final-invalid-context', 'theme-dependent', false, themed('theme-final-invalid-context', 'Turn the final letter gently', 'SOFT', 'Turn'), 'an answer governed by a declared mechanic', 'Theme validation has no mechanic registry to consult.', 'Supply the puzzle mechanic context.', ['missing-mechanic-context']),
  fixture('theme-final-invalid-signal', 'theme-dependent', false, { ...themed('theme-final-invalid-signal', 'Shift the ending sharply', 'EDGE', 'Shift'), signalSpans: [] }, 'an answer governed by the declared letter shift', 'The mechanic reference has no literal cue span.', 'Add a mechanic-indicator span covering the cue.', ['missing-mechanic-signal'], themeContext),
  fixture('theme-final-invalid-explanation', 'theme-dependent', false, { ...themed('theme-final-invalid-explanation', 'Twist the last letter again', 'BEND', 'Twist'), mechanicRef: { mechanicId: mechanic.id, explanation: '' } }, 'an answer governed by the declared letter turn', 'The mechanic reference has no explanation.', 'Explain how the mechanic applies.', ['missing-mechanic-explanation'], themeContext),
  fixture('theme-final-invalid-unknown', 'theme-dependent', false, { ...themed('theme-final-invalid-unknown', 'Turn the ending once more', 'MOVE', 'Turn'), mechanicRef: { mechanicId: 'missing-final-mechanic', explanation: 'Unknown.' } }, 'an answer governed by a declared mechanic', 'The clue references a mechanic absent from the puzzle registry.', 'Use the declared mechanic ID.', ['unknown-mechanic'], themeContext),
];

/**
 * Ten positive and ten negative cases per currently supported family.  The
 * original smoke rows stay above, while the authored release-pack layers add
 * morphology, punctuation, reference, wordplay, and mechanic variants.  The
 * matrix remains small enough for every CI run and broad enough to keep
 * family boundaries visible during model/prompt changes.
 */
export const CLUE_GRAMMAR_FIXTURES: readonly ClueGrammarFixture[] = [
  ...definitions,
  ...releasePackExpansionDefinitions,
  ...factualRelations,
  ...releasePackExpansionFactualRelations,
  ...fillBlanks,
  ...releasePackExpansionFillBlanks,
  ...spokenEquivalents,
  ...releasePackExpansionSpokenEquivalents,
  ...nonverbalExpressions,
  ...releasePackExpansionNonverbalExpressions,
  ...semanticMisdirections,
  ...releasePackExpansionSemanticMisdirections,
  ...puns,
  ...releasePackExpansionPuns,
  ...metalinguistic,
  ...releasePackExpansionMetalinguistic,
  ...linked,
  ...releasePackExpansionLinked,
  ...themeDependent,
  ...releasePackExpansionThemeDependent,
  ...releasePackCompletionDefinitions,
  ...releasePackCompletionFactualRelations,
  ...releasePackCompletionFillBlanks,
  ...releasePackCompletionSpokenEquivalents,
  ...releasePackCompletionNonverbalExpressions,
  ...releasePackCompletionSemanticMisdirections,
  ...releasePackCompletionPuns,
  ...releasePackCompletionMetalinguistic,
  ...releasePackCompletionLinked,
  ...releasePackCompletionThemeDependent,
];

export type ClueGrammarFixtureCounts = Readonly<{
  total: number;
  valid: number;
  invalid: number;
}>;

/** Per-family release-pack counts, kept as data so CI can enforce the matrix shape. */
export const CLUE_GRAMMAR_FIXTURE_COUNTS: Readonly<
  Partial<Record<ClueFamily, ClueGrammarFixtureCounts>>
> = Object.freeze(
  CLUE_GRAMMAR_FIXTURES.reduce<Record<ClueFamily, ClueGrammarFixtureCounts>>(
    (counts, item) => {
      const current = counts[item.family] ?? { total: 0, valid: 0, invalid: 0 };
      counts[item.family] = {
        total: current.total + 1,
        valid: current.valid + (item.valid ? 1 : 0),
        invalid: current.invalid + (item.valid ? 0 : 1),
      };
      return counts;
    },
    {} as Record<ClueFamily, ClueGrammarFixtureCounts>,
  ),
);
