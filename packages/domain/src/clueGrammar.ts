/**
 * Structural checks for the house clue grammar. These checks validate the
 * supplied annotation and its links to literal clue text; they do not decide
 * whether a clue is true, fair, or semantically equivalent to its answer.
 */
export const CLUE_GRAMMAR_VERSION = 'clue-grammar-v1' as const;

export type ClueVariantRole =
  | 'standard'
  | 'direct-alternative'
  | 'oblique-alternative'
  | 'context-hint'
  | 'convention-hint';

export type ClueFamily =
  | 'definition'
  | 'factual-relation'
  | 'fill-blank'
  | 'spoken-equivalent'
  | 'nonverbal-expression'
  | 'semantic-misdirection'
  | 'pun'
  | 'metalinguistic'
  | 'linked'
  | 'theme-dependent';

export type PartOfSpeech =
  | 'noun'
  | 'verb'
  | 'adjective'
  | 'adverb'
  | 'pronoun'
  | 'preposition'
  | 'conjunction'
  | 'interjection'
  | 'phrase'
  | 'other'
  | 'ambiguous';

export type NumberForm =
  | 'singular'
  | 'plural'
  | 'mass'
  | 'invariant'
  | 'not-applicable'
  | 'ambiguous';

export type VerbTense =
  | 'past'
  | 'present'
  | 'future'
  | 'conditional'
  | 'imperative'
  | 'nonfinite'
  | 'not-applicable'
  | 'ambiguous';

export type VerbAspect =
  | 'simple'
  | 'progressive'
  | 'perfect'
  | 'perfect-progressive'
  | 'not-applicable'
  | 'ambiguous';
export type GrammaticalPerson = 1 | 2 | 3 | 'not-applicable' | 'ambiguous';

export type Register =
  | 'neutral'
  | 'formal'
  | 'informal'
  | 'slang'
  | 'archaic'
  | 'dialectal'
  | 'technical'
  | 'vulgar'
  | 'ambiguous';

export type GrammarFeatures = Readonly<{
  partOfSpeech: PartOfSpeech;
  number: NumberForm;
  tense?: VerbTense;
  aspect?: VerbAspect;
  person?: GrammaticalPerson;
  register?: Register;
  language?: string;
}>;

export type GrammarDimension =
  | 'partOfSpeech'
  | 'number'
  | 'tense'
  | 'aspect'
  | 'person'
  | 'register'
  | 'language';

export type SpanBase = Readonly<{
  id: string;
  start: number;
  end: number;
  text: string;
}>;

export type ClueSignalSpan =
  | (SpanBase &
      Readonly<{
        kind: 'quote';
        role: 'spoken-equivalent' | 'title' | 'mentioned-word';
      }>)
  | (SpanBase & Readonly<{ kind: 'brackets'; role: 'nonverbal-expression' }>)
  | (SpanBase & Readonly<{ kind: 'abbreviation-indicator' }>)
  | (SpanBase & Readonly<{ kind: 'language-indicator'; language: string }>)
  | (SpanBase &
      Readonly<{
        kind: 'cross-reference';
        targetEntryId: string;
        displayedNumber: number;
        direction: 'across' | 'down';
      }>)
  | (SpanBase &
      Readonly<{
        kind:
          | 'theme-indicator'
          | 'mechanic-indicator'
          | 'register-indicator'
          | 'fill-blank'
          | 'metalinguistic-marker';
      }>);

export type SubstitutionWitness = Readonly<{
  /** A common slot in which the clue phrase and answer phrase are proposed substitutes. */
  frame: string;
  cluePhrase: string;
  answerPhrase: string;
  editorialNote: string;
  reviewerId: string;
}>;

export type AmbiguityWitness = Readonly<{
  dimension: GrammarDimension;
  resolvedAs: string | number;
  explanation: string;
  reviewerId: string;
}>;

export type ConstructionWitness = Readonly<{
  kind:
    | 'conversion'
    | 'ellipsis'
    | 'phrase-response'
    | 'nominalization'
    | 'other';
  cluePartOfSpeech: PartOfSpeech;
  answerPartOfSpeech: PartOfSpeech;
  exampleFrame: string;
  explanation: string;
  reviewerId: string;
}>;

export type ClueInterpretation = Readonly<{
  intendedSense: string;
  surfaceReading?: string;
  intendedReading?: string;
  explanation: string;
}>;

export type AbbreviationEvidence =
  | Readonly<{ kind: 'indicator-span'; spanId: string }>
  | Readonly<{
      kind: 'licensed-exception';
      exceptionId: string;
      rationale: string;
    }>;

export type ClueMechanicReference = Readonly<{
  mechanicId: string;
  explanation: string;
}>;

export type ClueGrammarAnnotation = Readonly<{
  grammarVersion: typeof CLUE_GRAMMAR_VERSION;
  clueId: string;
  entryId: string;
  clueText: string;
  answer: string;
  answerIsAbbreviation?: boolean;
  variantRole: ClueVariantRole;
  primaryFamily: ClueFamily;
  morphology?: Readonly<{
    clue: GrammarFeatures;
    answer: GrammarFeatures;
    substitutionWitness?: SubstitutionWitness;
    ambiguityWitnesses?: readonly AmbiguityWitness[];
    constructionWitness?: ConstructionWitness;
  }>;
  signalSpans: readonly ClueSignalSpan[];
  interpretation?: ClueInterpretation;
  abbreviationEvidence?: AbbreviationEvidence;
  mechanicRef?: ClueMechanicReference;
}>;

