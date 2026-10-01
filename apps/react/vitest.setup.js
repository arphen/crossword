// jsdom's window.localStorage ends up undefined under Node 24 because Node
// already defines a (file-backed, unavailable-by-default) global of the same
// name. Suites written against a working Web Storage global go red. Provide a
// minimal in-memory store so the assumed environment holds. Fresh per test
// file, like a new jsdom origin.
class MemoryStorage {
  constructor() {
    this._entries = new Map();
  }
  get length() {
    return this._entries.size;
  }
  key(index) {
    return [...this._entries.keys()][index] ?? null;
  }
  getItem(key) {
    const value = this._entries.get(String(key));
    return value === undefined ? null : value;
  }
  setItem(key, value) {
    this._entries.set(String(key), String(value));
  }
  removeItem(key) {
    this._entries.delete(String(key));
  }
  clear() {
    this._entries.clear();
  }
}

function descriptorMissing(name) {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, name);
  if (!descriptor) return true;
  if (typeof descriptor.get === 'function') return true;
  return descriptor.value === undefined || descriptor.value === null;
}

for (const name of ['localStorage', 'sessionStorage']) {
  if (descriptorMissing(name)) {
    Object.defineProperty(globalThis, name, {
      value: new MemoryStorage(),
      configurable: true,
      writable: true,
    });
  }
}
