// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import {
  catalog,
  createProfileId,
  changeObject,
  freshDraft,
  readDraft,
  seedProfile,
  validateDraft,
  writeDraft,
  STORAGE_KEY,
} from './episteme';

describe('a provisional episteme', () => {
  it('creates a UUID capability on local HTTP without randomUUID', () => {
    const id = createProfileId({
      getRandomValues: (bytes) => crypto.getRandomValues(bytes),
    });
    expect(id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
  });
  it('retains explicit choices without inventing knowledge', () => {
    const draft = {
      ...freshDraft(),
      object: 'thread',
      companion: 'fork',
      traces: ['echo'],
      excluded: ['tension'],
      weekday: 'thursday',
    };
    expect(validateDraft(draft)).toBe(true);
    const profile = seedProfile(draft);
    expect(profile.associations).toContain('resonance');
    expect(profile.associations).not.toContain('tension');
    expect(profile.knowledge).toEqual({});
    expect(profile.weekday).toBe('thursday');
    expect(profile.provisional).toBe(true);
  });
  it('clears dependent choices when the first object changes', () => {
    const draft = {
      ...freshDraft(),
      object: 'thread',
      companion: 'fork',
      excluded: ['echo'],
      reflection: { model: 'test', words: ['music'] },
    };
    expect(changeObject(draft, 'cube')).toMatchObject({
      object: 'cube',
      companion: null,
      excluded: [],
      reflection: null,
    });
    expect(changeObject(draft, 'thread').companion).toBe('fork');
  });
  it('supports every authored branch and rejects a companion from another branch', () => {
    for (const object of catalog.objects)
      for (const companion of object.companions)
        expect(
          validateDraft({ ...freshDraft(), object: object.id, companion }),
        ).toBe(true);
    expect(
      validateDraft({ ...freshDraft(), object: 'thread', companion: 'shell' }),
    ).toBe(false);
  });
  it('restores drafts and handles unavailable or malformed browser storage', () => {
    const draft = { ...freshDraft(), step: 3, traces: ['echo', '?'] };
    expect(writeDraft(draft)).toBe(true);
    expect(readDraft()).toEqual(draft);
    localStorage.setItem(STORAGE_KEY, '{broken');
    expect(readDraft().step).toBe(0);
    const blocked = {
      getItem() {
        throw new Error('blocked');
      },
      setItem() {
        throw new Error('full');
      },
    };
    expect(readDraft(blocked).complete).toBe(false);
    expect(writeDraft(draft, blocked)).toBe(false);
  });
  it('keeps the skipped profile empty and model proposals separate from observations', () => {
    expect(seedProfile(freshDraft()).associations).toEqual([]);
    const profile = seedProfile({
      ...freshDraft(),
      reflection: { model: 'test', words: ['resonance'] },
    });
    expect(profile.associations).toEqual(['resonance']);
    expect(profile.observations).toEqual([]);
    expect(profile.knowledge).toEqual({});
  });
});
