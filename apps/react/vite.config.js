import { defineConfig } from 'vite';
const backend = process.env.CROSSWORD_BACKEND ?? 'http://127.0.0.1:5001';
export default defineConfig({
  server: { host: '127.0.0.1', port: 5174, strictPort: true, proxy: {
    '/static': backend, '/random_crossword': backend, '/crossword_by_date': backend,
    '/api': backend, '/socket.io': { target: backend, ws: true }
  } },
  esbuild: { jsx: 'automatic' },
  // Builds land in Flask's static tree; relative asset URLs let Flask serve
  // them under /static/react/ without extra Flask routes. The dev server
  // keeps root-absolute URLs because base only applies to builds.
  base: './',
  build: { outDir: '../../src/crossword/static/react', emptyOutDir: true },
});
