import { describe, expect, it } from 'vitest';
import { frameDue, loopNeeded, nextRenderScale } from './scheduler';

const options = { ambientFps: 30, ambientFor: 90 };

describe('when the glass draws', () => {
  it('draws every frame while an event animates', () => {
    const state = { animateUntil: 10, lastFrame: 9.99, lastInput: 0, ambient: false };
    expect(frameDue(9.995, state, options)).toBe(true);
  });

  it('breathes at most thirty times a second between events', () => {
    const state = { animateUntil: 0, lastFrame: 10, lastInput: 9, ambient: true };
    expect(frameDue(10.01, state, options)).toBe(false);
    expect(frameDue(10.034, state, options)).toBe(true);
  });

  it('stops altogether once the reader has been away, or asks for stillness', () => {
    expect(frameDue(200, { animateUntil: 0, lastFrame: 0, lastInput: 0, ambient: true }, options)).toBe(false);
    expect(loopNeeded(200, { animateUntil: 0, lastInput: 0, ambient: true }, options)).toBe(false);
    expect(loopNeeded(5, { animateUntil: 0, lastInput: 0, ambient: false }, options)).toBe(false);
    expect(loopNeeded(5, { animateUntil: 6, lastInput: 0, ambient: false }, options)).toBe(true);
  });
});

describe('dynamic resolution', () => {
  it('steps down quickly over budget and never below the floor', () => {
    expect(nextRenderScale(1, 9, 4, 0).scale).toBe(0.9);
    expect(nextRenderScale(0.5, 9, 4, 0).scale).toBe(0.5);
  });

  it('creeps back up only after a calm stretch', () => {
    let state = { scale: 0.8, calmFrames: 0 };
    for (let i = 0; i < 5; i += 1) state = nextRenderScale(state.scale, 1, 4, state.calmFrames, { min: 0.5, max: 1, calmNeeded: 6 });
    expect(state.scale).toBe(0.8);
    state = nextRenderScale(state.scale, 1, 4, state.calmFrames, { min: 0.5, max: 1, calmNeeded: 6 });
    expect(state.scale).toBe(0.85);
    // A frame near budget resets the calm count.
    expect(nextRenderScale(0.85, 3.5, 4, 4).calmFrames).toBe(0);
  });
});
