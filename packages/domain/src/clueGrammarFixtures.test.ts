import { describe, expect, it } from 'vitest';
import {
  CLUE_GRAMMAR_FIXTURES,
  CLUE_GRAMMAR_FIXTURE_COUNTS,
  type ClueGrammarFixture,
} from './clueGrammarFixtures';
import { validateClueGrammar } from './clueGrammar';

function groupedByFamily(fixtures: readonly ClueGrammarFixture[]) {
  return fixtures.reduce((groups, fixture) => {
    const existing = groups.get(fixture.family) ?? [];
    existing.push(fixture);
    groups.set(fixture.family, existing);
    return groups;
  }, new Map<ClueGrammarFixture['family'], ClueGrammarFixture[]>());
}

describe('original clue-grammar-v1 fixture matrix', () => {
  it('keeps ten accepted and ten rejected fixtures for every family', () => {
    const groups = groupedByFamily(CLUE_GRAMMAR_FIXTURES);
    expect(groups.size).toBe(10);
    for (const [family, fixtures] of groups) {
      expect(fixtures.filter((fixture) => fixture.valid), family).toHaveLength(10);
      expect(fixtures.filter((fixture) => !fixture.valid), family).toHaveLength(10);
      expect(CLUE_GRAMMAR_FIXTURE_COUNTS[family], family).toEqual({
        total: 20,
        valid: 10,
        invalid: 10,
      });
    }
    expect(CLUE_GRAMMAR_FIXTURES).toHaveLength(200);
  });

  it('accepts every positive fixture and keeps semantic truth explicitly open', () => {
    for (const fixture of CLUE_GRAMMAR_FIXTURES.filter((item) => item.valid)) {
      const result = validateClueGrammar(fixture.annotation, fixture.context);
      expect(result.valid, fixture.id).toBe(true);
      expect(result.issues, fixture.id).toEqual([]);
      expect(result.semanticStatus, fixture.id).toBe('not-established');
      expect(fixture.intendedReading.length, fixture.id).toBeGreaterThan(0);
      expect(fixture.defectOrReason.length, fixture.id).toBeGreaterThan(0);
      expect(fixture.repair.length, fixture.id).toBeGreaterThan(0);
    }
  });

  it('rejects every negative fixture with its declared structural defect', () => {
    for (const fixture of CLUE_GRAMMAR_FIXTURES.filter((item) => !item.valid)) {
      const result = validateClueGrammar(fixture.annotation, fixture.context);
      const actualCodes = new Set(result.issues.map((issue) => issue.code));
      expect(result.valid, fixture.id).toBe(false);
      for (const expectedCode of fixture.expectedIssues) {
        expect(actualCodes, fixture.id).toContain(expectedCode);
      }
      expect(fixture.expectedIssues.length, fixture.id).toBeGreaterThan(0);
      expect(result.semanticStatus, fixture.id).toBe('not-established');
      expect(fixture.intendedReading.length, fixture.id).toBeGreaterThan(0);
      expect(fixture.defectOrReason.length, fixture.id).toBeGreaterThan(0);
      expect(fixture.repair.length, fixture.id).toBeGreaterThan(0);
    }
  });

  it('preserves family-specific boundaries instead of treating punctuation as semantics', () => {
    const punWithoutQuestion = CLUE_GRAMMAR_FIXTURES.find(
      (fixture) => fixture.id === 'pun-valid-quiet',
    );
    const factualQuestion = CLUE_GRAMMAR_FIXTURES.find(
      (fixture) => fixture.id === 'factual-invalid-question',
    );
    expect(punWithoutQuestion).toBeDefined();
    expect(factualQuestion).toBeDefined();
    expect(validateClueGrammar(punWithoutQuestion!.annotation).valid).toBe(true);
    expect(
      validateClueGrammar(factualQuestion!.annotation).issues.map(
        (issue) => issue.code,
      ),
    ).toContain('unexplained-question-mark');
  });
});
