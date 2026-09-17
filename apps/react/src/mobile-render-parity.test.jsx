// @vitest-environment jsdom
import React, { act, useLayoutEffect, useSyncExternalStore } from 'react';
import { createRoot } from 'react-dom/client';
import Vue from 'vue/dist/vue.common.js';
import { afterEach, expect, it, vi } from 'vitest';
import source from '../../../src/crossword/static/mobile.js?raw';
import template from '../../../src/crossword/templates/mobile.html?raw';
import { createController } from './controller';
import { createOptions } from './behavior/mobile';
import MobileView from './MobileView';

const entries = [
  { clue_number: 1, clue_text: 'Feline', direction: 'across', start_x: 0, start_y: 0, characters: [...'CAT'].map(letters => ({ letters })) },
  { clue_number: 1, clue_text: 'Rogue', direction: 'down', start_x: 0, start_y: 0, characters: [...'CAD'].map(letters => ({ letters })) },
  { clue_number: 3, clue_text: 'Canine', direction: 'across', start_x: 0, start_y: 2, characters: [...'DOG'].map(letters => ({ letters })) },
];
const cleanup = [];
afterEach(async () => {
  for (const dispose of cleanup.splice(0).reverse()) await dispose();
  document.body.replaceChildren();
  vi.unstubAllGlobals();
});
async function mount(engine) {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.stubGlobal('alert', vi.fn());
  const handlers = new Map();
  const socket = { on: (name, fn) => handlers.set(name, fn), emit: vi.fn(), connect() {}, disconnect() {}, removeAllListeners() { handlers.clear(); } };
  const axios = { get: vi.fn(async () => ({ data: { entries: structuredClone(entries) } })) };
  const host = document.createElement('div');
  document.body.append(host);
  let controller, app;
  if (engine === 'vue') {
    let options;
    new Function('Vue', 'io', 'axios', 'ROOM_ID', 'INITIAL_ROLE', source)(function Capture(value) { options = value; }, () => socket, axios, 'TEST', 'across');
    // Compile the actual curated markup, not a reimplementation of its bindings.
    options.template = template.slice(template.indexOf('    <div id="app">'), template.indexOf('    <script>', template.indexOf('<body>')));
    delete options.el;
    app = new Vue(options).$mount();
    host.append(app.$el);
    cleanup.push(() => { app.$destroy(); host.remove(); handlers.clear(); });
  } else {
    controller = createController(createOptions, { socket, axios, room: 'TEST', role: 'across' });
    app = controller.app;
    function View() {
      useSyncExternalStore(controller.subscribe, controller.snapshot);
      useLayoutEffect(() => controller.flush());
      return <MobileView app={app} />;
    }
    const root = createRoot(host);
    await act(async () => { root.render(<View />); });
    await act(async () => controller.start());
    cleanup.push(async () => { await act(async () => root.unmount()); controller.dispose(); host.remove(); });
  }
  async function settle(action = () => {}) {
    if (engine === 'react') await act(async () => { await action(); });
    else { await action(); await Vue.nextTick(); }
  }
  await settle(() => handlers.get('game_state')({ grid: {}, puzzle_date: '260829' }));
  await settle();
  const q = selector => host.querySelector(selector);
  const click = selector => settle(() => {
    const target = q(selector);
    // dispatchEvent alone omits the browser's pointer-down focus default.
    // Clicking Check/Swap should focus the button before its click handler.
    if (target.matches('button,input,select')) target.focus();
    target.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });
  const input = value => settle(() => { const el = q('input'); el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); });
  const key = value => settle(() => q('input').dispatchEvent(new KeyboardEvent('keydown', { key: value, bubbles: true })));
  const snapshot = () => ({
    role: q('.role-badge').textContent.trim(), label: q('.check-btn').textContent.trim(),
    clues: [...host.querySelectorAll('.clue-item')].map(li => ({
      number: li.querySelector('.clue-number').textContent.trim(), classes: [...li.classList].sort(),
      cells: [...li.querySelectorAll('.char-box')].map(el => ({ text: el.textContent.trim(), classes: [...el.classList].sort() })),
      input: !!li.querySelector('input'), focused: li.contains(document.activeElement),
    })),
    modal: !!q('.modal-overlay'), emits: structuredClone(socket.emit.mock.calls),
  });
  return { app, host, q, click, input, key, settle, handlers, snapshot };
}
async function compare(scenario) {
  const reference = await mount('vue');
  const expected = await scenario(reference);
  const port = await mount('react');
  expect(await scenario(port)).toEqual(expected);
  return expected;
}