export type CrosswordEntryReference = Readonly<{
  entryId: string;
  number: number;
  direction: 'across' | 'down';
}>;

export type PuzzleMechanic = Readonly<{
  id: string;
  family: string;
  affectedEntryIds: readonly string[];
  requiredSignal?: 'theme-indicator' | 'mechanic-indicator';
  explanationRequired?: boolean;
}>;

export type ClueGrammarContext = Readonly<{
  currentEntryId?: string;
  entries?: readonly CrosswordEntryReference[];
  mechanics?: readonly PuzzleMechanic[];
  licensedAbbreviationExceptions?: readonly string[];
  punQuestionMarkPolicy?: 'required' | 'optional' | 'forbidden';
  /** Admission-mode safety for answer leakage and dead-end clue templates. */
  enforceAnswerSafety?: boolean;
}>;

export type ClueGrammarIssueCode =
  | 'unsupported-version'
  | 'invalid-annotation'
  | 'unknown-role'
  | 'unknown-family'
  | 'invalid-span'
  | 'span-role-mismatch'
  | 'missing-morphology'
  | 'missing-verb-morphology'
  | 'missing-substitution-witness'
  | 'missing-ambiguity-witness'
  | 'morphology-mismatch'
  | 'unsupported-part-of-speech-switch'
  | 'missing-interpretation'
  | 'missing-whole-quote'
  | 'missing-whole-brackets'
  | 'unexplained-question-mark'
  | 'pun-question-mark-policy'
  | 'missing-abbreviation-indicator'
  | 'unknown-abbreviation-exception'
  | 'missing-language-indicator'
  | 'missing-fill-blank-signal'
  | 'missing-metalinguistic-signal'
  | 'missing-reference-context'
  | 'missing-cross-reference'
  | 'missing-reference-target'
  | 'stale-cross-reference'
  | 'missing-mechanic-context'
  | 'missing-mechanic-reference'
  | 'unknown-mechanic'
  | 'mechanic-not-applicable'
  | 'missing-mechanic-signal'
  | 'missing-mechanic-explanation'
  | 'missing-register-signal'
  | 'answer-giveaway'
  | 'answer-form-in-clue'
  | 'generic-clue'
  | 'plural-marker-mismatch'
  | 'past-tense-marker-mismatch';

export type ClueGrammarIssue = Readonly<{
  code: ClueGrammarIssueCode;
  message: string;
  path?: string;
}>;

export type ClueGrammarValidation = Readonly<{
  valid: boolean;
  issues: readonly ClueGrammarIssue[];
  /** A successful structural check never establishes semantic correctness. */
  semanticStatus: 'not-established';
}>;

type FamilyRule = Readonly<{
  requiresMorphology?: boolean;
  requiresInterpretation?: boolean;
  requiredSignal?: ClueSignalSpan['kind'];
}>;

/** Versioned rule table: family identifies how the clue works; role says why it is shown. */
export const CLUE_FAMILY_RULES: Readonly<Record<ClueFamily, FamilyRule>> = {
  definition: { requiresMorphology: true },
  'factual-relation': {},
  'fill-blank': { requiredSignal: 'fill-blank' },
  'spoken-equivalent': {
    requiredSignal: 'quote',
    requiresInterpretation: true,
  },
  'nonverbal-expression': {
    requiredSignal: 'brackets',
    requiresInterpretation: true,
  },
  'semantic-misdirection': { requiresInterpretation: true },
  pun: { requiresInterpretation: true },
  metalinguistic: { requiredSignal: 'metalinguistic-marker' },
  linked: { requiredSignal: 'cross-reference' },
  'theme-dependent': { requiresInterpretation: true },
};

const CLUE_ROLES: readonly ClueVariantRole[] = [
  'standard',
  'direct-alternative',
  'oblique-alternative',
  'context-hint',
  'convention-hint',
];

const CLUE_FAMILIES = Object.keys(CLUE_FAMILY_RULES) as ClueFamily[];
const AMBIGUOUS_VALUE = 'ambiguous';

