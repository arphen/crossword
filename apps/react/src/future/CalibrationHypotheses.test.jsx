// @vitest-environment jsdom
import React, { act } from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { createRoot } from 'react-dom/client';
import CalibrationHypotheses from './CalibrationHypotheses';

const deck = {
  deckId: 'deck-1',
  items: [
    {
      proposalId: 'path-1',
      phrase: 'An echo might open a door.',
      relation: 'Echo / reply',
      connection: 'The word echo and the image of an open doorway appeared nearby.',
      ambiguity: 'The overlap may be incidental; there is no single reading.',
      sourceObservationIds: ['observation-1'],
    },
    {
      proposalId: 'path-2',
      phrase: 'A small map can leave room for detours.',
      relation: 'Map / wandering',
      connection: 'The map was selected beside a trace about elsewhere.',
      ambiguity: 'This is only one possible association.',
      sourceObservationIds: ['observation-2'],
    },
    {
      proposalId: 'path-3',
      phrase: 'A number can work like a quiet marker.',
      relation: 'Number / mark',
      connection: 'A time and a typographic sign were both kept.',
      ambiguity: 'A shared shape does not establish a shared meaning.',
      sourceObservationIds: ['observation-3'],
    },
  ],
};

let host;
let root;

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
});

async function mount(props, { onSubmit } = {}) {
  host = document.createElement('div');
  host.className = 'future-root';
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root.render(
      onSubmit ? (
        <form onSubmit={onSubmit}>
          <CalibrationHypotheses {...props} />
        </form>
      ) : (
        <CalibrationHypotheses {...props} />
      ),
    );
  });
}

async function click(button) {
  await act(async () => {
    button.click();
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function keyboardActivate(button, key = 'Enter') {
  await act(async () => {
    button.focus();
    button.dispatchEvent(
      new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }),
    );
    if (key === ' ') {
      button.dispatchEvent(
        new KeyboardEvent('keyup', { key, bubbles: true, cancelable: true }),
      );
    }
    // jsdom does not synthesize a native button activation from keyboard input.
    button.click();
    await Promise.resolve();
  });
}

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  host?.remove();
  root = undefined;
  host = undefined;
  vi.unstubAllGlobals();
});

it('introduces tentative word paths with labelled relation, connection, and uncertainty', async () => {
  await mount({
    deck,
    responses: {},
    busyProposalId: null,
    onRespond: vi.fn(),
    onAction: vi.fn(),
  });

  const region = host.querySelector('.future-hypotheses');
  expect(region.getAttribute('aria-labelledby')).toBe(
    'future-hypotheses-title',
  );
  expect(host.querySelector('#future-hypotheses-title').textContent).toBe(
    'Possible word paths.',
  );
  expect(region.textContent).toContain(
    'You decide whether they lead anywhere.',
  );
  expect(host.querySelectorAll('.future-hypothesis-card')).toHaveLength(3);
  expect(host.querySelectorAll('.future-hypothesis-card')[0].textContent).toContain(
    'Echo / reply',
  );
  expect(host.querySelectorAll('.future-hypothesis-card')[0].textContent).toContain(
    'The overlap may be incidental; there is no single reading.',
  );
  expect(host.querySelector('[role="group"][aria-label="Respond to possible path 1"]')).not.toBeNull();
  expect(region.textContent).not.toMatch(/you are|your desire|you secretly/i);
});

it('forwards keep, not-for-me, and pass as distinct non-submitting button actions', async () => {
  const onRespond = vi.fn();
  const onSubmit = vi.fn((event) => event.preventDefault());
  await mount(
    {
      deck,
      responses: {},
      busyProposalId: null,
      onRespond,
      onAction: vi.fn(),
    },
    { onSubmit },
  );

  const keep = host.querySelector('.future-hypothesis-choice-keep');
  await keyboardActivate(keep, 'Enter');
  expect(document.activeElement).toBe(keep);
  expect(keep.type).toBe('button');
  expect(onRespond).toHaveBeenCalledWith('path-1', 'keep');
  await click(host.querySelector('.future-hypothesis-choice-not-for-me'));
  await click(host.querySelector('.future-hypothesis-choice-pass'));
  expect(onRespond.mock.calls).toEqual([
    ['path-1', 'keep'],
    ['path-1', 'not-for-me'],
    ['path-1', 'pass'],
  ]);
  expect(onSubmit).not.toHaveBeenCalled();
});

it('maps a touch swipe to a reversible calibration response', async () => {
  const onRespond = vi.fn();
  await mount({
    deck,
    responses: {},
    busyProposalId: null,
    onRespond,
    onAction: vi.fn(),
  });
  const card = host.querySelector('.future-hypothesis-card');
  const down = new Event('pointerdown', { bubbles: true });
  Object.defineProperties(down, {
    pointerId: { value: 9 },
    pointerType: { value: 'touch' },
    clientX: { value: 100 },
  });
  const up = new Event('pointerup', { bubbles: true });
  Object.defineProperties(up, {
    pointerId: { value: 9 },
    pointerType: { value: 'touch' },
    clientX: { value: 10 },
  });
  await act(async () => {
    card.dispatchEvent(down);
    card.dispatchEvent(up);
    await Promise.resolve();
  });
  expect(onRespond).toHaveBeenCalledWith('path-1', 'not-for-me');
});

