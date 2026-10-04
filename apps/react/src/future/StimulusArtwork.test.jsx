// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it } from 'vitest';
import StimulusArtwork from './StimulusArtwork';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;

async function render(item, presentationMode) {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () =>
    root.render(
      <StimulusArtwork item={item} presentationMode={presentationMode} />,
    ),
  );
  return container.querySelector('.future-stimulus-art');
}

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  container?.remove();
  root = null;
  container = null;
});

it('renders decorative art for each of the seven versioned stimulus kinds', async () => {
  const cases = [
    {
      item: { id: 'thread-knot', kind: 'object', legacy_ids: ['thread'] },
      child: '.future-signifier',
      text: '',
    },
    {
      item: {
        id: 'form-offset-arcs',
        kind: 'abstract_form',
        accessible_label: 'Two facing arcs.',
      },
      child: '.future-stimulus-art__drawing path',
      text: '',
    },
    {
      item: {
        id: 'surface-cotton-weave',
        kind: 'texture_material',
        accessible_label: 'A woven surface.',
      },
      child: '.future-stimulus-art__texture path',
      text: '',
    },
    {
      item: {
        id: 'color-cobalt',
        kind: 'color',
        swatch_hex: '#3157A4',
        accessible_label: 'A cobalt square.',
      },
      child: '.future-stimulus-art__swatch',
      text: '',
    },
    {
      item: { id: 'numeral-two', kind: 'numeral', accessible_label: 'Two.' },
      child: '.future-stimulus-art__type',
      text: '2',
    },
    {
      item: { id: 'word-drift', kind: 'word', accessible_label: 'The word drift.' },
      child: '.future-stimulus-art__type',
      text: 'drift',
    },
    {
      item: {
        id: 'mark-ampersand',
        kind: 'typographic_mark',
        accessible_label: 'An ampersand.',
      },
      child: '.future-stimulus-art__mark',
      text: '&',
    },
  ];

  for (const { item, child, text } of cases) {
    const art = await render(item, 'visual');
    expect(art).not.toBeNull();
    expect(art.getAttribute('aria-hidden')).toBe('true');
    expect(art.getAttribute('data-stimulus-kind')).toBe(item.kind);
    expect(art.querySelector(child)).not.toBeNull();
    if (text) expect(art.textContent).toBe(text);
    await act(async () => root.unmount());
    container.remove();
    root = null;
    container = null;
  }
});

it('uses the unchanged catalog swatch in visual mode and grayscale presentation in monochrome mode', async () => {
  const item = {
    id: 'color-cobalt',
    kind: 'color',
    swatch_hex: '#3157A4',
    accessible_label: 'A cobalt square.',
  };

  let art = await render(item, 'visual');
  expect(art.querySelector('.future-stimulus-art__swatch').style.backgroundColor).toBe(
    'rgb(49, 87, 164)',
  );
  expect(item.id).toBe('color-cobalt');
  await act(async () => root.unmount());
  container.remove();
  root = null;
  container = null;

  art = await render(item, 'monochrome');
  expect(art.style.filter).toBe('grayscale(1)');
  expect(art.querySelector('.future-stimulus-art__swatch').style.backgroundColor).toBe(
    'rgb(49, 87, 164)',
  );
  expect(item.id).toBe('color-cobalt');
});

it('supports a text-equivalent presentation without exposing the decorative node to assistive technology', async () => {
  const item = {
    id: 'form-offset-arcs',
    kind: 'abstract_form',
    accessible_label: 'Two facing arcs with a gap between them.',
  };
  const art = await render(item, 'text-equivalent');

  expect(art.getAttribute('data-presentation-mode')).toBe('text-equivalent');
  expect(art.getAttribute('aria-hidden')).toBe('true');
  expect(art.querySelector('.future-stimulus-art__equivalent').textContent).toBe(
    item.accessible_label,
  );
});

it('uses stable item IDs for typographic forms and legacy IDs only for known Signifiers', async () => {
  const numeral = await render(
    { id: 'numeral-clock-time', kind: 'numeral', legacy_ids: ['03:17'] },
    'visual',
  );
  expect(numeral.textContent).toBe('03:17');
  expect(numeral.querySelector('.future-signifier')).toBeNull();

  await act(async () => root.unmount());
  container.remove();
  root = null;
  container = null;

  const zero = await render(
    { id: 'numeral-zero', kind: 'numeral', legacy_ids: ['zero'] },
    'visual',
  );
  expect(zero.querySelector('.future-signifier')).not.toBeNull();
});
