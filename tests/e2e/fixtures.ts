import { test as base, expect } from '@playwright/test';

export const test = base.extend<{ offlineHarness: void }>({
  offlineHarness: [async ({ context, page, request }, use, testInfo) => {
    const logs: string[] = [];
    const forbidden: string[] = [];
    const pageErrors: string[] = [];
    const local = (url: string) => {
      const parsed = new URL(url);
      return parsed.hostname === '127.0.0.1' && parsed.port === (process.env.CROSSWORD_E2E_BACKEND_PORT ?? '5002');
    };
    // No mocked application responses: allow only the isolated Flask app.
    await context.route('**/*', async route => {
      if (local(route.request().url())) await route.continue();
      else {
        forbidden.push(route.request().url());
        await route.abort('blockedbyclient');
      }
    });
    await context.routeWebSocket('**/*', ws => {
      if (local(ws.url())) ws.connectToServer();
      else {
        forbidden.push(ws.url());
        ws.close();
      }
    });
    page.on('console', message => logs.push(`[${message.type()}] ${message.text()}`));
    page.on('pageerror', error => { pageErrors.push(error.message); logs.push(`[pageerror] ${error.stack}`); });
    page.on('requestfailed', req => logs.push(`[requestfailed] ${req.url()} ${req.failure()?.errorText}`));
    // Avoid the optional bulk prefetch job; keep normal initial puzzle/API reads.
    await context.addInitScript(() => localStorage.setItem('lastCachingTime', String(Date.now())));

    const health = await request.get('/api/health');
    expect(health.ok()).toBeTruthy();
    expect(await health.json()).toEqual({ status: 'ok', database: 'temporary-sqlite', fixture: 'synthetic' });
    const list = await request.get('/api/completed_puzzles');
    expect(list.ok()).toBeTruthy();
    for (const record of await list.json()) {
      expect((await request.delete(`/api/completed_puzzles/${record.puzzle_date}`)).ok()).toBeTruthy();
    }
    await use();
    await testInfo.attach('browser.log', { body: logs.join('\n'), contentType: 'text/plain' });
    expect(forbidden, 'Unexpected outbound browser requests').toEqual([]);
    expect(pageErrors, 'Uncaught frontend errors').toEqual([]);
  }, { auto: true }],
});
export { expect };
