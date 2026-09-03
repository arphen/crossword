import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { HarnessPage } from './harness/HarnessPage';
import { resolveHarnessFixture, resolveHarnessMode } from './harness/fixtures';
import './legacy.css';

const root = document.getElementById('root');

if (!root) {
  throw new Error('The application root is missing.');
}

const harnessQuery = new URLSearchParams(window.location.search);
const harnessFixture = harnessQuery.get('fixture');
const isHarness = window.location.pathname === '/harness' || harnessFixture !== null;

createRoot(root).render(
  <StrictMode>
    {isHarness ? (
      <HarnessPage
        fixtureId={harnessFixture ?? resolveHarnessFixture(null).id}
        mode={resolveHarnessMode(harnessQuery.get('mode'))}
      />
    ) : (
      <App />
    )}
  </StrictMode>
);

if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').then((registration) => {
    const announceUpdate = () => window.dispatchEvent(new Event('crossword-sw-update'));
    if (registration.waiting) announceUpdate();
    registration.addEventListener('updatefound', () => {
      const worker = registration.installing;
      worker?.addEventListener('statechange', () => {
        if (worker.state === 'installed' && navigator.serviceWorker.controller) announceUpdate();
      });
    });
  }).catch(() => undefined);
}
