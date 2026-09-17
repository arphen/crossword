import axios from 'axios';
import { io } from 'socket.io-client';

// An observable external store preserves the curated imperative behavior while
// React owns all rendering. No Vue runtime or template compiler is involved.
export function createController(createOptions, configuration = {}) {
  const listeners = new Set();
  const proxies = new WeakMap();
  const rawValues = new WeakMap();
  const timers = new Set();
  const intervals = new Set();
  const frames = new Set();
  let revision = 0;
  let alive = true;
  let started = false;
  let app;
  const nextTicks = [];
  const socket = configuration.socket ?? io({ autoConnect: false });
  const notify = () => { if (alive) { revision++; listeners.forEach(listener => listener()); } };
  const unwrap = value => rawValues.get(value) ?? value;
  function observe(value) {
    if (!value || typeof value !== 'object') return value;
    if (rawValues.has(value)) return value;
    if (proxies.has(value)) return proxies.get(value);
    const prototype = Object.getPrototypeOf(value);
    if (![Object.prototype, Array.prototype, Map.prototype, Set.prototype].includes(prototype)) return value;
    const proxy = new Proxy(value, {
      get(target, key) {
        // Runtime helpers (especially $refs) are fixed properties, not state.
        // Proxy invariants require returning their exact value, not a wrapper.
        const descriptor = Object.getOwnPropertyDescriptor(target, key);
        if (descriptor && !descriptor.configurable && 'value' in descriptor && !descriptor.writable) return descriptor.value;
        if (target instanceof Map || target instanceof Set) {
          if (key === 'size') return target.size;
          if (['set', 'add', 'delete', 'clear'].includes(key)) return (...args) => {
            const result = target[key](...args.map(unwrap)); notify();
            return result === target ? proxy : result;
          };
          if (key === 'get') return keyValue => observe(target.get(keyValue));
          const member = target[key];
          return typeof member === 'function' ? member.bind(target) : member;
        }
        return observe(Reflect.get(target, key));
      },
      set(target, key, value) {
        const raw = unwrap(value); const previous = target[key];
        Reflect.set(target, key, raw);
        if (previous !== raw) {
          if (target === state && options.watch?.[key]) options.watch[key].call(app, raw, previous);
          notify();
        }
        return true;
      },
      deleteProperty(target, key) { const result = Reflect.deleteProperty(target, key); notify(); return result; }
    });
    proxies.set(value, proxy); rawValues.set(proxy, value); return proxy;
  }
  const dependencies = {
    axios: configuration.axios ?? axios, socket,
    ROOM_ID: configuration.room, INITIAL_ROLE: configuration.role ?? 'across',
    setTimeout(callback, delay) { const id = window.setTimeout(() => { timers.delete(id); if (alive) callback(); }, delay); timers.add(id); return id; },
    clearTimeout(id) { window.clearTimeout(id); timers.delete(id); },
    setInterval(callback, delay) { const id = window.setInterval(() => { if (alive) callback(); }, delay); intervals.add(id); return id; },
    clearInterval(id) { window.clearInterval(id); intervals.delete(id); },
    requestAnimationFrame(callback) { const id = window.requestAnimationFrame(time => { frames.delete(id); if (alive) callback(time); }); frames.add(id); return id; },
    cancelAnimationFrame(id) { window.cancelAnimationFrame(id); frames.delete(id); }
  };
  const options = createOptions(dependencies);
  const state = typeof options.data === 'function' ? options.data() : options.data;
  app = observe(state);
  Object.defineProperties(state, {
    $refs: { value: {} },
    setRef: { value: (name, element) => { if (element) state.$refs[name] = [element]; else delete state.$refs[name]; } },
    $set: { value: (target, key, value) => { target[key] = value; notify(); } },
    $forceUpdate: { value: notify },
    $nextTick: { value: callback => { nextTicks.push(callback); notify(); } }
  });
  for (const [name, method] of Object.entries(options.methods)) Object.defineProperty(state, name, { value: method.bind(app) });
  for (const [name, getter] of Object.entries(options.computed ?? {})) Object.defineProperty(state, name, { get: () => getter.call(app) });
  return {
    app,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    snapshot: () => revision,
    flush() { nextTicks.splice(0).forEach(callback => callback()); },
    start() { if (started) return; started = true; options.created?.call(app); options.mounted?.call(app); socket.connect?.(); },
    dispose() {
      options.beforeUnmount?.call(app); alive = false;
      window.removeEventListener('online', app.handleOnlineStatus);
      window.removeEventListener('offline', app.handleOnlineStatus);
      document.removeEventListener('click', app.handleDocumentClick);
      timers.forEach(window.clearTimeout); intervals.forEach(window.clearInterval); frames.forEach(window.cancelAnimationFrame);
      socket.removeAllListeners?.(); socket.disconnect?.(); listeners.clear();
    }
  };
}
