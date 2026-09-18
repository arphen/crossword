import { defineConfig } from 'vite';
const backend = process.env.CROSSWORD_BACKEND ?? 'http://127.0.0.1:5001';
export default defineConfig({
  server: { host: '127.0.0.1', port: 5174, strictPort: true, proxy: {
    '/static': backend, '/random_crossword': backend, '/crossword_by_date': backend,
    '/api': backend, '/socket.io': { target: backend, ws: true }
  } },
  // `vite preview` serves the built React app for Playwright E2E; proxy the
  // same backend routes the dev server proxies so tests hit one origin.
  preview: { host: '127.0.0.1', port: 4173, strictPort: true, proxy: {
    '/static': backend, '/random_crossword': backend, '/crossword_by_date': backend,
    '/api': backend, '/socket.io': { target: backend, ws: true }
  } },
  esbuild: { jsx: 'automatic' },
  // Flask serves this shell at both '/' and '/mobile/<room>/<role>'.
  // Absolute asset URLs keep nested mobile routes on the same built bundle.
  base: '/',
  build: { outDir: '../../src/crossword/static/react', emptyOutDir: true },
});
