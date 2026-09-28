/**
 * Future-only language input policy.
 *
 * The construction runtime currently emits ordinary ASCII cells.  A language
 * pack therefore has two deliberately separate representations:
 *
 *   display: what a player typed, normalised to a stable NFC/uppercase form;
 *   fill:    the token that an ordinary one-letter cell can compare with.
 *
 * `fill` mappings are explicit per language.  We never strip accents or apply
 * an English fallback merely because a language was not recognised.  Unknown
 * packs remain disabled and return a reason that callers can record.
 */

export const LANGUAGE_INPUT_PACK_VERSION = 'language-input-pack-v1';
export const LANGUAGE_TOKEN_METADATA_VERSION = 'language-token-metadata-v1';

const DISPLAY_MAPS = Object.freeze({
  de: Object.freeze({
    ä: 'Ä',
    ö: 'Ö',
    ü: 'Ü',
    ß: 'ß',
    ẞ: 'ẞ',
  }),
  fr: Object.freeze({
    à: 'À',
    â: 'Â',
    æ: 'Æ',
    ç: 'Ç',
    é: 'É',
    è: 'È',
    ê: 'Ê',
    ë: 'Ë',
    î: 'Î',
    ï: 'Ï',
    ô: 'Ô',
    œ: 'Œ',
    ù: 'Ù',
    û: 'Û',
    ü: 'Ü',
    ÿ: 'Ÿ',
  }),
  es: Object.freeze({
    á: 'Á',
    é: 'É',
    í: 'Í',
    ó: 'Ó',
    ú: 'Ú',
    ü: 'Ü',
    ñ: 'Ñ',
  }),
  it: Object.freeze({
    à: 'À',
    è: 'È',
    é: 'É',
    ì: 'Ì',
    ò: 'Ò',
    ù: 'Ù',
  }),
  pt: Object.freeze({
    á: 'Á',
    â: 'Â',
    ã: 'Ã',
    à: 'À',
    ç: 'Ç',
    é: 'É',
    ê: 'Ê',
    í: 'Í',
    ó: 'Ó',
    ô: 'Ô',
    õ: 'Õ',
    ú: 'Ú',
    ü: 'Ü',
  }),
  nl: Object.freeze({
    á: 'Á',
    é: 'É',
    ë: 'Ë',
    ï: 'Ï',
    ó: 'Ó',
    ö: 'Ö',
    ü: 'Ü',
  }),
});

// Longest aliases are matched first.  They are intentionally explicit rather
// than generated from a generic accent-stripping rule.
const FILL_ALIASES = Object.freeze({
  de: Object.freeze([
    ['ẞ', 'SS'],
    ['ß', 'SS'],
    ['Ä', 'AE'],
    ['Ö', 'OE'],
    ['Ü', 'UE'],
  ]),
  fr: Object.freeze([
    ['Œ', 'OE'],
    ['Æ', 'AE'],
    ['À', 'A'],
    ['Â', 'A'],
    ['Ç', 'C'],
    ['É', 'E'],
    ['È', 'E'],
    ['Ê', 'E'],
    ['Ë', 'E'],
    ['Î', 'I'],
    ['Ï', 'I'],
    ['Ô', 'O'],
    ['Ù', 'U'],
    ['Û', 'U'],
    ['Ü', 'U'],
    ['Ÿ', 'Y'],
  ]),
  es: Object.freeze([
    ['Á', 'A'],
    ['É', 'E'],
    ['Í', 'I'],
    ['Ó', 'O'],
    ['Ú', 'U'],
    ['Ü', 'U'],
    ['Ñ', 'N'],
  ]),
  it: Object.freeze([
    ['À', 'A'],
    ['È', 'E'],
    ['É', 'E'],
    ['Ì', 'I'],
    ['Ò', 'O'],
    ['Ù', 'U'],
  ]),
  pt: Object.freeze([
    ['Á', 'A'],
    ['Â', 'A'],
    ['Ã', 'A'],
    ['À', 'A'],
    ['Ç', 'C'],
    ['É', 'E'],
    ['Ê', 'E'],
    ['Í', 'I'],
    ['Ó', 'O'],
    ['Ô', 'O'],
    ['Õ', 'O'],
    ['Ú', 'U'],
    ['Ü', 'U'],
  ]),
  nl: Object.freeze([
    ['Á', 'A'],
    ['É', 'E'],
    ['Ë', 'E'],
    ['Ï', 'I'],
    ['Ó', 'O'],
    ['Ö', 'O'],
    ['Ü', 'U'],
  ]),
});

