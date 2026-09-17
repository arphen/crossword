import { defineConfig } from 'vite';
const backend = process.env.CROSSWORD_BACKEND ?? 'http://127.0.0.1:5001';
export default defineConfig({
  server: { host: '127.0.0.1', port: 5174, strictPort: true, proxy: {
    '/static': backend, '/random_crossword': backend, '/crossword_by_date': backend,
    '/api': backend, '/socket.io': { target: backend, ws: true }
  } },
  esbuild: { jsx: 'automatic' },
  build: { outDir: '../../src/crossword/static/react', emptyOutDir: true },
});