function nonEmpty(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isOneOf<T extends string>(
  value: unknown,
  allowed: readonly T[],
): value is T {
  return (
    typeof value === 'string' && (allowed as readonly string[]).includes(value)
  );
}

const PARTS_OF_SPEECH: readonly PartOfSpeech[] = [
  'noun',
  'verb',
  'adjective',
  'adverb',
  'pronoun',
  'preposition',
  'conjunction',
  'interjection',
  'phrase',
  'other',
  'ambiguous',
];
const NUMBER_FORMS: readonly NumberForm[] = [
  'singular',
  'plural',
  'mass',
  'invariant',
  'not-applicable',
  'ambiguous',
];
const TENSES: readonly VerbTense[] = [
  'past',
  'present',
  'future',
  'conditional',
  'imperative',
  'nonfinite',
  'not-applicable',
  'ambiguous',
];
const ASPECTS: readonly VerbAspect[] = [
  'simple',
  'progressive',
  'perfect',
  'perfect-progressive',
  'not-applicable',
  'ambiguous',
];
const PERSONS: readonly (1 | 2 | 3 | 'not-applicable' | 'ambiguous')[] = [
  1,
  2,
  3,
  'not-applicable',
  'ambiguous',
];
const REGISTERS: readonly Register[] = [
  'neutral',
  'formal',
  'informal',
  'slang',
  'archaic',
  'dialectal',
  'technical',
  'vulgar',
  'ambiguous',
];

function isGrammarFeatures(value: unknown): value is GrammarFeatures {
  if (
    !isRecord(value) ||
    !isOneOf(value.partOfSpeech, PARTS_OF_SPEECH) ||
    !isOneOf(value.number, NUMBER_FORMS)
  )
    return false;
  if (value.tense !== undefined && !isOneOf(value.tense, TENSES)) return false;
  if (value.aspect !== undefined && !isOneOf(value.aspect, ASPECTS))
    return false;
  if (
    value.person !== undefined &&
    !PERSONS.includes(value.person as (typeof PERSONS)[number])
  )
    return false;
  if (value.register !== undefined && !isOneOf(value.register, REGISTERS))
    return false;
  return value.language === undefined || typeof value.language === 'string';
}

function isSignalSpan(value: unknown): value is ClueSignalSpan {
  if (
    !isRecord(value) ||
    !nonEmpty(value.id) ||
    !Number.isInteger(value.start) ||
    !Number.isInteger(value.end) ||
    typeof value.text !== 'string'
  )
    return false;
  switch (value.kind) {
    case 'quote':
      return isOneOf(value.role, [
        'spoken-equivalent',
        'title',
        'mentioned-word',
      ] as const);
    case 'brackets':
      return value.role === 'nonverbal-expression';
    case 'abbreviation-indicator':
    case 'theme-indicator':
    case 'mechanic-indicator':
    case 'register-indicator':
    case 'fill-blank':
    case 'metalinguistic-marker':
      return true;
    case 'language-indicator':
      return nonEmpty(value.language);
    case 'cross-reference':
      return (
        nonEmpty(value.targetEntryId) &&
        typeof value.displayedNumber === 'number' &&
        Number.isInteger(value.displayedNumber) &&
        value.displayedNumber > 0 &&
        (value.direction === 'across' || value.direction === 'down')
      );
    default:
      return false;
  }
}

function isMorphology(
  value: unknown,
): value is NonNullable<ClueGrammarAnnotation['morphology']> {
  if (
    !isRecord(value) ||
    !isGrammarFeatures(value.clue) ||
    !isGrammarFeatures(value.answer)
  )
    return false;
  const substitution = value.substitutionWitness;
  if (
    substitution !== undefined &&
    (!isRecord(substitution) ||
      typeof substitution.frame !== 'string' ||
      typeof substitution.cluePhrase !== 'string' ||
      typeof substitution.answerPhrase !== 'string' ||
      typeof substitution.editorialNote !== 'string' ||
      typeof substitution.reviewerId !== 'string')
  )
    return false;
  const ambiguity = value.ambiguityWitnesses;
  if (
    ambiguity !== undefined &&
    (!Array.isArray(ambiguity) ||
      ambiguity.some(
        (item) =>
          !isRecord(item) ||
          typeof item.dimension !== 'string' ||
          ![
            'partOfSpeech',
            'number',
            'tense',
            'aspect',
            'person',
            'register',
            'language',
          ].includes(item.dimension) ||
          (typeof item.resolvedAs !== 'string' &&
            typeof item.resolvedAs !== 'number') ||
          typeof item.explanation !== 'string' ||
          typeof item.reviewerId !== 'string',
      ))
  )
    return false;
  const construction = value.constructionWitness;
  if (
    construction !== undefined &&
    (!isRecord(construction) ||
      ![
        'conversion',
        'ellipsis',
        'phrase-response',
        'nominalization',
        'other',
      ].includes(String(construction.kind)) ||
      !isOneOf(construction.cluePartOfSpeech, PARTS_OF_SPEECH) ||
      !isOneOf(construction.answerPartOfSpeech, PARTS_OF_SPEECH) ||
      typeof construction.exampleFrame !== 'string' ||
      typeof construction.explanation !== 'string' ||
      typeof construction.reviewerId !== 'string')
  )
    return false;
  return true;
}

function isInterpretation(value: unknown): value is ClueInterpretation {
  return (
    isRecord(value) &&
    typeof value.intendedSense === 'string' &&
    typeof value.explanation === 'string' &&
    (value.surfaceReading === undefined ||
      typeof value.surfaceReading === 'string') &&
    (value.intendedReading === undefined ||
      typeof value.intendedReading === 'string')
  );
}

function hasWholeSpeechQuotes(text: string): boolean {
  const quotePairs: Readonly<Record<string, string>> = {
    '"': '"',
    '“': '”',
    '‘': '’',
  };
  const opening = text[0];
  const closing = opening ? quotePairs[opening] : undefined;
  return Boolean(closing && text.length >= 2 && text.at(-1) === closing);
}

function hasWholeSquareBrackets(text: string): boolean {
  return /^\[[^\]]+\]$/u.test(text) && !text.slice(1, -1).includes('[');
}

function normalizedAnswerSurface(answer: string): string {
  return answer.toLocaleUpperCase().replace(/[^\p{L}]/gu, '');
}

function answerLexicalForms(answer: string): readonly string[] {
  const normalized = normalizedAnswerSurface(answer);
  if (!normalized) return [];
  const forms = new Set([normalized]);
  if (normalized.length < 3) return [...forms];
  if (normalized.endsWith('IES') && normalized.length > 3) {
    forms.add(`${normalized.slice(0, -3)}Y`);
  }
  if (normalized.endsWith('ES') && normalized.length > 4) {
    forms.add(normalized.slice(0, -2));
  }
  if (normalized.endsWith('S') && !normalized.endsWith('SS') && normalized.length > 3) {
    forms.add(normalized.slice(0, -1));
  }
  if (!normalized.endsWith('S')) forms.add(`${normalized}S`);
  if (!normalized.endsWith('ES')) forms.add(`${normalized}ES`);
  if (normalized.endsWith('ING') && normalized.length > 5) {
    forms.add(normalized.slice(0, -3));
  }
  if (normalized.endsWith('ED') && normalized.length > 4) {
    forms.add(normalized.slice(0, -2));
  }
  if (normalized.endsWith('E') && normalized.length > 3) {
    forms.add(`${normalized.slice(0, -1)}ED`);
  } else {
    forms.add(`${normalized}ED`);
  }
  if (!normalized.endsWith('ING')) forms.add(`${normalized}ING`);
  return [...forms].filter((form) => form.length >= 3);
}