const LANGUAGE_ALIASES = Object.freeze({
  de: 'de',
  'de-de': 'de',
  german: 'de',
  deutsch: 'de',
  fr: 'fr',
  'fr-fr': 'fr',
  french: 'fr',
  français: 'fr',
  es: 'es',
  'es-es': 'es',
  spanish: 'es',
  español: 'es',
  it: 'it',
  'it-it': 'it',
  italian: 'it',
  italiano: 'it',
  pt: 'pt',
  'pt-pt': 'pt',
  portuguese: 'pt',
  português: 'pt',
  nl: 'nl',
  'nl-nl': 'nl',
  dutch: 'nl',
  nederlands: 'nl',
});

const LANGUAGE_PACKS = Object.freeze(
  Object.fromEntries(
    Object.keys(DISPLAY_MAPS).map((code) => [
      code,
      Object.freeze({
        code,
        version: LANGUAGE_INPUT_PACK_VERSION,
        locale:
          code === 'de'
            ? 'de-DE'
            : code === 'fr'
              ? 'fr-FR'
              : code === 'es'
                ? 'es-ES'
              : code === 'it'
                ? 'it-IT'
                : code === 'pt'
                  ? 'pt-PT'
                  : 'nl-NL',
        displayMap: DISPLAY_MAPS[code],
        fillAliases: FILL_ALIASES[code],
      }),
    ]),
  ),
);

function text(value) {
  return typeof value === 'string' ? value.normalize('NFC') : '';
}

function canonicalLanguage(language) {
  if (typeof language !== 'string') return null;
  const key = language.trim().toLocaleLowerCase('en-US');
  return LANGUAGE_ALIASES[key] ?? null;
}

/** Return a supported explicit pack, or null for no/unknown language. */
export function resolveLanguagePack(language) {
  const code = canonicalLanguage(language);
  return code ? LANGUAGE_PACKS[code] : null;
}

function displayCharacter(character, pack) {
  if (pack.displayMap[character]) return pack.displayMap[character];
  const uppercase = character.toLocaleUpperCase(pack.locale);
  if (pack.displayMap[uppercase] || Object.values(pack.displayMap).includes(uppercase)) {
    return uppercase;
  }
  // Packs are responsible for deciding that ASCII letters are valid.  This is
  // not a fallback for unknown languages because the caller must have a pack.
  if (/^[a-z]$/u.test(character)) return character.toUpperCase();
  if (/^[A-Z]$/u.test(character)) return character;
  return character;
}

function displayText(value, pack) {
  const normalized = text(value);
  let result = '';
  for (const character of normalized) {
    result += displayCharacter(character, pack);
  }
  return result;
}

function fillText(value, pack) {
  const displayed = displayText(value, pack);
  let result = '';
  let cursor = 0;
  while (cursor < displayed.length) {
    const alias = pack.fillAliases.find(([source]) =>
      displayed.startsWith(source, cursor),
    );
    if (alias) {
      result += alias[1];
      cursor += alias[0].length;
      continue;
    }
    const character = displayed[cursor];
    if (/^[A-Z]$/u.test(character)) {
      result += character;
      cursor += 1;
      continue;
    }
    // Spaces and punctuation are not fill tokens.  Keeping them rejected is
    // safer than silently importing English crossword assumptions.
    return { value: result, rejected: character };
  }
  return { value: result, rejected: null };
}

function rejectedResult(raw, reason, pack = null, display = undefined) {
  return {
    accepted: false,
    raw: typeof raw === 'string' ? raw : '',
    display:
      display ?? (typeof raw === 'string' ? raw.normalize('NFC') : ''),
    fill: null,
    language: pack?.code ?? null,
    packVersion: pack?.version ?? null,
    metadata: null,
    reason,
  };
}

function tokenMetadata(display, fill, pack) {
  const displayUnits = [...display];
  const fillUnits = [...fill];
  return {
    version: LANGUAGE_TOKEN_METADATA_VERSION,
    language: pack.code,
    packVersion: pack.version,
    displayUnits,
    fillUnits,
    displayUnitCount: displayUnits.length,
    fillUnitCount: fillUnits.length,
    aliasApplied: display !== fill,
    multiCharacter: fillUnits.length > 1,
  };
}

/** @typedef {{language?: string | null, allowMultiCharacter?: boolean}} LanguageTokenOptions */

