import { describe, expect, it } from 'vitest';
import {
  createLanguageInputPolicy,
  describeLanguageToken,
  normalizeDisplayToken,
  normalizeFillToken,
  normalizeLanguageToken,
  normalizeLanguageRebusValue,
  normalizeFutureKey,
  resolveLanguagePack,
  supportedLanguageInputPacks,
} from './languageInput';

describe('future language input packs', () => {
  it('resolves explicit German, French, Spanish, Italian, Portuguese, and Dutch packs', () => {
    expect(resolveLanguagePack('German')?.code).toBe('de');
    expect(resolveLanguagePack('de-DE')?.code).toBe('de');
    expect(resolveLanguagePack('français')?.code).toBe('fr');
    expect(resolveLanguagePack('Spanish')?.code).toBe('es');
    expect(resolveLanguagePack('Dutch')?.code).toBe('nl');
    expect(resolveLanguagePack('Nederlands')?.code).toBe('nl');
    expect(resolveLanguagePack('en')).toBeNull();
    expect(supportedLanguageInputPacks.map((pack) => pack.code)).toEqual([
      'de',
      'fr',
      'es',
      'it',
      'pt',
      'nl',
    ]);
  });

  it('normalises combining accents for display and explicit fill comparison', () => {
    expect(normalizeDisplayToken('e\u0301', 'fr')).toBe('É');
    expect(normalizeFillToken('e\u0301', 'fr')).toMatchObject({
      accepted: true,
      display: 'É',
      fill: 'E',
      language: 'fr',
    });
    expect(normalizeFillToken('Ä', 'de')).toMatchObject({
      accepted: false,
      display: 'Ä',
      fill: null,
      reason: 'multi-character-token',
    });
    expect(normalizeFillToken('ñ', 'Spanish')).toMatchObject({
      accepted: true,
      display: 'Ñ',
      fill: 'N',
      language: 'es',
    });
    expect(normalizeFillToken('ç', 'Portuguese')).toMatchObject({
      accepted: true,
      display: 'Ç',
      fill: 'C',
      language: 'pt',
    });
    expect(normalizeFillToken('ë', 'Dutch')).toMatchObject({
      accepted: true,
      display: 'Ë',
      fill: 'E',
      language: 'nl',
    });
  });

  it('keeps multi-character aliases explicit and opt-in', () => {
    expect(normalizeLanguageToken('ß', { language: 'de' })).toMatchObject({
      accepted: false,
      reason: 'multi-character-token',
    });
    expect(
      normalizeLanguageToken('ß', {
        language: 'de',
        allowMultiCharacter: true,
      }),
    ).toMatchObject({
      accepted: true,
      display: 'ß',
      fill: 'SS',
    });
    expect(
      normalizeLanguageToken('œ', {
        language: 'fr',
        allowMultiCharacter: true,
      }),
    ).toMatchObject({
      accepted: true,
      display: 'Œ',
      fill: 'OE',
    });
    expect(
      normalizeLanguageToken('Ü', {
        language: 'de',
        allowMultiCharacter: true,
      }),
    ).toMatchObject({
      accepted: true,
      display: 'Ü',
      fill: 'UE',
    });
  });

  it('exposes answer-free token metadata for multi-character aliases', () => {
    expect(describeLanguageToken('ß', { language: 'de' })).toMatchObject({
      accepted: true,
      display: 'ß',
      fill: 'SS',
      metadata: {
        version: 'language-token-metadata-v1',
        language: 'de',
        displayUnits: ['ß'],
        fillUnits: ['S', 'S'],
        displayUnitCount: 1,
        fillUnitCount: 2,
        aliasApplied: true,
        multiCharacter: true,
      },
    });
    expect(normalizeLanguageRebusValue('œ', 'fr')).toMatchObject({
      accepted: true,
      display: 'Œ',
      fill: 'OE',
    });
  });

  it('does not silently apply English or accent-stripping rules to unknown packs', () => {
    expect(normalizeLanguageToken('é', { language: 'Japanese' })).toMatchObject({
      accepted: false,
      reason: 'unsupported-language-pack',
      fill: null,
    });
    expect(normalizeLanguageToken('!', { language: 'fr' })).toMatchObject({
      accepted: false,
      reason: 'unsupported-token',
    });
  });

  it('exposes a stable adapter for future UI code', () => {
    const policy = createLanguageInputPolicy('German');
    expect(policy.enabled).toBe(true);
    expect(policy.normalizeForCell('ü')).toMatchObject({
      accepted: false,
      display: 'Ü',
      fill: null,
      reason: 'multi-character-token',
    });
    expect(policy.describe('ß').metadata).toMatchObject({
      fillUnits: ['S', 'S'],
      multiCharacter: true,
    });
    expect(policy.normalizeRebus('ß')).toMatchObject({
      accepted: true,
      fill: 'SS',
    });
    expect(createLanguageInputPolicy('Spanish').enabled).toBe(true);
  });

  it('only hands non-ASCII single-cell keys to the future solver hook', () => {
    const policy = createLanguageInputPolicy('French');
    expect(normalizeFutureKey(policy, 'é')).toMatchObject({
      accepted: true,
      fill: 'E',
    });
    expect(normalizeFutureKey(policy, 'a')).toBeNull();
    expect(normalizeFutureKey(policy, 'é', { isRebus: true })).toBeNull();
    expect(normalizeFutureKey(policy, 'é', { ctrlKey: true })).toBeNull();
    expect(normalizeFutureKey(createLanguageInputPolicy('Spanish'), 'ñ')).toMatchObject({
      accepted: true,
      fill: 'N',
    });
  });
});
