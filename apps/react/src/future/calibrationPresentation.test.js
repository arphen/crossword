import { describe, expect, it } from 'vitest';
import {
  CALIBRATION_SELECTOR_VERSION_V1,
  CALIBRATION_SELECTOR_VERSION_V2,
  createCalibrationPresentation,
  deriveCalibrationSeed,
  seededShuffle,
  toCalibrationOffer,
} from './calibrationPresentation.js';

const catalogItems = [
  { id: 'thread-knot', version: 1 },
  { id: 'glass-orbit', version: 2 },
  { id: 'blue-hour', version: 4 },
  { id: 'soft-square', version: 7 },
  { id: 'number-8', version: 1 },
];

const positionBiasItems = Array.from({ length: 12 }, (_, index) => ({
  id: `candidate-${index}`,
  version: 1,
}));

function createCalibrationIds(count) {
  let state = 0x41c64e6d;
  const nextByte = () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state >>> 24;
  };

  return Array.from({ length: count }, () => {
    const bytes = Array.from({ length: 16 }, nextByte);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = bytes.map((byte) => byte.toString(16).padStart(2, '0')).join('');
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  });
}

function expectPositionBalanced(counts, sessionCount) {
  const expected = sessionCount / positionBiasItems.length;
  let chiSquare = 0;
  let largestStandardizedDeviation = 0;

  for (const candidateCounts of counts) {
    expect(candidateCounts.reduce((total, count) => total + count, 0)).toBe(sessionCount);
    for (const observed of candidateCounts) {
      chiSquare += ((observed - expected) ** 2) / expected;
      largestStandardizedDeviation = Math.max(
        largestStandardizedDeviation,
        Math.abs(observed - expected) / Math.sqrt(expected),
      );
    }
  }

  // 144 item/position cells should fluctuate around this distribution. These
  // fixed-seed, deliberately wide limits catch structural slot bias without
  // making the suite depend on ambient randomness or a fragile exact count.
  expect(chiSquare).toBeLessThan(210);
  expect(largestStandardizedDeviation).toBeLessThan(4.5);
}

describe('calibration presentation', () => {
  it('derives a stable unsigned seed from a calibration UUID', () => {
    const seed = deriveCalibrationSeed('8de29432-833e-4a03-a861-387435567048');

    expect(seed).toBe(deriveCalibrationSeed('8de29432-833e-4a03-a861-387435567048'));
    expect(seed).toBeGreaterThanOrEqual(0);
    expect(seed).toBeLessThanOrEqual(0xffffffff);
    expect(deriveCalibrationSeed('8DE29432-833E-4A03-A861-387435567048')).toBe(seed);
    expect(() => deriveCalibrationSeed('not-a-uuid')).toThrow(/UUID/);
  });

  it('reproduces the same order for the same seed without changing the source', () => {
    const source = [...catalogItems];

    expect(seededShuffle(catalogItems, 0xdeadbeef)).toEqual(
      seededShuffle(catalogItems, 0xdeadbeef),
    );
    expect(catalogItems).toEqual(source);
  });

  it('keeps selector-v1 replay output fixed and versions unbiased selector-v2', () => {
    const legacyOrder = [
      'candidate-8', 'candidate-3', 'candidate-4', 'candidate-0',
      'candidate-6', 'candidate-11', 'candidate-5', 'candidate-7',
      'candidate-2', 'candidate-9', 'candidate-10', 'candidate-1',
    ];
    const unbiasedOrder = [
      'candidate-11', 'candidate-1', 'candidate-9', 'candidate-4',
      'candidate-7', 'candidate-6', 'candidate-8', 'candidate-3',
      'candidate-0', 'candidate-5', 'candidate-2', 'candidate-10',
    ];

    expect(seededShuffle(positionBiasItems, 0x12345678).map(({ id }) => id)).toEqual(
      legacyOrder,
    );
    expect(
      seededShuffle(positionBiasItems, 0x12345678, CALIBRATION_SELECTOR_VERSION_V1)
        .map(({ id }) => id),
    ).toEqual(legacyOrder);
    expect(
      seededShuffle(positionBiasItems, 0x12345678, CALIBRATION_SELECTOR_VERSION_V2)
        .map(({ id }) => id),
    ).toEqual(unbiasedOrder);
    const v2Presentation = createCalibrationPresentation(
      positionBiasItems,
      0x12345678,
      CALIBRATION_SELECTOR_VERSION_V2,
    );
    expect(v2Presentation.shownItems.map(({ id }) => id)).toEqual(unbiasedOrder);
    expect(v2Presentation.offered.map(({ stimulusId }) => stimulusId)).toEqual(unbiasedOrder);
    expect(() => seededShuffle(positionBiasItems, 4, 'selector-v3')).toThrow(/version/);
  });

  it('balances each candidate across offer positions over calibration UUIDs and movements', () => {
    const sessionCount = 6000;
    const movementCount = 6;
    const calibrationIds = createCalibrationIds(sessionCount);

    for (const selectorVersion of [
      CALIBRATION_SELECTOR_VERSION_V1,
      CALIBRATION_SELECTOR_VERSION_V2,
    ]) {
      const countsByMovement = Array.from({ length: movementCount }, () =>
        Array.from({ length: positionBiasItems.length }, () =>
          Array(positionBiasItems.length).fill(0),
        ),
      );

      for (const calibrationId of calibrationIds) {
        const calibrationSeed = deriveCalibrationSeed(calibrationId);
        for (let movement = 0; movement < movementCount; movement += 1) {
          const movementSeed =
            (calibrationSeed + Math.imul(movement, 0x9e3779b9)) >>> 0;
          seededShuffle(positionBiasItems, movementSeed, selectorVersion).forEach(
            ({ id }, position) => {
              const candidateIndex = Number(id.slice('candidate-'.length));
              countsByMovement[movement][candidateIndex][position] += 1;
            },
          );
        }
      }

      countsByMovement.forEach((counts) => expectPositionBalanced(counts, sessionCount));
    }
  });

  it('produces a different ordering for different seeds', () => {
    expect(seededShuffle(catalogItems, 17)).not.toEqual(
      seededShuffle(catalogItems, 18),
    );
  });

  it('retains every item exactly once in the deterministic order', () => {
    const shuffled = seededShuffle(catalogItems, 987654321);

    expect(shuffled).toHaveLength(catalogItems.length);
    expect(shuffled.map(({ id }) => id).sort()).toEqual(
      catalogItems.map(({ id }) => id).sort(),
    );
    expect(new Set(shuffled.map(({ id }) => id)).size).toBe(catalogItems.length);
  });

  it('records the exact shown order, stable versions, and zero-based positions', () => {
    const { shownItems, offered } = createCalibrationPresentation(
      catalogItems,
      0x12345678,
    );

    expect(offered).toEqual(
      shownItems.map(({ id, version }, position) => ({
        stimulusId: id,
        stimulusVersion: String(version),
        position,
      })),
    );
    expect(offered.map(({ position }) => position)).toEqual([0, 1, 2, 3, 4]);
    expect(createCalibrationPresentation(catalogItems, 0x12345678)).toEqual({
      shownItems,
      offered,
    });
  });

  it('rejects malformed seeds and non-unique or unversioned offers', () => {
    expect(() => seededShuffle(catalogItems, -1)).toThrow(/unsigned 32-bit/);
    expect(() => toCalibrationOffer([{ id: 'same', version: 1 }, { id: 'same', version: 1 }])).toThrow(
      /cannot repeat/,
    );
    expect(() => toCalibrationOffer([{ id: 'missing-version' }])).toThrow(/stable id and version/);
  });
});