function validateAnswerSafety(
  clue: ClueGrammarAnnotation,
  issues: ClueGrammarIssue[],
): void {
  const upperText = clue.clueText.toLocaleUpperCase();
  const tokens = [...upperText.matchAll(/[\p{L}]+/gu)].map((match) => ({
    value: match[0],
  }));
  const overlap = answerLexicalForms(clue.answer).reduce<string | null>((found, form) => {
    if (found) return found;
    const token = tokens.find((item) => item.value === form);
    return token ? form : null;
  }, null);
  if (overlap) {
    issue(
      issues,
      overlap === normalizedAnswerSurface(clue.answer)
        ? 'answer-giveaway'
        : 'answer-form-in-clue',
      'A clue must not repeat the answer or an obvious lexical form of it.',
      'clueText',
    );
  }

  const normalized = clue.clueText.trim().replace(/\s+/gu, ' ');
  if (
    /\b(?:common|usual|ordinary|generic|standard)\s+(?:(?:[\p{L}\p{N}][\p{L}\p{N}'’/-]*|\d+)\s+){0,3}(?:name|term|word|designation|label)\b/iu.test(normalized) ||
    /^(?:(?:a|an|the)\s+)?(?:(?:famous|well[- ]known|notable|popular|renowned|celebrated|italian|french|german|spanish|japanese|portuguese|dutch)\s+)?(?:actor|actress|author|band|character|director|king|queen|singer|surname|writer|person|president|saint|celebrity)(?:'s|’s)?\s+name(?:\s*,?\s*perhaps)?[?.]?$/iu.test(
      normalized,
    )
  ) {
    issue(
      issues,
      'generic-clue',
      'A generic name or term template does not give the player a route into the answer.',
      'clueText',
    );
  }

  const answer = clue.answer.toLocaleUpperCase().replace(/[^A-Z]/gu, '');
  const pluralMarker = /[\[(]\s*pl\.?\s*[\])]/iu.test(clue.clueText);
  const pastMarker =
    /\bpast(?:\s+tense)?\b|[\[(]\s*past(?:\s+tense)?\s*[\])]/iu.test(
      clue.clueText,
    );
  const irregularPlurals = new Set([
    'CHILDREN',
    'FEET',
    'GEESE',
    'MEN',
    'MICE',
    'PEOPLE',
    'TEETH',
    'WOMEN',
    'OXEN',
  ]);
  const looksPlural =
    irregularPlurals.has(answer) ||
    (answer.length > 3 &&
      answer.endsWith('S') &&
      !answer.endsWith('SS') &&
      !answer.endsWith('US') &&
      !answer.endsWith('IS'));
  const irregularPast = new Set([
    'ATE',
    'BEGAN',
    'BENT',
    'BOUGHT',
    'BROUGHT',
    'BUILT',
    'CAME',
    'DID',
    'DREW',
    'DRANK',
    'DROVE',
    'FELT',
    'FLEW',
    'FOUND',
    'GAVE',
    'GOT',
    'GREW',
    'HAD',
    'HEARD',
    'HELD',
    'KEPT',
    'KNEW',
    'LEFT',
    'LOST',
    'MADE',
    'MET',
    'PAID',
    'PUT',
    'RAN',
    'READ',
    'ROSE',
    'SAID',
    'SAW',
    'SANG',
    'SENT',
    'SLEPT',
    'SPOKE',
    'STOOD',
    'SWAM',
    'TOOK',
    'WAS',
    'WENT',
    'WERE',
    'WORE',
    'WROTE',
  ]);
  const looksPast = irregularPast.has(answer) || answer.endsWith('ED');
  if (pluralMarker && !looksPlural) {
    issue(
      issues,
      'plural-marker-mismatch',
      'An explicit plural marker must accompany an obviously plural answer form.',
      'clueText',
    );
  }
  if (pastMarker && !looksPast) {
    issue(
      issues,
      'past-tense-marker-mismatch',
      'An explicit past-tense marker must accompany an obviously past answer form.',
      'clueText',
    );
  }
}

function issue(
  issues: ClueGrammarIssue[],
  code: ClueGrammarIssueCode,
  message: string,
  path?: string,
): void {
  issues.push({ code, message, ...(path ? { path } : {}) });
}

function validateSpanBounds(
  clue: ClueGrammarAnnotation,
  issues: ClueGrammarIssue[],
): void {
  const spanIds = new Set<string>();
  clue.signalSpans.forEach((span, index) => {
    const path = `signalSpans[${index}]`;
    if (!nonEmpty(span.id) || spanIds.has(span.id)) {
      issue(
        issues,
        'invalid-span',
        'Signal span IDs must be nonempty and unique.',
        path,
      );
    }
    spanIds.add(span.id);
    if (
      !Number.isInteger(span.start) ||
      !Number.isInteger(span.end) ||
      span.start < 0 ||
      span.end <= span.start ||
      span.end > clue.clueText.length ||
      clue.clueText.slice(span.start, span.end) !== span.text
    ) {
      issue(
        issues,
        'invalid-span',
        'Signal span offsets and literal text must match the clue exactly.',
        path,
      );
    }
  });
}

function hasSignal(
  clue: ClueGrammarAnnotation,
  kind: ClueSignalSpan['kind'],
): boolean {
  return clue.signalSpans.some((span) => span.kind === kind);
}

function validateMorphology(
  clue: ClueGrammarAnnotation,
  issues: ClueGrammarIssue[],
): void {
  const morphology = clue.morphology;
  if (CLUE_FAMILY_RULES[clue.primaryFamily].requiresMorphology && !morphology) {
    issue(
      issues,
      'missing-morphology',
      'Definition clues need explicit clue and answer morphology.',
    );
    return;
  }
  if (!morphology) return;

  const { clue: clueForm, answer: answerForm } = morphology;
  if (clueForm.partOfSpeech === 'verb' || answerForm.partOfSpeech === 'verb') {
    const verbFields: readonly (keyof Pick<
      GrammarFeatures,
      'tense' | 'aspect' | 'person'
    >)[] = ['tense', 'aspect', 'person'];
    const missing = verbFields.filter(
      (field) =>
        clueForm[field] === undefined || answerForm[field] === undefined,
    );
    if (missing.length > 0) {
      issue(
        issues,
        'missing-verb-morphology',
        `Verb readings must record tense, aspect, and person on both sides; missing ${missing.join(', ')}.`,
        'morphology',
      );
    }
  }
  if (clue.primaryFamily === 'definition' && !morphology.substitutionWitness) {
    issue(
      issues,
      'missing-substitution-witness',
      'A direct definition needs an editor-authored substitution frame.',
    );
  }
  if (morphology.substitutionWitness) {
    const witness = morphology.substitutionWitness;
    const normalizedAnswer = (value: string) =>
      value.trim().replace(/\s+/gu, ' ').toLocaleLowerCase();
    if (
      !nonEmpty(witness.frame) ||
      (witness.frame.match(/\{0\}/gu)?.length ?? 0) !== 1 ||
      !nonEmpty(witness.cluePhrase) ||
      !nonEmpty(witness.answerPhrase) ||
      !clue.clueText
        .toLocaleLowerCase()
        .includes(witness.cluePhrase.toLocaleLowerCase()) ||
      normalizedAnswer(witness.answerPhrase) !==
        normalizedAnswer(clue.answer) ||
      !nonEmpty(witness.editorialNote) ||
      !nonEmpty(witness.reviewerId)
    ) {
      issue(
        issues,
        'missing-substitution-witness',
        'A substitution witness needs a {0} frame, both proposed substitutions, a note, and a reviewer ID.',
      );
    }
  }

  const ambiguityWitnesses = morphology.ambiguityWitnesses ?? [];
  const compare = (
    dimension: GrammarDimension,
    left: string | number | undefined,
    right: string | number | undefined,
  ) => {
    if (left === undefined || right === undefined) return;
    if (left === AMBIGUOUS_VALUE || right === AMBIGUOUS_VALUE) {
      if (left === AMBIGUOUS_VALUE && right === AMBIGUOUS_VALUE) {
        issue(
          issues,
          'missing-ambiguity-witness',
          `Both ${dimension} readings are unresolved; at least one side needs a pinned value.`,
          `morphology.${dimension}`,
        );
        return;
      }
      const witness = ambiguityWitnesses.find(
        (item) => item.dimension === dimension,
      );
      if (
        !witness ||
        !nonEmpty(witness.explanation) ||
        !nonEmpty(witness.reviewerId)
      ) {
        issue(
          issues,
          'missing-ambiguity-witness',
          `Ambiguous ${dimension} requires an editor-selected reading and rationale.`,
          `morphology.${dimension}`,
        );
        return;
      }
      const intended = left === AMBIGUOUS_VALUE ? right : left;
      if (String(witness.resolvedAs) !== String(intended)) {
        issue(
          issues,
          'morphology-mismatch',
          `The ${dimension} ambiguity witness does not resolve to the other annotated form.`,
          `morphology.${dimension}`,
        );
      }
      return;
    }
    if (left === right) return;
    if (
      dimension === 'number' &&
      right === 'invariant' &&
      (left === 'singular' || left === 'plural')
    )
      return;
    if (dimension === 'partOfSpeech') {
      const witness = morphology.constructionWitness;
      if (
        witness &&
        witness.cluePartOfSpeech === clueForm.partOfSpeech &&
        witness.answerPartOfSpeech === answerForm.partOfSpeech &&
        nonEmpty(witness.exampleFrame) &&
        nonEmpty(witness.explanation) &&
        nonEmpty(witness.reviewerId)
      )
        return;
      issue(
        issues,
        'unsupported-part-of-speech-switch',
        'Different clue and answer parts of speech need a reviewed construction witness.',
        'morphology.partOfSpeech',
      );
      return;
    }
    if (dimension === 'register' && hasSignal(clue, 'register-indicator'))
      return;
    issue(
      issues,
      'morphology-mismatch',
      `The clue and answer ${dimension} annotations disagree.`,
      `morphology.${dimension}`,
    );
  };

  compare('partOfSpeech', clueForm.partOfSpeech, answerForm.partOfSpeech);
  compare('number', clueForm.number, answerForm.number);
  compare('tense', clueForm.tense, answerForm.tense);
  compare('aspect', clueForm.aspect, answerForm.aspect);
  compare('person', clueForm.person, answerForm.person);
  compare('register', clueForm.register, answerForm.register);
  if (
    answerForm.register &&
    answerForm.register !== 'neutral' &&
    clueForm.register !== answerForm.register &&
    !hasSignal(clue, 'register-indicator')
  ) {
    issue(
      issues,
      'missing-register-signal',
      'A marked answer register needs a matching clue register or an explicit register signal.',
    );
  }
}

function validateFamilySignals(
  clue: ClueGrammarAnnotation,
  context: ClueGrammarContext,
  issues: ClueGrammarIssue[],
): void {
  const rule = CLUE_FAMILY_RULES[clue.primaryFamily];
  for (const span of clue.signalSpans) {
    if (
      span.kind === 'quote' &&
      span.role === 'spoken-equivalent' &&
      clue.primaryFamily !== 'spoken-equivalent'
    ) {
      issue(
        issues,
        'span-role-mismatch',
        'A whole spoken-equivalent quote must use the spoken-equivalent clue family.',
        `signalSpans.${span.id}`,
      );
    }
    if (
      span.kind === 'brackets' &&
      clue.primaryFamily !== 'nonverbal-expression'
    ) {
      issue(
        issues,
        'span-role-mismatch',
        'Literal square brackets are reserved for nonverbal-expression clues.',
        `signalSpans.${span.id}`,
      );
    }
    if (
      span.kind === 'fill-blank' &&
      !/^(?:_{3,}|…+|\.{3,})$/u.test(span.text.trim())
    ) {
      issue(
        issues,
        'span-role-mismatch',
        'A fill-blank span must match a literal blank marker such as ___ or an ellipsis.',
        `signalSpans.${span.id}`,
      );
    }
  }
  if (rule.requiredSignal && !hasSignal(clue, rule.requiredSignal)) {
    const code: ClueGrammarIssueCode =
      rule.requiredSignal === 'cross-reference'
        ? 'missing-cross-reference'
        : rule.requiredSignal === 'fill-blank'
          ? 'missing-fill-blank-signal'
          : rule.requiredSignal === 'metalinguistic-marker'
            ? 'missing-metalinguistic-signal'
            : rule.requiredSignal === 'quote'
              ? 'missing-whole-quote'
              : rule.requiredSignal === 'brackets'
                ? 'missing-whole-brackets'
                : 'span-role-mismatch';
    issue(
      issues,
      code,
      `The ${clue.primaryFamily} family requires a ${rule.requiredSignal} signal.`,
    );
  }
  if (rule.requiresInterpretation && !clue.interpretation) {
    issue(
      issues,
      'missing-interpretation',
      `${clue.primaryFamily} clues need an explicit intended reading and explanation.`,
    );
  } else if (
    clue.interpretation &&
    (!nonEmpty(clue.interpretation.intendedSense) ||
      !nonEmpty(clue.interpretation.explanation))
  ) {
    issue(
      issues,
      'missing-interpretation',
      'Interpretation annotations need a pinned sense and concise explanation.',
    );
  }
  if (
    clue.primaryFamily === 'semantic-misdirection' &&
    (!nonEmpty(clue.interpretation?.surfaceReading) ||
      !nonEmpty(clue.interpretation?.intendedReading))
  ) {
    issue(
      issues,
      'missing-interpretation',
      'Semantic misdirection needs both the surface reading and the intended reading.',
    );
  }

  if (clue.primaryFamily === 'spoken-equivalent') {
    const span = clue.signalSpans.find(
      (item) => item.kind === 'quote' && item.role === 'spoken-equivalent',
    );
    if (
      !span ||
      span.start !== 0 ||
      span.end !== clue.clueText.length ||
      !hasWholeSpeechQuotes(clue.clueText)
    ) {
      issue(
        issues,
        'missing-whole-quote',
        'Spoken-equivalent quotes must surround the entire literal utterance.',
      );
    }
  }
  if (clue.primaryFamily === 'nonverbal-expression') {
    const span = clue.signalSpans.find(
      (item) =>
        item.kind === 'brackets' && item.role === 'nonverbal-expression',
    );
    if (
      !span ||
      span.start !== 0 ||
      span.end !== clue.clueText.length ||
      !hasWholeSquareBrackets(clue.clueText)
    ) {
      issue(
        issues,
        'missing-whole-brackets',
        'Nonverbal-expression brackets must enclose the whole literal clue.',
      );
    }
  }

  const endsInQuestionMark = clue.clueText.trimEnd().endsWith('?');
  const punPolicy = context.punQuestionMarkPolicy ?? 'optional';
  const hasWordplayAccount = Boolean(
    clue.interpretation &&
      nonEmpty(clue.interpretation.surfaceReading) &&
      nonEmpty(clue.interpretation.intendedReading) &&
      nonEmpty(clue.interpretation.explanation),
  );
  if (
    endsInQuestionMark &&
    (clue.primaryFamily !== 'pun' || !hasWordplayAccount)
  ) {
    issue(
      issues,
      'unexplained-question-mark',
      'A final question mark requires a reviewed pun family and both surface and intended readings.',
    );
  }
  if (
    clue.primaryFamily === 'pun' &&
    punPolicy === 'required' &&
    !endsInQuestionMark
  ) {
    issue(
      issues,
      'pun-question-mark-policy',
      'This puzzle recipe requires question-mark signaling for pun clues.',
    );
  }
  if (
    clue.primaryFamily === 'pun' &&
    punPolicy === 'forbidden' &&
    endsInQuestionMark
  ) {
    issue(
      issues,
      'pun-question-mark-policy',
      'This puzzle recipe forbids question-mark pun signaling.',
    );
  }

  if (clue.answerIsAbbreviation) {
    const evidence = clue.abbreviationEvidence;
    if (!evidence) {
      issue(
        issues,
        'missing-abbreviation-indicator',
        'An abbreviated answer needs an exact indicator span or a registered exception.',
      );
    } else if (evidence.kind === 'indicator-span') {
      if (
        !clue.signalSpans.some(
          (span) =>
            span.id === evidence.spanId &&
            span.kind === 'abbreviation-indicator',
        )
      ) {
        issue(
          issues,
          'missing-abbreviation-indicator',
          'Abbreviation evidence must point to the literal abbreviation-indicator span.',
        );
      }
    } else if (
      !(context.licensedAbbreviationExceptions ?? []).includes(
        evidence.exceptionId,
      ) ||
      !nonEmpty(evidence.rationale)
    ) {
      issue(
        issues,
        'unknown-abbreviation-exception',
        'Abbreviation exceptions must be registered and include an editorial rationale.',
      );
    }
  } else if (clue.abbreviationEvidence) {
    issue(
      issues,
      'span-role-mismatch',
      'Abbreviation evidence is present for an answer not annotated as abbreviated.',
      'abbreviationEvidence',
    );
  }

  const targetLanguage = clue.morphology?.answer.language;
  if (
    targetLanguage &&
    !clue.signalSpans.some(
      (span) =>
        span.kind === 'language-indicator' && span.language === targetLanguage,
    )
  ) {
    issue(
      issues,
      'missing-language-indicator',
      'A language-specific answer needs a matching explicit language-indicator span.',
    );
  }

  if (clue.primaryFamily === 'linked')
    validateReferences(clue, context, issues);
  else if (clue.signalSpans.some((span) => span.kind === 'cross-reference'))
    validateReferences(clue, context, issues);

  if (
    clue.primaryFamily === 'theme-dependent' ||
    clue.mechanicRef ||
    context.mechanics?.some((mechanic) =>
      mechanic.affectedEntryIds.includes(clue.entryId),
    )
  )
    validateMechanic(clue, context, issues);
}

function validateReferences(
  clue: ClueGrammarAnnotation,
  context: ClueGrammarContext,
  issues: ClueGrammarIssue[],
): void {
  const referenceSpans = clue.signalSpans.filter(
    (span) => span.kind === 'cross-reference',
  );
  if (referenceSpans.length === 0) return;
  if (!context.entries) {
    issue(
      issues,
      'missing-reference-context',
      'Cross-references require the current puzzle entry index.',
    );
    return;
  }
  for (const [index, span] of referenceSpans.entries()) {
    const visibleTarget = span.text.match(/\b(\d+)\s*[-–]\s*(across|down)\b/iu);
    if (
      !visibleTarget ||
      Number(visibleTarget[1]) !== span.displayedNumber ||
      visibleTarget[2]?.toLowerCase() !== span.direction
    ) {
      issue(
        issues,
        'stale-cross-reference',
        `The printed reference text does not encode ${span.displayedNumber}-${span.direction}.`,
        `signalSpans.${span.id}`,
      );
    }
    const target = context.entries.find(
      (entry) => entry.entryId === span.targetEntryId,
    );
    if (!target) {
      issue(
        issues,
        'missing-reference-target',
        `Cross-reference target ${span.targetEntryId} is not in this puzzle.`,
        `signalSpans.${span.id}`,
      );
    } else if (
      target.number !== span.displayedNumber ||
      target.direction !== span.direction
    ) {
      issue(
        issues,
        'stale-cross-reference',
        `Cross-reference ${index + 1} no longer matches the target entry's number and direction.`,
        `signalSpans.${span.id}`,
      );
    }
  }
}

function validateMechanic(
  clue: ClueGrammarAnnotation,
  context: ClueGrammarContext,
  issues: ClueGrammarIssue[],
): void {
  if (!context.mechanics) {
    issue(
      issues,
      'missing-mechanic-context',
      'Theme and special-mechanic clues require the puzzle mechanic registry.',
    );
    return;
  }
  const applicable = context.mechanics.find((mechanic) =>
    mechanic.affectedEntryIds.includes(clue.entryId),
  );
  if (!clue.mechanicRef) {
    if (applicable || clue.primaryFamily === 'theme-dependent') {
      issue(
        issues,
        'missing-mechanic-reference',
        'This entry is governed by a puzzle mechanic and must reference its specification.',
      );
    }
    return;
  }
  const mechanic = context.mechanics.find(
    (item) => item.id === clue.mechanicRef?.mechanicId,
  );
  if (!mechanic) {
    issue(
      issues,
      'unknown-mechanic',
      `Mechanic ${clue.mechanicRef.mechanicId} is not declared by the puzzle.`,
    );
    return;
  }
  if (!mechanic.affectedEntryIds.includes(clue.entryId)) {
    issue(
      issues,
      'mechanic-not-applicable',
      `Mechanic ${mechanic.id} does not apply to entry ${clue.entryId}.`,
    );
  }
  if (mechanic.requiredSignal && !hasSignal(clue, mechanic.requiredSignal)) {
    issue(
      issues,
      'missing-mechanic-signal',
      `Mechanic ${mechanic.id} requires an explicit ${mechanic.requiredSignal} span.`,
    );
  }
  if (mechanic.explanationRequired && !nonEmpty(clue.mechanicRef.explanation)) {
    issue(
      issues,
      'missing-mechanic-explanation',
      `Mechanic ${mechanic.id} needs an explanation attached to its clue reference.`,
    );
  }
  if (applicable && applicable.id !== mechanic.id) {
    issue(
      issues,
      'mechanic-not-applicable',
      `Entry ${clue.entryId} belongs to ${applicable.id}, not ${mechanic.id}.`,
    );
  }
}

/** Validate one clue's declared structure against its literal text and puzzle context. */
export function validateClueGrammar(
  value: unknown,
  context: ClueGrammarContext = {},
): ClueGrammarValidation {
  const issues: ClueGrammarIssue[] = [];
  if (!isRecord(value)) {
    issue(
      issues,
      'invalid-annotation',
      'A clue-grammar annotation must be an object.',
    );
    return { valid: false, issues, semanticStatus: 'not-established' };
  }
  const clue = value as ClueGrammarAnnotation;
  if (clue.grammarVersion !== CLUE_GRAMMAR_VERSION) {
    issue(
      issues,
      'unsupported-version',
      `Expected ${CLUE_GRAMMAR_VERSION}.`,
      'grammarVersion',
    );
  }
  if (
    !nonEmpty(clue.clueId) ||
    !nonEmpty(clue.entryId) ||
    !nonEmpty(clue.clueText) ||
    !nonEmpty(clue.answer)
  ) {
    issue(
      issues,
      'invalid-annotation',
      'Clue ID, entry ID, literal clue text, and answer must be nonempty.',
    );
    return { valid: false, issues, semanticStatus: 'not-established' };
  }
  if (
    clue.answerIsAbbreviation !== undefined &&
    typeof clue.answerIsAbbreviation !== 'boolean'
  ) {
    issue(
      issues,
      'invalid-annotation',
      'answerIsAbbreviation must be a boolean.',
      'answerIsAbbreviation',
    );
    return { valid: false, issues, semanticStatus: 'not-established' };
  }
  if (!CLUE_ROLES.includes(clue.variantRole)) {
    issue(
      issues,
      'unknown-role',
      'variantRole must identify how this clue is being shown.',
    );
    return { valid: false, issues, semanticStatus: 'not-established' };
  }
  if (!CLUE_FAMILIES.includes(clue.primaryFamily)) {
    issue(
      issues,
      'unknown-family',
      'primaryFamily must identify the clue construction, independently of variantRole.',
    );
    return { valid: false, issues, semanticStatus: 'not-established' };
  }
  if (
    !Array.isArray(clue.signalSpans) ||
    !clue.signalSpans.every(isSignalSpan)
  ) {
    issue(
      issues,
      'invalid-annotation',
      'signalSpans must be an array of typed literal-text spans with valid fields.',
    );
    return { valid: false, issues, semanticStatus: 'not-established' };
  }
  if (clue.morphology !== undefined && !isMorphology(clue.morphology)) {
    issue(
      issues,
      'invalid-annotation',
      'Morphology and its evidence must use the clue-grammar-v1 schema.',
      'morphology',
    );
    return { valid: false, issues, semanticStatus: 'not-established' };
  }
  if (
    clue.interpretation !== undefined &&
    !isInterpretation(clue.interpretation)
  ) {
    issue(
      issues,
      'invalid-annotation',
      'Interpretation must contain a sense and explanation.',
      'interpretation',
    );
    return { valid: false, issues, semanticStatus: 'not-established' };
  }
  if (clue.abbreviationEvidence !== undefined) {
    const evidence = clue.abbreviationEvidence as unknown;
    if (
      !isRecord(evidence) ||
      (evidence.kind === 'indicator-span' && !nonEmpty(evidence.spanId)) ||
      (evidence.kind === 'licensed-exception' &&
        (!nonEmpty(evidence.exceptionId) ||
          typeof evidence.rationale !== 'string')) ||
      !['indicator-span', 'licensed-exception'].includes(String(evidence.kind))
    ) {
      issue(
        issues,
        'invalid-annotation',
        'abbreviationEvidence does not use the clue-grammar-v1 schema.',
        'abbreviationEvidence',
      );
      return { valid: false, issues, semanticStatus: 'not-established' };
    }
  }
  if (
    clue.mechanicRef !== undefined &&
    (!isRecord(clue.mechanicRef) ||
      !nonEmpty(clue.mechanicRef.mechanicId) ||
      typeof clue.mechanicRef.explanation !== 'string')
  ) {
    issue(
      issues,
      'invalid-annotation',
      'mechanicRef needs a mechanic ID and explanation.',
      'mechanicRef',
    );
    return { valid: false, issues, semanticStatus: 'not-established' };
  }
  if (context.enforceAnswerSafety) validateAnswerSafety(clue, issues);
  validateSpanBounds(clue, issues);
  if (CLUE_FAMILIES.includes(clue.primaryFamily)) {
    validateMorphology(clue, issues);
    validateFamilySignals(clue, context, issues);
  }
  if (context.currentEntryId && clue.entryId !== context.currentEntryId) {
    issue(
      issues,
      'invalid-annotation',
      'The annotation is attached to a different current entry.',
      'entryId',
    );
  }
  return {
    valid: issues.length === 0,
    issues,
    semanticStatus: 'not-established',
  };
}

/** Validate a batch so each clue is checked against the same current puzzle index. */
export function validateClueGrammarBatch(
  clues: readonly unknown[],
  context: ClueGrammarContext = {},
): readonly ClueGrammarValidation[] {
  return clues.map((clue) => validateClueGrammar(clue, context));
}