it('shows reversible saved state and calls retract and restore with the response identity', async () => {
  const onAction = vi.fn(async () => {});
  await mount({
    deck,
    responses: {
      'path-1': { response: 'keep', responseId: 'response-17' },
    },
    busyProposalId: null,
    onRespond: vi.fn(),
    onAction,
  });

  expect(host.textContent).toContain('You kept this possible path for now.');
  await click(host.querySelector('.future-hypothesis-revision-button'));
  expect(host.textContent).toContain(
    'Set aside. The original response remains in your history.',
  );
  expect(onAction).toHaveBeenNthCalledWith(
    1,
    'path-1',
    'response-17',
    'retract',
  );
  await click(host.querySelector('.future-hypothesis-revision-button'));
  expect(host.textContent).toContain('You kept this possible path for now.');
  expect(onAction).toHaveBeenNthCalledWith(
    2,
    'path-1',
    'response-17',
    'restore',
  );
});

it('makes clear that passing does not add a preference', async () => {
  await mount({
    deck,
    responses: {
      'path-1': { response: 'pass', responseId: 'response-pass' },
    },
    busyProposalId: null,
    onRespond: vi.fn(),
    onAction: vi.fn(),
  });
  expect(host.querySelector('.future-hypothesis-state').textContent).toBe(
    'You passed on this path; passing adds no preference.',
  );
});

it('restores an inactive response state from persisted response data', async () => {
  const onAction = vi.fn(async () => {});
  await mount({
    deck,
    responses: {
      'path-1': {
        response: 'not-for-me',
        responseId: 'response-retracted',
        active: false,
      },
    },
    busyProposalId: null,
    onRespond: vi.fn(),
    onAction,
  });

  expect(host.textContent).toContain(
    'Set aside. The original response remains in your history.',
  );
  const restore = host.querySelector('.future-hypothesis-revision-button');
  expect(restore.textContent).toBe('Restore this response');
  await click(restore);
  expect(onAction).toHaveBeenCalledWith(
    'path-1',
    'response-retracted',
    'restore',
  );
});

it('keeps pass and skip easy, and limits a busy state to its proposal', async () => {
  await mount({
    deck,
    responses: {},
    busyProposalId: 'path-2',
    onRespond: vi.fn(),
    onAction: vi.fn(),
  });
  const groups = host.querySelectorAll('.future-hypothesis-actions');
  expect(groups[0].querySelector('.future-hypothesis-choice-pass').disabled).toBe(
    false,
  );
  expect(groups[1].querySelectorAll('button:disabled')).toHaveLength(3);
  expect(groups[2].querySelector('.future-hypothesis-choice-pass').disabled).toBe(
    false,
  );
  expect(host.querySelector('.future-hypotheses-footer').textContent).toContain(
    'You can leave the rest open.',
  );
});

it('announces loading and parent errors while honoring a global disabled state', async () => {
  await mount({
    deck,
    responses: {},
    busyProposalId: null,
    loading: true,
    disabled: true,
    error: 'These suggestions are temporarily unavailable.',
    onRespond: vi.fn(),
    onAction: vi.fn(),
  });
  const section = host.querySelector('.future-hypotheses');
  expect(section.getAttribute('aria-busy')).toBe('true');
  expect(host.querySelector('[role="status"]').textContent).toContain(
    'Gathering a few possible word paths…',
  );
  expect(host.querySelector('[role="alert"]').textContent).toBe(
    'These suggestions are temporarily unavailable.',
  );
  expect(host.querySelectorAll('.future-hypothesis-actions button:disabled')).toHaveLength(9);
});

it('announces callback failures without losing the available choices', async () => {
  await mount({
    deck: { ...deck, items: [deck.items[0]] },
    responses: {},
    busyProposalId: null,
    onRespond: () => {
      throw new Error('Local response storage is unavailable.');
    },
    onAction: vi.fn(),
  });
  await click(host.querySelector('.future-hypothesis-choice-keep'));
  expect(host.querySelector('[role="alert"]').textContent).toBe(
    'Local response storage is unavailable.',
  );
  expect(host.querySelectorAll('.future-hypothesis-actions button')).toHaveLength(
    3,
  );
});

it('closes new responses and restores on an expired deck while keeping retraction available', async () => {
  const onAction = vi.fn(async () => {});
  const expiredDeck = { ...deck, expired: true };
  await mount({
    deck: expiredDeck,
    responses: {
      'path-1': { response: 'keep', responseId: 'response-active', active: true },
      'path-2': {
        response: 'not-for-me',
        responseId: 'response-inactive',
        active: false,
      },
    },
    busyProposalId: null,
    onRespond: vi.fn(),
    onAction,
  });

  expect(host.querySelector('.future-hypotheses-expired').textContent).toContain(
    'new responses and restores are closed',
  );
  expect(host.querySelectorAll('.future-hypothesis-choice')).toHaveLength(0);
  const revisions = host.querySelectorAll('.future-hypothesis-revision-button');
  expect(revisions[0].textContent).toBe('Undo this response');
  expect(revisions[0].disabled).toBe(false);
  expect(revisions[1].textContent).toBe('Restore this response');
  expect(revisions[1].disabled).toBe(true);

  await click(revisions[0]);
  expect(onAction).toHaveBeenCalledWith(
    'path-1',
    'response-active',
    'retract',
  );
});

it('explains an expired deck without saved responses', async () => {
  await mount({
    deck: { ...deck, expired: true },
    responses: {},
    busyProposalId: null,
    onRespond: vi.fn(),
    onAction: vi.fn(),
  });
  expect(host.querySelector('.future-hypotheses-expired')).not.toBeNull();
  expect(host.querySelectorAll('.future-hypothesis-actions')).toHaveLength(0);
});