/**
 * Normalise a player's token for display and fill comparison.
 *
 * A one-letter cell rejects a mapping such as German ß→SS or French Œ→OE;
 * callers must opt into `allowMultiCharacter` for rebus/multi-token cells.
 * @param {unknown} raw
 * @param {LanguageTokenOptions} options
 */
export function normalizeLanguageToken(raw, options = {}) {
  const { language, allowMultiCharacter = false } = options;
  const pack = resolveLanguagePack(language);
  if (!pack) {
    return rejectedResult(
      raw,
      language ? 'unsupported-language-pack' : 'no-language-pack',
    );
  }
  const normalized = text(raw);
  if (!normalized) return rejectedResult(raw, 'empty-token', pack);
  const display = displayText(normalized, pack);
  const filled = fillText(display, pack);
  if (filled.rejected) {
    return rejectedResult(raw, 'unsupported-token', pack, display);
  }
  if (!allowMultiCharacter && [...filled.value].length !== 1) {
    return rejectedResult(raw, 'multi-character-token', pack, display);
  }
  return {
    accepted: true,
    raw,
    display,
    fill: filled.value,
    language: pack.code,
    packVersion: pack.version,
    metadata: tokenMetadata(display, filled.value, pack),
    reason: null,
  };
}

/**
 * Return the stable, answer-free token description used by future UI and
 * journal adapters. The fill remains the only value written into the legacy
 * grid; display units preserve what the player entered for a later token-aware
 * renderer. Multi-character aliases are deliberately allowed here so a rebus
 * cell can accept them without loosening ordinary one-cell input.
 */
export function describeLanguageToken(raw, options = {}) {
  return normalizeLanguageToken(raw, {
    ...options,
    allowMultiCharacter: true,
  });
}

/**
 * Normalize a value for a deliberately multi-token/rebus cell. Keeping this
 * helper in the future adapter makes the boundary explicit and leaves the
 * shared daily solver untouched.
 */
export function normalizeLanguageRebusValue(raw, language) {
  return normalizeLanguageToken(raw, {
    language,
    allowMultiCharacter: true,
  });
}

export function normalizeDisplayToken(raw, language) {
  const pack = resolveLanguagePack(language);
  return pack ? displayText(raw, pack) : typeof raw === 'string' ? text(raw) : '';
}

/** @param {LanguageTokenOptions} options */
export function normalizeFillToken(raw, language, options = {}) {
  return normalizeLanguageToken(raw, { language, ...options });
}

/**
 * Create the small adapter consumed by the future solver.  Returning a
 * disabled adapter for an unrecognised language lets the UI preserve the raw
 * value while exposing an explicit reason to event/journal callers.
 */
export function createLanguageInputPolicy(language) {
  const pack = resolveLanguagePack(language);
  return Object.freeze({
    enabled: Boolean(pack),
    language: pack?.code ?? (typeof language === 'string' ? language : null),
    packVersion: pack?.version ?? null,
    normalizeDisplay(value) {
      return normalizeDisplayToken(value, language);
    },
    /** @param {LanguageTokenOptions} options */
    normalize(value, options = {}) {
      return normalizeLanguageToken(value, { language, ...options });
    },
    normalizeRebus(value) {
      return normalizeLanguageRebusValue(value, language);
    },
    describe(value) {
      return describeLanguageToken(value, { language });
    },
    normalizeForCell(value, { isRebus = false } = {}) {
      return normalizeLanguageToken(value, {
        language,
        allowMultiCharacter: isRebus,
      });
    },
  });
}

/**
 * Return the canonical token for a non-ASCII key that the future solver may
 * handle itself. Ordinary ASCII and rebus keys deliberately return null so
 * the existing controller/context-menu behavior remains authoritative.
 */
export function normalizeFutureKey(
  policy,
  key,
  {
    isRebus = false,
    ctrlKey = false,
    metaKey = false,
    altKey = false,
  } = {},
) {
  if (
    !policy?.enabled ||
    isRebus ||
    ctrlKey ||
    metaKey ||
    altKey ||
    typeof key !== 'string' ||
    key.length === 0 ||
    key.startsWith('Arrow')
  ) {
    return null;
  }
  const normalized = policy.normalizeForCell(key, { isRebus: false });
  if (
    !normalized.accepted ||
    normalized.fill.length !== 1 ||
    normalized.fill === key.toUpperCase()
  ) {
    return null;
  }
  return normalized;
}

export const supportedLanguageInputPacks = Object.freeze(
  Object.values(LANGUAGE_PACKS).map((pack) => ({
    code: pack.code,
    locale: pack.locale,
    version: pack.version,
  })),
);
