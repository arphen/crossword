// @vitest-environment jsdom
import React, { act } from 'react';
import { afterEach, expect, it } from 'vitest';
import { createRoot } from 'react-dom/client';
import ClueQualityNotes from './ClueQualityNotes';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const provenance = {
  clueQuality: {
    issueCount: 1,
    grounding: {
      entries: [
        {
          id: '1A',
          status: 'semantic-unverified',
          riskFlags: ['unsupported-factual-surface'],
        },
      ],
      signalCounts: {
        'question-mark': 1,
        brackets: 2,
      },
      familyCounts: { definition: 73, pun: 1 },
    },
  },
  crossingSupport: {
    status: 'measured',
    entryCount: 74,
    weakWithoutCrossing: ['4D'],
  },
  constructionEvidence: {
    footholdSeedPlan: {
      version: 'private-foothold-seed-plan-v1',
      targetCount: 4,
      seededTargetCount: 3,
      unseededTargetCount: 1,
    },
  },
};

let host;
let root;

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  host?.remove();
  root = null;
  host = null;
});

it('keeps local clue warnings collapsed until requested', async () => {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () =>
    root.render(
      <ClueQualityNotes
        provenance={provenance}
        entries={[{ clue_number: 1, direction: 'across', clue_text: 'Singer with a hit song?' }]}
      />,
    ),
  );

  expect(host.textContent).toContain('1 local clue note');
  expect(host.querySelector('details').open).toBe(false);
  await act(async () => host.querySelector('summary').click());
  expect(host.querySelector('details').open).toBe(true);
  expect(host.textContent).toContain('Singer with a hit song?');
  expect(host.textContent).toContain('factual surface is unverified');
  expect(host.textContent).toContain('Structural crossings measured for 74 entries');
  expect(host.textContent).toContain('Player support remains unmeasured');
  expect(host.textContent).toContain('A structural seed is available for 3 of 4 weaker entries');
  expect(host.textContent).toContain('Surface signals observed: definition 73 · pun 1');
  expect(host.textContent).toContain('Literal clue markers observed: brackets 2 · question marks 1');
  expect(host.textContent).toContain('do not establish a clue');
});

it('renders nothing when no provenance quality is present', async () => {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root.render(<ClueQualityNotes provenance={null} />));
  expect(host.firstChild).toBeNull();
});

it('labels an optional local challenger as advisory evidence', async () => {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () =>
    root.render(
      <ClueQualityNotes
        provenance={{
          ...provenance,
          semanticClueChallenge: {
            status: 'completed',
            checkedCount: 74,
          },
        }}
      />,
    ),
  );

  await act(async () => host.querySelector('summary').click());
  expect(host.textContent).toContain('optional local challenger compared 74 clue surfaces');
  expect(host.textContent).toContain('advisory and unverified');
});

it('reports when a weekday surface floor was attempted but not met', async () => {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () =>
    root.render(
      <ClueQualityNotes
        provenance={{
          ...provenance,
          clueDiversity: {
            status: 'varied-below-recipe-floor',
            nonDefinitionFamilies: ['pun', 'fill-blank'],
            requiredNonDefinitionFamilies: 5,
            repair: { status: 'repaired', rewrittenCount: 2 },
          },
        }}
      />,
    ),
  );

  await act(async () => host.querySelector('summary').click());
  expect(host.textContent).toContain('The writer reached 2 of 5 requested clue families');
  expect(host.textContent).toContain("recipe's visible variety target was not met");
});

it('surfaces non-keep challenger recommendations without turning them into profile controls', async () => {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () =>
    root.render(
      <ClueQualityNotes
        provenance={{
          ...provenance,
          clueQuality: {
            ...provenance.clueQuality,
            issueCount: 0,
            grounding: {
              ...provenance.clueQuality.grounding,
              entries: [{ id: '1A', riskFlags: [] }],
            },
          },
          semanticClueChallenge: {
            status: 'completed',
            checkedCount: 1,
            byId: {
              '1A': {
                disposition: 'review',
                confidence: 'medium',
                reason: 'The identity claim needs a source.',
              },
            },
          },
        }}
        entries={[{ clue_number: 1, direction: 'across', clue_text: 'Singer with a hit song?' }]}
      />
    ),
  );

  await act(async () => host.querySelector('summary').click());
  expect(host.textContent).toContain('local challenger recommends review');
  expect(host.textContent).toContain('The identity claim needs a source.');
  expect(host.textContent).toContain('Keep this note for future puzzles');
  expect(host.querySelector('button.future-clue-quality-flag')).not.toBeNull();
});

it('shows when exact clue text came from a configured reviewed pack', async () => {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () =>
    root.render(
      <ClueQualityNotes
        provenance={{
          ...provenance,
          reviewedCluePack: { matchedCount: 4, contextCount: 2 },
        }}
      />,
    ),
  );

  await act(async () => host.querySelector('summary').click());
  expect(host.textContent).toContain(
    '4 clue surfaces came from the configured reviewed pack',
  );
  expect(host.textContent).toContain(
    'Reviewed senses or facts also supplied bounded context for 2 uncovered clues',
  );
  expect(host.textContent).toContain('not a publication claim');
});

it('explains answer-free scaffolds created for ungrounded factual surfaces', async () => {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () =>
    root.render(
      <ClueQualityNotes
        provenance={{
          ...provenance,
          clueQuality: {
            ...provenance.clueQuality,
            fallbackCount: 2,
          },
        }}
      />,
    ),
  );

  await act(async () => host.querySelector('summary').click());
  expect(host.textContent).toContain(
    '2 clue surfaces use an answer-free crossing scaffold',
  );
  expect(host.textContent).toContain('no reviewed source supported the original surface');
});

it('distinguishes exact reviewed joins from the broader pack match count', async () => {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () =>
    root.render(
      <ClueQualityNotes
        provenance={{
          ...provenance,
          clueQuality: {
            ...provenance.clueQuality,
            grounding: {
              ...provenance.clueQuality.grounding,
              reviewedCount: 1,
              entries: [
                { id: '1A', semanticStatus: 'reviewed-source', riskFlags: [] },
              ],
            },
          },
        }}
      />,
    ),
  );

  await act(async () => host.querySelector('summary').click());
  expect(host.textContent).toContain(
    '1 exact visible clue has a reviewed sense or fact join',
  );
  expect(host.textContent).toContain('not evidence that the player knows the answer');
});

it('labels a bounded clue-surface diversity repair as advisory', async () => {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () =>
    root.render(
      <ClueQualityNotes
        provenance={{
          ...provenance,
          clueDiversity: {
            repair: { status: 'repaired', rewrittenCount: 3 },
          },
        }}
      />,
    ),
  );

  await act(async () => host.querySelector('summary').click());
  expect(host.textContent).toContain('A bounded local pass added 3 visibly signalled clue surfaces');
  expect(host.textContent).toContain('does not establish meaning');
});