it('renders clue/cell selection, hidden-input focus and input/backspace boundaries like Vue', async () => {
  const trace = await compare(async ui => {
    const states = [];
    await ui.click('.clue-item .clue-text'); states.push(ui.snapshot());
    await ui.input('cq'); states.push(ui.snapshot());
    await ui.key('Backspace'); states.push(ui.snapshot());
    await ui.click('.clue-item:nth-child(2) .char-box:nth-child(3)'); states.push(ui.snapshot());
    await ui.input('g'); states.push(ui.snapshot());
    await ui.key('Backspace'); states.push(ui.snapshot());
    return states;
  });
  expect(trace[0].clues[0]).toMatchObject({ input: true, focused: true, classes: ['active', 'clue-item'] });
  expect(trace[1].clues[0].cells[0].text).toBe('Q');
  expect(trace[1].clues[0].cells[1].classes).toContain('active-cell');
  expect(trace[2].clues[0].cells[0].text).toBe('');
  expect(trace[3].clues[1].focused).toBe(true);
  expect(trace[4].clues[1].cells[2]).toMatchObject({ text: 'G', classes: ['active-cell', 'char-box', 'filled'] });
  expect(trace[5].clues[1].cells[2].classes).toContain('active-cell');
});

it('renders check colors, solved reorder, sticky selection and refocus after reordering like Vue', async () => {
  const trace = await compare(async ui => {
    await ui.click('.clue-item .clue-text');
    for (const char of 'CAT') await ui.input(char);
    await ui.settle(() => ui.handlers.get('cell_updated')({ row: 2, col: 1, value: 'X' }));
    await ui.click('.check-btn'); const checked = ui.snapshot();
    await ui.click('.check-btn'); const cleared = ui.snapshot();
    await ui.click('.clue-item:nth-child(2) .char-box:nth-child(2)'); const refocused = ui.snapshot();
    return { checked, cleared, refocused };
  });
  expect(trace.checked.label).toBe('Clear Errors');
  expect(trace.checked.clues[0].cells.every(c => c.classes.includes('correct'))).toBe(true);
  expect(trace.checked.clues[1].cells[1].classes).toContain('incorrect');
  expect(trace.cleared.clues.map(c => c.number)).toEqual(['3', '1']);
  expect(trace.cleared.clues[1].classes).toEqual(['active', 'clue-item', 'solved']);
  expect(trace.cleared.clues[0].cells[1].text).toBe('');
  expect(trace.refocused.clues[1].focused).toBe(true);
  expect(trace.refocused.clues[1].cells[1].classes).toContain('active-cell');
});

it('renders swap denial/acceptance and server-confirmed role/selection reset like Vue', async () => {
  const trace = await compare(async ui => {
    await ui.click('.clue-item .clue-text');
    await ui.click('.swap-btn');
    await ui.settle(() => ui.handlers.get('swap_requested')());
    const requested = ui.snapshot();
    await ui.click('.btn-deny'); const denied = ui.snapshot();
    await ui.settle(() => ui.handlers.get('swap_requested')());
    await ui.click('.btn-accept'); const accepted = ui.snapshot();
    await ui.settle(() => ui.handlers.get('swap_confirmed')()); const confirmed = ui.snapshot();
    return { requested, denied, accepted, confirmed };
  });
  expect(trace.requested.modal).toBe(true);
  expect(trace.denied.modal).toBe(false);
  expect(trace.accepted.role).toBe('down');
  expect(trace.accepted.clues).toHaveLength(1);
  expect(trace.confirmed.role).toBe('across'); // preserve Vue optimistic + broadcast double toggle
  expect(trace.confirmed.clues.every(c => !c.input && !c.classes.includes('active'))).toBe(true);
});
